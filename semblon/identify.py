"""FACE-004: 1:N identify against reviewed persons. Never against clusters.

Unknown is valid. Wrong identity > unknown. Does not auto-assign person_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from semblon.compare import CompareError, compare
from semblon.eval import DEFAULT_THRESHOLD
from semblon.store import connect, init_db


class IdentifyError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _open(store: Path, *, writable: bool = True):
    p = Path(store)
    if writable:
        conn = connect(p)
        init_db(conn)
        return conn
    import sqlite3

    if not p.is_file():
        raise IdentifyError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _require_run(conn, run_id: str):
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise IdentifyError(f"unknown run: {run_id}")
    return run


def _gallery(conn, pack_id: str, exclude_face: str | None = None):
    """Active persons' ok faces, any run, this pack. Not clusters."""
    rows = conn.execute(
        """
        SELECT f.face_id, f.embedding, f.embedding_pack, f.embedding_dim,
               f.person_id, p.display_name
        FROM faces f
        JOIN persons p ON p.person_id = f.person_id
        WHERE f.status='ok' AND f.embedding IS NOT NULL
          AND p.status='active' AND f.person_id IS NOT NULL
        ORDER BY f.face_id
        """,
    ).fetchall()
    out = []
    for r in rows:
        if exclude_face and r["face_id"] == exclude_face:
            continue
        if r["embedding_pack"] != pack_id:
            continue
        out.append(r)
    return out


def _person_scores(probe, gallery, pack_id: str) -> list[dict]:
    best: dict[str, dict] = {}
    for g in gallery:
        try:
            s = compare(
                pack_id,
                probe["embedding_dim"],
                probe["embedding"],
                pack_id,
                g["embedding_dim"],
                g["embedding"],
            )
        except CompareError:
            continue
        pid = g["person_id"]
        rec = best.get(pid)
        if rec is None or s > rec["score"]:
            best[pid] = {
                "person_id": pid,
                "display_name": g["display_name"],
                "score": float(s),
                "exemplar_face_id": g["face_id"],
            }
    ranked = sorted(best.values(), key=lambda r: (-r["score"], r["person_id"]))
    return ranked


def _decide(ranked: list[dict], threshold: float) -> dict:
    """ACCEPT only if exactly one person is at/above the identity threshold."""
    top1 = ranked[0] if ranked else None
    top2 = ranked[1] if len(ranked) > 1 else None
    score_top1 = None if top1 is None else top1["score"]
    score_top2 = None if top2 is None else top2["score"]
    margin = None
    if score_top1 is not None and score_top2 is not None:
        margin = float(score_top1 - score_top2)

    if top1 is None or score_top1 is None or score_top1 < threshold:
        decision = "UNKNOWN"
        person_id = None
        display_name = None
    elif top2 is not None and score_top2 is not None and score_top2 >= threshold:
        decision = "UNKNOWN"
        person_id = None
        display_name = None
    else:
        decision = "ACCEPT"
        person_id = top1["person_id"]
        display_name = top1["display_name"]

    return {
        "decision": decision,
        "person_id": person_id,
        "display_name": display_name,
        "score_top1": score_top1,
        "score_top2": score_top2,
        "margin": margin,
        "gallery_size": len(ranked),
        "ranked": ranked,
    }


