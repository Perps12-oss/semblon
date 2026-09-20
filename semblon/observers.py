"""Non-identity observation providers and persistence.

Identity remains FaceKit on faces.* only. These items never vote on
compare(), DBSCAN, or identify.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import numpy as np

from semblon.store import connect, init_db

APPEARANCE_PACK = "appearance/rgb8@1"
APPEARANCE_DIM = 24
OBJECT_PROVIDER = "opencv-contour"
CLIP_PACK = "clip/openclip-vitb32@1"
OCR_PROVIDER = "tesseract"
POSE_PROVIDER = "mediapipe-pose"
_CLIP_CACHE = None
_POSE_CACHE = None


class ProviderUnavailable(RuntimeError):
    pass


def color_histogram(img) -> bytes:
    """8-bin RGB histogram, L2-normalised. Appearance space, not identity."""
    arr = np.asarray(img)
    if arr.ndim != 3 or arr.shape[2] < 3:
        vec = np.zeros(APPEARANCE_DIM, dtype=np.float32)
        return vec.tobytes()
    b, g, r = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    hist = []
    for ch in (r, g, b):
        h, _ = np.histogram(ch, bins=8, range=(0, 256), density=False)
        hist.extend(h.astype(np.float32))
    vec = np.asarray(hist, dtype=np.float32)
    n = float(np.linalg.norm(vec))
    if n > 0:
        vec = vec / n
    return vec.tobytes()


def contour_objects(img, *, min_area: int = 400, max_regions: int = 8) -> list[dict]:
    """Cheap OpenCV contours as object observations. Not a detector pack. Not identity."""
    import cv2

    arr = np.asarray(img)
    if arr.ndim != 3:
        return []
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thr = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape[:2]
    out = []
    scored = []
    for c in contours:
        area = float(cv2.contourArea(c))
        if area < min_area:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        if bw >= w * 0.98 and bh >= h * 0.98:
            continue
        scored.append((area, (float(x), float(y), float(x + bw), float(y + bh))))
    scored.sort(reverse=True)
    for area, bbox in scored[:max_regions]:
        out.append({"bbox": bbox, "score": min(1.0, area / float(max(w * h, 1))), "class": "region"})
    return out


def optional_status() -> dict:
    """Honest availability of extra providers. Missing extras are not a crash."""
    ocr = clip = pose = False
    notes = {}
    try:
        import pytesseract  # noqa: F401

        ocr = True
    except Exception as e:
        notes["ocr"] = f"unavailable: {type(e).__name__}"
    try:
        import open_clip  # noqa: F401

        clip = True
    except Exception as e:
        notes["clip"] = f"unavailable: {type(e).__name__}"
    try:
        import mediapipe  # noqa: F401

        pose = True
    except Exception as e:
        notes["pose"] = f"unavailable: {type(e).__name__}"
    return {
        "facekit": True,
        "appearance": True,
        "object": True,
        "ocr": ocr,
        "clip": clip,
        "pose": pose,
        "notes": notes,
        "identity": "facekit only",
        "note": "optional extras never write faces.person_id or embeddings.modality=face",
    }


def ocr_image(img) -> dict | None:
    """OCR text. None = library missing. Never identity."""
    try:
        import cv2
        import pytesseract
    except Exception:
        return None
    try:
        arr = np.asarray(img)
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY) if arr.ndim == 3 else arr
        text = (pytesseract.image_to_string(gray) or "").strip()
        return {"text": text[:4000], "score": 1.0 if text else 0.0}
    except Exception as e:  # noqa: BLE001 — optional extra must not crash ingest
        return {"error": type(e).__name__, "note": str(e)[:240]}


def clip_embed(img) -> dict | None:
    """Optional CLIP visual embedding. None = unavailable. Never modality=face."""
    global _CLIP_CACHE
    try:
        import open_clip
        import torch
        from PIL import Image
    except Exception:
        return None
    try:
        if _CLIP_CACHE is None:
            model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
            model.eval()
            _CLIP_CACHE = (model, preprocess)
        model, preprocess = _CLIP_CACHE
        arr = np.asarray(img)
        if arr.ndim != 3:
            return {"error": "bad-image", "note": "need BGR"}
        rgb = arr[:, :, ::-1].copy()
        with torch.no_grad():
            feat = model.encode_image(preprocess(Image.fromarray(rgb)).unsqueeze(0))
            feat = feat / feat.norm(dim=-1, keepdim=True)
        vec = feat.squeeze(0).detach().cpu().numpy().astype(np.float32)
        return {"embedding": vec.tobytes(), "pack_id": CLIP_PACK, "dim": int(vec.size)}
    except Exception as e:  # noqa: BLE001 — optional extra must not crash ingest
        return {"error": type(e).__name__, "note": str(e)[:240]}


def pose_landmarks(img) -> dict | None:
    """Optional pose landmarks. None = unavailable. Not a person."""
    global _POSE_CACHE
    try:
        import mediapipe as mp
    except Exception:
        return None
    try:
        arr = np.asarray(img)
        if arr.ndim != 3:
            return {"error": "bad-image", "note": "need BGR"}
        h, w = arr.shape[:2]
        rgb = arr[:, :, ::-1]
        if _POSE_CACHE is None:
            _POSE_CACHE = mp.solutions.pose.Pose(static_image_mode=True)
        res = _POSE_CACHE.process(rgb)
        if not res.pose_landmarks:
            return {"landmarks": [], "score": 0.0}
        lms = [
            {"i": i, "x": float(p.x), "y": float(p.y), "z": float(p.z), "v": float(p.visibility)}
            for i, p in enumerate(res.pose_landmarks.landmark)
        ]
        xs = [p["x"] for p in lms]
        ys = [p["y"] for p in lms]
        bbox = (min(xs) * w, min(ys) * h, max(xs) * w, max(ys) * h)
        return {"landmarks": lms[:33], "score": 1.0, "bbox": bbox}
    except Exception as e:  # noqa: BLE001 — optional extra must not crash ingest
        return {"error": type(e).__name__, "note": str(e)[:240]}


def persist_item(
    conn,
    *,
    observation_id: str,
    run_id: str,
    kind: str,
    provider: str,
    payload: dict,
    bbox=None,
    score=None,
    face_id=None,
    embedding: bytes | None = None,
    modality: str | None = None,
    pack_id: str | None = None,
    dim: int | None = None,
) -> str:
    item_id = uuid.uuid4().hex
    x1 = y1 = x2 = y2 = None
    if bbox is not None:
        x1, y1, x2, y2 = bbox
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
           bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json, face_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            item_id,
            observation_id,
            run_id,
            kind,
            provider,
            x1,
            y1,
            x2,
            y2,
            score,
            json.dumps(payload),
            face_id,
        ),
    )
    if embedding is not None:
        if not modality or not pack_id or not dim:
            raise ValueError("embedding requires modality, pack_id, dim")
        if modality == "face":
            raise ValueError("face identity embeddings stay on faces; not embeddings table")
        conn.execute(
            """INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
               VALUES (?,?,?,?,?,?)""",
            (uuid.uuid4().hex, item_id, modality, pack_id, int(dim), embedding),
        )
    return item_id


def observe_bgr(conn, *, observation_id: str, run_id: str, img, observers: tuple[str, ...]) -> dict:
    """Run non-identity observers. 'face' is ignored here (FaceKit owns faces)."""
    counts = {"appearance": 0, "object": 0, "text": 0, "pose": 0, "clip": 0}
    wanted = {o.strip() for o in observers if o.strip() and o.strip() != "face"}
    if "color" in wanted or "appearance" in wanted:
        blob = color_histogram(img)
        persist_item(
            conn,
            observation_id=observation_id,
            run_id=run_id,
            kind="appearance",
            provider="color-hist",
            payload={"space": "rgb8"},
            embedding=blob,
            modality="appearance",
            pack_id=APPEARANCE_PACK,
            dim=APPEARANCE_DIM,
        )
        counts["appearance"] += 1
    if "object" in wanted:
        for obj in contour_objects(img):
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="object",
                provider=OBJECT_PROVIDER,
                payload={"class": obj["class"]},
                bbox=obj["bbox"],
                score=obj["score"],
            )
            counts["object"] += 1
    if "text" in wanted or "ocr" in wanted:
        rec = ocr_image(img)
        if rec is None:
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="text",
                provider=OCR_PROVIDER,
                payload={"status": "unavailable", "note": optional_status()["notes"].get("ocr", "unavailable")},
                score=0.0,
            )
        elif rec.get("error"):
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="text",
                provider=OCR_PROVIDER,
                payload={"status": "error", "error": rec["error"], "note": rec.get("note", "")},
                score=0.0,
            )
        else:
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="text",
                provider=OCR_PROVIDER,
                payload={"text": rec.get("text") or "", "identity": "not facekit"},
                score=rec.get("score"),
            )
            counts["text"] += 1
    if "clip" in wanted:
        rec = clip_embed(img)
        if rec is None:
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="clip",
                provider="open-clip",
                payload={"status": "unavailable", "note": optional_status()["notes"].get("clip", "unavailable")},
                score=0.0,
            )
        elif rec.get("error"):
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="clip",
                provider="open-clip",
                payload={"status": "error", "error": rec["error"], "note": rec.get("note", "")},
                score=0.0,
            )
        else:
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="clip",
                provider="open-clip",
                payload={"space": "clip", "identity": "not facekit"},
                embedding=rec["embedding"],
                modality="clip",
                pack_id=rec["pack_id"],
                dim=rec["dim"],
            )
            counts["clip"] += 1
    if "pose" in wanted:
        rec = pose_landmarks(img)
        if rec is None:
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="pose",
                provider=POSE_PROVIDER,
                payload={"status": "unavailable", "note": optional_status()["notes"].get("pose", "unavailable")},
                score=0.0,
            )
        elif rec.get("error"):
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="pose",
                provider=POSE_PROVIDER,
                payload={"status": "error", "error": rec["error"], "note": rec.get("note", "")},
                score=0.0,
            )
        else:
            persist_item(
                conn,
                observation_id=observation_id,
                run_id=run_id,
                kind="pose",
                provider=POSE_PROVIDER,
                payload={"landmarks": rec.get("landmarks") or [], "identity": "not facekit"},
                bbox=rec.get("bbox"),
                score=rec.get("score"),
            )
            counts["pose"] += 1
    return counts


def ensure_face_item(conn, *, face_id: str, observation_id: str, run_id: str, bbox=None, score=None, status: str = "ok") -> str:
    """Dual-write a FaceKit face as an observation_item. No identity embedding here."""
    row = conn.execute(
        "SELECT item_id FROM observation_items WHERE face_id=? AND kind='face'",
        (face_id,),
    ).fetchone()
    if row:
        return row["item_id"] if not isinstance(row, tuple) else row[0]
    return persist_item(
        conn,
        observation_id=observation_id,
        run_id=run_id,
        kind="face",
        provider="facekit",
        payload={"status": status, "identity": "faces table only"},
        bbox=bbox,
        score=score,
        face_id=face_id,
    )


def snapshot_groups_from_clusters(conn, run_id: str) -> dict:
    """observation_groups from DBSCAN clusters. Group ≠ person."""
    conn.execute(
        """DELETE FROM group_members WHERE group_id IN
           (SELECT group_id FROM observation_groups WHERE run_id=? AND kind='face')""",
        (run_id,),
    )
    conn.execute(
        "DELETE FROM observation_groups WHERE run_id=? AND kind='face'",
        (run_id,),
    )
    clusters = conn.execute(
        "SELECT cluster_id, strategy, face_count FROM clusters WHERE run_id=?",
        (run_id,),
    ).fetchall()
    n_groups = 0
    n_members = 0
    for c in clusters:
        faces = conn.execute(
            "SELECT face_id, observation_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2, det_score, status FROM faces WHERE cluster_id=?",
            (c["cluster_id"],),
        ).fetchall()
        item_ids = []
        for f in faces:
            bbox = (f["bbox_x1"], f["bbox_y1"], f["bbox_x2"], f["bbox_y2"])
            iid = ensure_face_item(
                conn,
                face_id=f["face_id"],
                observation_id=f["observation_id"],
                run_id=run_id,
                bbox=bbox,
                score=f["det_score"],
                status=f["status"],
            )
            item_ids.append(iid)
        gid = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO observation_groups(group_id, run_id, kind, strategy, member_count, status)
               VALUES (?,?,?,?,?,?)""",
            (gid, run_id, "face", c["strategy"], len(item_ids), "auto"),
        )
        for iid in item_ids:
            conn.execute(
                "INSERT OR IGNORE INTO group_members(group_id, item_id) VALUES (?,?)",
                (gid, iid),
            )
        n_groups += 1
        n_members += len(item_ids)
    conn.commit()
    return {"groups": n_groups, "members": n_members, "note": "cluster group is not a person"}


