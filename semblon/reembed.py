"""Recoverable re-embed of still faces onto the active YuNet+SFace pack.

Preserves persons, decisions, and face_id rows where bbox IoU matches.
Does not assume new clusters map 1:1 onto old clusters.
Does not compare across pack_ids. Does not delete the store.
Operator should backup before large libraries.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from semblon import __version__
from semblon.engine import (
    ModelPackError,
    discover_weight_hashes,
    embed_bgr,
    load_app,
    pack_id,
    process_arch,
    process_execution,
)
from semblon.identity_config import (
    CLUSTER_MIN_SIDE,
    DET_SCORE_MIN,
    DET_SIZE,
    EXPECTED_FACE_DIM,
    PACK_FAMILY,
)
from semblon.ingest import size_band
from semblon.observers import ensure_face_item
from semblon.store import connect, init_db, writer_lock


class ReembedError(ValueError):
    pass


def _checkpoint_path(store: Path) -> Path:
    return Path(store).with_suffix(Path(store).suffix + ".reembed-checkpoint.json")


def _load_checkpoint(path: Path) -> dict:
    if not path.is_file():
        return {"done_media": [], "run_id": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReembedError(f"unreadable re-embed checkpoint: {path}") from exc


def _save_checkpoint(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    return float(inter / denom) if denom > 0 else 0.0


def _status_for(face: dict) -> str:
    if face["det_score"] < DET_SCORE_MIN:
        return "rejected"
    if min(face["face_w"], face["face_h"]) < CLUSTER_MIN_SIDE:
        return "low_quality"
    return "ok"


def reembed_stills(
    store: Path,
    *,
    resume: bool = True,
    clear_clusters: bool = True,
    iou_match: float = 0.3,
) -> dict:
    """Re-detect and re-embed folder stills with the active pack.

    Matched faces (IoU >= iou_match) keep face_id / person_id / decisions.
    Unmatched old faces are marked rejected (row kept). New detections insert new rows.
    """
    store = Path(store)
    if not store.is_file():
        raise ReembedError(f"store not found: {store}")

    try:
        app = load_app(DET_SIZE, prefer_gpu=False)
    except ModelPackError as exc:
        raise ReembedError(str(exc)) from exc

    eng_ver = f"opencv-{cv2.__version__}"
    hashes = discover_weight_hashes()
    pid = pack_id(eng_ver, hashes)
    ckpt_path = _checkpoint_path(store)
    ckpt = _load_checkpoint(ckpt_path) if resume else {"done_media": [], "run_id": None}
    done = set(ckpt.get("done_media") or [])

    conn = connect(store)
    init_db(conn)
    run_id = ckpt.get("run_id") or (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    )
    import onnxruntime as ort

    with writer_lock():
        if not ckpt.get("run_id"):
            conn.execute(
                """INSERT INTO runs(run_id, started_at, software_version, pack_id,
                   embedding_dim, embedding_norm, config_json, runtime_json, arch, execution, ort_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    datetime.now(timezone.utc).isoformat(),
                    __version__,
                    pid,
                    EXPECTED_FACE_DIM,
                    "l2",
                    json.dumps(
                        {
                            "kind": "reembed",
                            "pack_family": PACK_FAMILY,
                            "clear_clusters": bool(clear_clusters),
                            "backup_required": True,
                            "iou_match": float(iou_match),
                        }
                    ),
                    json.dumps(
                        {
                            "identity_engine": "yunet_sface",
                            "opencv_version": cv2.__version__,
                            "ort_version": ort.__version__,
                        }
                    ),
                    process_arch(),
                    process_execution(),
                    ort.__version__,
                ),
            )
            conn.commit()

        if clear_clusters:
            conn.execute("DELETE FROM cluster_person")
            conn.execute("UPDATE faces SET cluster_id=NULL")
            conn.commit()

        rows = conn.execute(
            """SELECT m.media_id, m.path, o.observation_id
               FROM media m
               JOIN observations o ON o.media_id = m.media_id
               WHERE m.source_type = 'folder'
               ORDER BY m.path"""
        ).fetchall()

        n_media = n_faces = n_ok = n_skip = n_missing = n_matched = n_new = 0
        for row in rows:
            media_id = str(row["media_id"])
            if media_id in done:
                n_skip += 1
                continue
            path = Path(row["path"])
            obs_id = str(row["observation_id"])
            if not path.is_file():
                n_missing += 1
                done.add(media_id)
                _save_checkpoint(
                    ckpt_path,
                    {"done_media": sorted(done), "run_id": run_id, "pack_id": pid},
                )
                continue
            img = cv2.imread(str(path))
            if img is None:
                n_missing += 1
                done.add(media_id)
                _save_checkpoint(
                    ckpt_path,
                    {"done_media": sorted(done), "run_id": run_id, "pack_id": pid},
                )
                continue

            detected = embed_bgr(app, img)
            old_faces = conn.execute(
                """SELECT face_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2
                   FROM faces WHERE observation_id=?""",
                (obs_id,),
            ).fetchall()
            used_old: set[str] = set()
            used_new: set[int] = set()

            # Greedy IoU match
            pairs: list[tuple[float, str, int]] = []
            for old in old_faces:
                ob = (
                    float(old["bbox_x1"]),
                    float(old["bbox_y1"]),
                    float(old["bbox_x2"]),
                    float(old["bbox_y2"]),
                )
                for i, det in enumerate(detected):
                    score = _iou(ob, det["bbox"])
                    if score >= iou_match:
                        pairs.append((score, str(old["face_id"]), i))
            pairs.sort(reverse=True)
            for _score, fid, i in pairs:
                if fid in used_old or i in used_new:
                    continue
                used_old.add(fid)
                used_new.add(i)
                det = detected[i]
                status = _status_for(det)
                vec = np.asarray(det["embedding"], dtype=np.float32)
                blob = None if status == "rejected" else vec.tobytes()
                pack = None if status == "rejected" else pid
                dim = None if status == "rejected" else int(vec.size)
                x1, y1, x2, y2 = det["bbox"]
                fw, fh = det["face_w"], det["face_h"]
                conn.execute(
                    """UPDATE faces SET run_id=?, bbox_x1=?, bbox_y1=?, bbox_x2=?, bbox_y2=?,
                       det_score=?, face_w=?, face_h=?, size_band=?, embedding=?,
                       embedding_pack=?, embedding_dim=?, status=?, cluster_id=NULL
                       WHERE face_id=?""",
                    (
                        run_id,
                        x1, y1, x2, y2,
                        det["det_score"], fw, fh, size_band(fw, fh),
                        blob, pack, dim, status, fid,
                    ),
                )
                n_matched += 1
                n_faces += 1
                if status == "ok":
                    n_ok += 1

            for old in old_faces:
                fid = str(old["face_id"])
                if fid in used_old:
                    continue
                conn.execute(
                    """UPDATE faces SET status='rejected', embedding=NULL,
                       embedding_pack=NULL, embedding_dim=NULL, cluster_id=NULL
                       WHERE face_id=?""",
                    (fid,),
                )

            for i, det in enumerate(detected):
                if i in used_new:
                    continue
                status = _status_for(det)
                vec = np.asarray(det["embedding"], dtype=np.float32)
                blob = None if status == "rejected" else vec.tobytes()
                pack = None if status == "rejected" else pid
                dim = None if status == "rejected" else int(vec.size)
                x1, y1, x2, y2 = det["bbox"]
                fw, fh = det["face_w"], det["face_h"]
                fid = uuid.uuid4().hex
                conn.execute(
                    """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                       det_score, face_w, face_h, size_band, embedding, embedding_pack, embedding_dim, status)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        fid, obs_id, run_id, x1, y1, x2, y2,
                        det["det_score"], fw, fh, size_band(fw, fh),
                        blob, pack, dim, status,
                    ),
                )
                ensure_face_item(
                    conn,
                    face_id=fid,
                    observation_id=obs_id,
                    run_id=run_id,
                    bbox=(x1, y1, x2, y2),
                    score=det["det_score"],
                    status=status,
                )
                n_new += 1
                n_faces += 1
                if status == "ok":
                    n_ok += 1

            conn.commit()
            done.add(media_id)
            n_media += 1
            _save_checkpoint(
                ckpt_path,
                {"done_media": sorted(done), "run_id": run_id, "pack_id": pid},
            )

        conn.execute(
            "UPDATE runs SET finished_at=? WHERE run_id=?",
            (datetime.now(timezone.utc).isoformat(), run_id),
        )
        conn.commit()

    return {
        "status": "SUCCESS",
        "run_id": run_id,
        "pack_id": pid,
        "pack_family": PACK_FAMILY,
        "media_processed": n_media,
        "media_skipped_checkpoint": n_skip,
        "media_missing": n_missing,
        "faces_written": n_faces,
        "faces_ok": n_ok,
        "faces_matched": n_matched,
        "faces_new": n_new,
        "checkpoint": str(ckpt_path),
        "note": (
            "Matched faces keep face_id/person_id/decisions. Re-run cluster. "
            "Do not compare to buffalo_l embeddings."
        ),
    }
