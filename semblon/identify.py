"""FACE-004: 1:N identify against reviewed persons. Never against clusters.

Unknown is valid. Wrong identity > unknown. Does not auto-assign person_id.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from semblon.compare import (
    CompareError,
    compare,
    require_finite_threshold,
    validate_identity_embedding,
)
from semblon.eval import DEFAULT_THRESHOLD
from semblon.store import connect, init_db, connect_readonly

# Bumped only when identify evaluation policy shape changes — not the score threshold.
POLICY_VERSION = "identify-eval-v1"


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
    conn = connect_readonly(p.resolve())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _require_run(conn, run_id: str):
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise IdentifyError(f"unknown run: {run_id}")
    return run


def _gallery(conn, pack_id: str, exclude_face: str | None = None):
    """Active persons' ok faces in this pack, across the store. Not clusters.

    Each gallery embedding is contract-validated independently of the probe
    (pack + dim + finite + L2). Rows that fail are dropped before scoring.
    """
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
    rows = conn.execute(sql, args).fetchall()
    out = []
    for g in rows:
        try:
            validate_identity_embedding(
                pack_id, int(g["embedding_dim"]), g["embedding"]
            )
        except CompareError:
            continue
        out.append(g)
    return out


def _person_scores(probe, gallery, pack_id: str) -> list[dict]:
    """Score probe vs pre-validated gallery. compare() re-checks both sides."""
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
    threshold = require_finite_threshold(threshold)
    top1 = ranked[0] if ranked else None
    top2 = ranked[1] if len(ranked) > 1 else None
    score_top1 = None if top1 is None else top1["score"]
    score_top2 = None if top2 is None else top2["score"]
    margin = None
    if score_top1 is not None and score_top2 is not None:
        margin = float(score_top1 - score_top2)

    reason = None
    if top1 is None or score_top1 is None or score_top1 < threshold:
        decision = "UNKNOWN"
        person_id = None
        display_name = None
        reason = "below_threshold" if top1 is not None else "empty_gallery"
    elif top2 is not None and score_top2 is not None and score_top2 >= threshold:
        decision = "UNKNOWN"
        person_id = None
        display_name = None
        reason = "ambiguous"
    else:
        decision = "ACCEPT"
        person_id = top1["person_id"]
        display_name = top1["display_name"]
        reason = "unique_above_threshold"

    out = {
        "decision": decision,
        "person_id": person_id,
        "display_name": display_name,
        "score_top1": score_top1,
        "score_top2": score_top2,
        "margin": margin,
        "gallery_size": len(ranked),
        "reason": reason,
    }
    if include_ranked:
        out["ranked"] = ranked
    return out


def _write_evaluation(
    conn,
    *,
    run_id: str,
    pack_id: str,
    embedding_dim: int,
    probe_face_id: str | None,
    verdict: dict,
    threshold: float,
    source: str,
) -> str:
    """Durable identify outcome. Distinct from decisions.kind human/machine kinds."""
    eid = uuid.uuid4().hex
    conn.execute(
        """INSERT INTO identify_evaluations(
             evaluation_id, probe_face_id, embedding_pack, embedding_dim, run_id,
             outcome, reason, threshold, policy_version, gallery_size,
             score_top1, score_top2, margin, person_id, source, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            eid,
            probe_face_id,
            pack_id,
            int(embedding_dim),
            run_id,
            verdict["decision"],
            verdict.get("reason"),
            float(threshold),
            POLICY_VERSION,
            verdict.get("gallery_size"),
            verdict.get("score_top1"),
            verdict.get("score_top2"),
            verdict.get("margin"),
            verdict.get("person_id"),
            source,
            _now(),
        ),
    )
    return eid


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
    record: bool = True,
) -> dict:
    """1:N a stored ok face against reviewed persons on this run.

    record=False: score only (search). Opens read-only; does not write a decision.
    """
    try:
        threshold = require_finite_threshold(threshold)
    except CompareError as exc:
        raise IdentifyError(str(exc)) from exc
    from semblon.capability_manifest import identity_work_allowed

    allowed, capability = identity_work_allowed()
    if not allowed:
        raise IdentifyError(capability.message or "Face recognition is not available.")
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
        try:
            validate_identity_embedding(
                pack_id, int(face["embedding_dim"]), face["embedding"]
            )
        except CompareError as exc:
            raise IdentifyError(str(exc)) from exc

        gallery = _gallery(conn, pack_id, exclude_face=face_id)
        ranked = _person_scores(face, gallery, pack_id)
        verdict = _decide(ranked, threshold)
        decision_id = None
        evaluation_id = None
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
            evaluation_id = _write_evaluation(
                conn,
                run_id=run_id,
                pack_id=pack_id,
                embedding_dim=int(face["embedding_dim"]),
                probe_face_id=face_id,
                verdict=verdict,
                threshold=threshold,
                source="face",
            )
            conn.commit()
        return {
            "run_id": run_id,
            "face_id": face_id,
            "decision_id": decision_id,
            "evaluation_id": evaluation_id,
            "threshold": threshold,
            "recorded": bool(record),
            "note": "identify vs persons; cluster is not a person; person_id not auto-assigned",
            **{k: verdict[k] for k in (
                "decision", "person_id", "display_name",
                "score_top1", "score_top2", "margin", "gallery_size", "reason",
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
    from semblon.engine import embed_image, identity_space_mismatch, load_app
    from semblon.ingest import CLUSTER_MIN_SIDE, DET_SCORE_MIN

    try:
        threshold = require_finite_threshold(threshold)
    except CompareError as exc:
        raise IdentifyError(str(exc)) from exc
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
        mismatch = identity_space_mismatch(
            pack_id, run["ort_version"], run["runtime_json"]
        )
        if mismatch:
            raise IdentifyError(mismatch)
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
            try:
                validate_identity_embedding(pack_id, dim, blob)
            except CompareError as exc:
                probes.append(
                    {
                        "status": "ok",
                        "decision": "UNKNOWN",
                        "reason": str(exc),
                        "bbox": list(f["bbox"]),
                    }
                )
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
                extra_policy={"bbox": list(f["bbox"])},
            )
            evaluation_id = _write_evaluation(
                conn,
                run_id=run_id,
                pack_id=pack_id,
                embedding_dim=dim,
                probe_face_id=None,
                verdict=verdict,
                threshold=threshold,
                source="image",
            )
            probes.append({
                "status": "ok",
                "bbox": list(f["bbox"]),
                "decision_id": decision_id,
                "evaluation_id": evaluation_id,
                **{k: verdict[k] for k in (
                    "decision", "person_id", "display_name",
                    "score_top1", "score_top2", "margin", "gallery_size", "reason",
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
    try:
        threshold = require_finite_threshold(threshold)
    except CompareError as exc:
        raise IdentifyError(str(exc)) from exc
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
            try:
                validate_identity_embedding(
                    pack_id, int(face["embedding_dim"]), face["embedding"]
                )
            except CompareError as exc:
                verdict = {
                    "decision": "UNKNOWN",
                    "person_id": None,
                    "display_name": None,
                    "score_top1": None,
                    "score_top2": None,
                    "margin": None,
                    "gallery_size": 0,
                    "reason": str(exc),
                }
                decision_id = _write_decision(
                    conn,
                    run_id=run_id,
                    pack_id=pack_id,
                    face_id=face["face_id"],
                    verdict=verdict,
                    threshold=threshold,
                    source="face",
                )
                evaluation_id = _write_evaluation(
                    conn,
                    run_id=run_id,
                    pack_id=pack_id,
                    embedding_dim=int(face["embedding_dim"] or 0),
                    probe_face_id=face["face_id"],
                    verdict=verdict,
                    threshold=threshold,
                    source="face",
                )
                results.append(
                    {
                        "run_id": run_id,
                        "face_id": face["face_id"],
                        "decision_id": decision_id,
                        "evaluation_id": evaluation_id,
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
                                "reason",
                            )
                        },
                    }
                )
                continue
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
            )
            evaluation_id = _write_evaluation(
                conn,
                run_id=run_id,
                pack_id=pack_id,
                embedding_dim=int(face["embedding_dim"]),
                probe_face_id=face["face_id"],
                verdict=verdict,
                threshold=threshold,
                source="face",
            )
            results.append(
                {
                    "run_id": run_id,
                    "face_id": face["face_id"],
                    "decision_id": decision_id,
                    "evaluation_id": evaluation_id,
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
                            "reason",
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