def snapshot_memory_graph(store: Path, run_id: str | None = None) -> dict:
    """Copy S6 together/events into relationship/event rows. confirmed=0. Not identity."""
    from semblon.memory import MemoryError, events, together

    p = Path(store)
    conn = connect(p)
    init_db(conn)
    try:
        tog = together(p, run_id=run_id)
        ev = events(p, run_id=run_id)
    except MemoryError:
        tog = {"items": []}
        ev = {"bursts": [], "days": [], "folders": []}
    rid = run_id or ""
    if not rid:
        row = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        rid = row["run_id"] if row else "unknown"
    conn.execute("DELETE FROM relationships WHERE confirmed=0 AND run_id=?", (rid,))
    conn.execute("DELETE FROM events WHERE confirmed=0 AND run_id=?", (rid,))
    n_rel = 0
    for item in tog.get("items") or []:
        ids = item.get("person_ids") or []
        if len(ids) < 2:
            continue
        conn.execute(
            """INSERT INTO relationships(relationship_id, run_id, kind, src_person_id, evidence_json, confirmed)
               VALUES (?,?,?,?,?,0)""",
            (
                uuid.uuid4().hex,
                rid,
                "together",
                ids[0],
                json.dumps(
                    {
                        "person_ids": ids,
                        "names": item.get("names"),
                        "media_id": item.get("media_id"),
                        "source_type": item.get("source_type"),
                    }
                ),
            ),
        )
        n_rel += 1
    n_ev = 0
    for burst in ev.get("bursts") or []:
        conn.execute(
            """INSERT INTO events(event_id, run_id, label, t_start, t_end, folder, evidence_json, confirmed)
               VALUES (?,?,?,?,?,?,?,0)""",
            (
                uuid.uuid4().hex,
                rid,
                "burst",
                burst.get("when"),
                burst.get("until"),
                burst.get("folder"),
                json.dumps(burst),
            ),
        )
        n_ev += 1
    conn.commit()
    conn.close()
    return {"relationships": n_rel, "events": n_ev, "confirmed": 0, "note": "S6 snapshot; not identity"}


