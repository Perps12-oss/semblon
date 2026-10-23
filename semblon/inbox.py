"""FACE-005 unknown inbox. Read-only. Does not invent schema columns.

Buckets: KNOWN / UNKNOWN / REVIEW_REQUIRED / REJECTED.
Identify decisions are evidence, not enrolment.
Named faces stay KNOWN even when status is low_quality.
"""

from __future__ import annotations

import json
from pathlib import Path

from semblon.eval import DEFAULT_THRESHOLD
from semblon.store import connect_readonly

BUCKETS = ("KNOWN", "UNKNOWN", "REVIEW_REQUIRED", "REJECTED")


class InboxError(ValueError):
    pass


def _open(store: Path):
    p = Path(store)
    if not p.is_file():
        raise InboxError(f"store not found: {p}")
    import sqlite3

    conn = connect_readonly(p.resolve())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _bucket(face, decision_row, threshold: float) -> str:
    status = face["status"]
    if status == "rejected":
        return "REJECTED"
    # Human-named / stamped person wins over quality band.
    if face["person_id"]:
        return "KNOWN"
    if status == "low_quality":
        return "REVIEW_REQUIRED"
    if decision_row is None:
        return "UNKNOWN"
    try:
        pol = json.loads(decision_row["policy_json"] or "{}")
    except json.JSONDecodeError:
        pol = {}
    # Prefer the recorded verdict; do not re-litigate scores with a caller's threshold.
    verdict = (pol.get("decision") or "").upper()
    if verdict == "ACCEPT":
        return "KNOWN"
    if verdict == "UNKNOWN":
        return "UNKNOWN"
    # Legacy / incomplete policy_json: fall back to recorded scores vs recorded threshold.
    th = pol.get("threshold")
    if th is None:
        th = threshold
    try:
        th = float(th)
    except (TypeError, ValueError):
        th = threshold
    top1 = decision_row["score_top1"]
    top2 = decision_row["score_top2"]
    if (
        top1 is not None
        and top2 is not None
        and top1 >= th
        and top2 >= th
    ):
        return "REVIEW_REQUIRED"
    return "UNKNOWN"


def inbox(
    store: Path,
    run_id: str,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """List faces on a run by inbox bucket. Opens the store read-only."""
    conn = _open(store)
    try:
        run = conn.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if run is None:
            raise InboxError(f"unknown run: {run_id}")
        rows = conn.execute(
            """
            SELECT f.face_id, f.status, f.person_id, f.cluster_id, f.det_score, f.face_w, f.face_h,
                   d.decision_id, d.person_id AS identified_person_id,
                   d.score_top1, d.score_top2, d.policy_json, d.created_at
            FROM faces f
            LEFT JOIN decisions d ON d.decision_id = (
                SELECT d2.decision_id FROM decisions d2
                WHERE d2.face_id = f.face_id AND d2.kind = 'identify'
                ORDER BY d2.created_at DESC, d2.decision_id DESC
                LIMIT 1
            )
            WHERE f.run_id = ?
            ORDER BY f.face_id
            """,
            (run_id,),
        ).fetchall()
        items = []
        counts = {b: 0 for b in BUCKETS}
        for r in rows:
            face = {
                "face_id": r["face_id"],
                "status": r["status"],
                "person_id": r["person_id"],
                "cluster_id": r["cluster_id"],
            }
            d = None
            if r["decision_id"] is not None:
                d = {
                    "decision_id": r["decision_id"],
                    "person_id": r["identified_person_id"],
                    "score_top1": r["score_top1"],
                    "score_top2": r["score_top2"],
                    "policy_json": r["policy_json"],
                    "created_at": r["created_at"],
                }
            bucket = _bucket(face, d, threshold)
            counts[bucket] += 1
            rec = {
                "face_id": face["face_id"],
                "bucket": bucket,
                "status": face["status"],
                "person_id": face["person_id"],
                "cluster_id": face["cluster_id"],
                "identify_decision_id": d["decision_id"] if d else None,
                "score_top1": d["score_top1"] if d else None,
                "score_top2": d["score_top2"] if d else None,
                "identified_person_id": d["person_id"] if d else None,
            }
            items.append(rec)
        return {
            "run_id": run_id,
            "threshold": threshold,
            "counts": counts,
            "faces": len(items),
            "items": items,
            "note": "inbox is evidence; KNOWN identify does not stamp person_id",
        }
    finally:
        conn.close()