def _write_decision(conn, *, run_id, pack_id, face_id, verdict: dict, threshold: float, source: str) -> str:
    did = uuid.uuid4().hex
    policy = {
        "decision": verdict["decision"],
        "threshold": threshold,
        "gallery_size": verdict["gallery_size"],
        "display_name": verdict["display_name"],
        "source": source,
        "against": "persons",
    }
    conn.execute(
        """INSERT INTO decisions(
             decision_id, kind, face_id, person_id, cluster_id,
             pack_id, score_top1, score_top2, margin, policy_json, run_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            did,
            "identify",
            face_id,
            verdict["person_id"],
            None,
            pack_id,
            verdict["score_top1"],
            verdict["score_top2"],
            verdict["margin"],
            json.dumps(policy, sort_keys=True),
            run_id,
            _now(),
        ),
    )
    return did


def identify_face(
    store: Path,
    run_id: str,
    face_id: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    record: bool = True,
) -> dict:
    """1:N a stored ok face against reviewed persons on this run.

    record=False: score only (search). Opens read-only; does not write a decision.
    """
    conn = _open(store, writable=record)
    try:
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]
        face = conn.execute(
            "SELECT * FROM faces WHERE face_id=? AND run_id=?",
            (face_id, run_id),
        ).fetchone()
        if face is None:
            raise IdentifyError(f"unknown face for run: {face_id}")
        if face["status"] != "ok" or face["embedding"] is None:
            raise IdentifyError(f"face is not identifiable (status={face['status']})")
        if face["embedding_pack"] != pack_id:
            raise IdentifyError("face pack_id does not match run")

        gallery = _gallery(conn, pack_id, exclude_face=face_id)
        ranked = _person_scores(face, gallery, pack_id)
        verdict = _decide(ranked, threshold)
        decision_id = None
        if record:
            decision_id = _write_decision(
                conn,
                run_id=run_id,
                pack_id=pack_id,
                face_id=face_id,
                verdict=verdict,
                threshold=threshold,
                source="face",
            )
            conn.commit()
        return {
            "run_id": run_id,
            "face_id": face_id,
            "decision_id": decision_id,
            "threshold": threshold,
            "recorded": bool(record),
            "note": "identify vs persons; cluster is not a person; person_id not auto-assigned",
            **{k: verdict[k] for k in (
                "decision", "person_id", "display_name",
                "score_top1", "score_top2", "margin", "gallery_size",
            )},
        }
    finally:
        conn.close()


def identify_image(
    store: Path,
    run_id: str,
    image: Path,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """Detect+embed a still and 1:N each ok face vs reviewed persons.

    Probe faces are not written to the store. Identification is a decision,
    not enrolment.
    """
    from semblon.engine import embed_image, load_app
    from semblon.ingest import CLUSTER_MIN_SIDE, DET_SCORE_MIN

    image = Path(image)
    if not image.is_file():
        raise IdentifyError(f"image not found: {image}")

    conn = _open(store)
    try:
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]
        dim = int(run["embedding_dim"])
        gallery = _gallery(conn, pack_id)
        app = load_app()
        faces = embed_image(app, image)
        probes = []
        for f in faces:
            if f["det_score"] < DET_SCORE_MIN:
                probes.append({"status": "rejected", "decision": "UNKNOWN", "reason": "rejected"})
                continue
            if min(f["face_w"], f["face_h"]) < CLUSTER_MIN_SIDE:
                probes.append({"status": "low_quality", "decision": "UNKNOWN", "reason": "low_quality"})
                continue
            vec = f["embedding"]
            blob = vec.astype("float32").tobytes()
            if int(vec.size) != dim:
                probes.append({"status": "ok", "decision": "UNKNOWN", "reason": "dimension mismatch"})
                continue
            probe = {
                "embedding": blob,
                "embedding_dim": dim,
                "embedding_pack": pack_id,
            }
            ranked = _person_scores(probe, gallery, pack_id)
            verdict = _decide(ranked, threshold)
            decision_id = _write_decision(
                conn,
                run_id=run_id,
                pack_id=pack_id,
                face_id=None,
                verdict=verdict,
                threshold=threshold,
                source="image",
            )
            probes.append({
                "status": "ok",
                "bbox": list(f["bbox"]),
                "decision_id": decision_id,
                **{k: verdict[k] for k in (
                    "decision", "person_id", "display_name",
                    "score_top1", "score_top2", "margin", "gallery_size",
                )},
            })
        conn.commit()
        any_accept = any(p.get("decision") == "ACCEPT" for p in probes)
        return {
            "run_id": run_id,
            "image": str(image),
            "faces": len(probes),
            "decision": "ACCEPT" if any_accept else "UNKNOWN",
            "probes": probes,
            "threshold": threshold,
            "note": "identify vs persons; cluster is not a person; person_id not auto-assigned",
        }
    finally:
        conn.close()


def identify_run(
    store: Path,
    run_id: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """1:N every unnamed ok face on this run against the person gallery."""
    conn = _open(store)
    try:
        _require_run(conn, run_id)
        rows = conn.execute(
            """
            SELECT face_id FROM faces
            WHERE run_id=? AND status='ok' AND embedding IS NOT NULL
              AND person_id IS NULL
            ORDER BY face_id
            """,
            (run_id,),
        ).fetchall()
        ids = [r["face_id"] for r in rows]
    finally:
        conn.close()
    results = [
        identify_face(store, run_id, fid, threshold=threshold) for fid in ids
    ]
    n_accept = sum(1 for r in results if r["decision"] == "ACCEPT")
    return {
        "run_id": run_id,
        "faces": len(results),
        "accept": n_accept,
        "unknown": len(results) - n_accept,
        "threshold": threshold,
        "results": results,
        "note": "identify vs persons; cluster is not a person; person_id not auto-assigned",
    }