def persist_derived_tracks(store: Path, run_id: str, conn=None) -> dict:
    """Write derived S7 tracks into the tracks table. Not identity. Re-runnable."""
    from semblon.tracks import TracksError, derive_tracks

    p = Path(store)
    own = conn is None
    if own:
        conn = connect(p)
        init_db(conn)
    try:
        rec = derive_tracks(p, run_id, prefer_persisted=False)
    except TracksError:
        if own:
            conn.close()
        return {"tracks": 0, "note": "no derived tracks"}
    conn.execute(
        "DELETE FROM track_members WHERE track_id IN (SELECT track_id FROM tracks WHERE run_id=?)",
        (run_id,),
    )
    conn.execute("DELETE FROM tracks WHERE run_id=?", (run_id,))
    n = 0
    for t in rec.get("tracks") or []:
        tid = t.get("track_id") or uuid.uuid4().hex
        conn.execute(
            """INSERT INTO tracks(track_id, media_id, run_id, kind, t_ms_start, t_ms_end, item_count, status)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                tid,
                t["media_id"],
                run_id,
                "face",
                t.get("t_ms_start"),
                t.get("t_ms_end"),
                int(t.get("face_count") or len(t.get("face_ids") or [])),
                "derived",
            ),
        )
        members = list(t.get("members") or [])
        if not members:
            # Fallback for payloads without member objects.
            for fid in t.get("face_ids") or []:
                row = conn.execute(
                    """
                    SELECT f.face_id, f.observation_id, f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2,
                           f.det_score, o.t_ms
                    FROM faces f
                    JOIN observations o ON o.observation_id = f.observation_id
                    WHERE f.face_id=? AND f.run_id=?
                    """,
                    (fid, run_id),
                ).fetchone()
                if row is None:
                    continue
                members.append(
                    {
                        "face_id": row["face_id"],
                        "observation_id": row["observation_id"],
                        "bbox": (row["bbox_x1"], row["bbox_y1"], row["bbox_x2"], row["bbox_y2"]),
                        "score": row["det_score"],
                        "t_ms": row["t_ms"],
                    }
                )
        for m in members:
            fid = m.get("face_id")
            oid = m.get("observation_id")
            if not fid or not oid:
                continue
            iid = ensure_face_item(
                conn,
                face_id=fid,
                observation_id=oid,
                run_id=run_id,
                bbox=m.get("bbox"),
                score=m.get("score"),
                status="ok",
            )
            conn.execute(
                "INSERT OR IGNORE INTO track_members(track_id, item_id, t_ms) VALUES (?,?,?)",
                (tid, iid, m.get("t_ms")),
            )
        n += 1
    conn.commit()
    if own:
        conn.close()
    return {"tracks": n, "note": "derived snapshot; track id is not person id"}
