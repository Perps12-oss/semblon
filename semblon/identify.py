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


def _open(store: Path):
    conn = connect(Path(store))
    init_db(conn)
    return conn


def _require_run(conn, run_id: str):
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise IdentifyError(f"unknown run: {run_id}")
    return run


def _gallery(conn, pack_id: str, exclude_face: str | None = None):
    """Active persons' ok faces in this pack, across the store. Not clusters."""
    sql = """
        SELECT f.face_id, f.embedding, f.embedding_pack, f.embedding_dim,
               f.person_id, p.display_name
        FROM faces f
        JOIN persons p ON p.person_id = f.person_id
        WHERE f.status='ok' AND f.embedding IS NOT NULL
          AND p.status='active' AND f.person_id IS NOT NULL
          AND f.embedding_pack=?
    """
    args: list = [pack_id]
    if exclude_face:
        sql += " AND f.face_id != ?"
        args.append(exclude_face)
    sql += " ORDER BY f.face_id"
    return conn.execute(sql, args).fetchall()


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


def _decide(ranked: list[dict], threshold: float, *, include_ranked: bool = False) -> dict:
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

    out = {
        "decision": decision,
        "person_id": person_id,
        "display_name": display_name,
        "score_top1": score_top1,
        "score_top2": score_top2,
        "margin": margin,
        "gallery_size": len(ranked),
    }
    if include_ranked:
        out["ranked"] = ranked
    return out


def _write_decision(
    conn,
    *,
    run_id,
    pack_id,
    face_id,
    verdict: dict,
    threshold: float,
    source: str,
    cluster_id=None,
    extra_policy: dict | None = None,
) -> str:
    did = uuid.uuid4().hex
    policy = {
        "decision": verdict["decision"],
        "threshold": threshold,
        "gallery_size": verdict["gallery_size"],
        "display_name": verdict["display_name"],
        "source": source,
        "against": "persons",
    }
    if extra_policy:
        policy.update(extra_policy)
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
            cluster_id,
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
) -> dict:
    """1:N a stored ok face against active reviewed persons (same pack)."""
    conn = _open(store)
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
    app=None,
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
        if app is None:
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
                extra_policy={"image": str(image), "bbox": list(f["bbox"])},
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
        run = _require_run(conn, run_id)
        pack_id = run["pack_id"]
        gallery = _gallery(conn, pack_id)
        rows = conn.execute(
            """
            SELECT * FROM faces
            WHERE run_id=? AND status='ok' AND embedding IS NOT NULL
              AND person_id IS NULL
            ORDER BY face_id
            """,
            (run_id,),
        ).fetchall()
        results = []
        for face in rows:
            ranked = _person_scores(face, gallery, pack_id)
            verdict = _decide(ranked, threshold)
            decision_id = _write_decision(
                conn,
                run_id=run_id,
                pack_id=pack_id,
                face_id=face["face_id"],
                verdict=verdict,
                threshold=threshold,
                source="face",
                cluster_id=face["cluster_id"],
            )
            results.append(
                {
                    "run_id": run_id,
                    "face_id": face["face_id"],
                    "decision_id": decision_id,
                    "threshold": threshold,
                    "note": "identify vs persons; cluster is not a person; person_id not auto-assigned",
                    **{
                        k: verdict[k]
                        for k in (
                            "decision",
                            "person_id",
                            "display_name",
                            "score_top1",
                            "score_top2",
                            "margin",
                            "gallery_size",
                        )
                    },
                }
            )
        conn.commit()
    finally:
        conn.close()
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
