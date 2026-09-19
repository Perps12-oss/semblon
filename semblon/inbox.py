"""FACE-005 unknown inbox. Read-only. Does not invent schema columns.

Buckets: KNOWN / UNKNOWN / REVIEW_REQUIRED / REJECTED.
Identify decisions are evidence, not enrolment.
"""

from __future__ import annotations

import json
from pathlib import Path

from semblon.eval import DEFAULT_THRESHOLD

BUCKETS = ("KNOWN", "UNKNOWN", "REVIEW_REQUIRED", "REJECTED")


class InboxError(ValueError):
    pass


def _open(store: Path):
    p = Path(store)
    if not p.is_file():
        raise InboxError(f"store not found: {p}")
    import sqlite3

    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _bucket(face, decision_row, threshold: float) -> str:
    status = face["status"]
    if status == "rejected":
        return "REJECTED"
    if status == "low_quality":
        return "REVIEW_REQUIRED"
    if face["person_id"]:
        return "KNOWN"
    if decision_row is None:
        return "UNKNOWN"
    try:
        pol = json.loads(decision_row["policy_json"] or "{}")
    except json.JSONDecodeError:
        pol = {}
    verdict = (pol.get("decision") or "").upper()
    if verdict == "ACCEPT":
        return "KNOWN"
    top1 = decision_row["score_top1"]
    top2 = decision_row["score_top2"]
    if (
        top1 is not None
        and top2 is not None
        and top1 >= threshold
        and top2 >= threshold
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
        run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if run is None:
            raise InboxError(f"unknown run: {run_id}")
        faces = conn.execute(
            """
            SELECT face_id, status, person_id, cluster_id, det_score, face_w, face_h
            FROM faces WHERE run_id=? ORDER BY face_id
            """,
            (run_id,),
        ).fetchall()
        items = []
        counts = {b: 0 for b in BUCKETS}
        for f in faces:
            d = conn.execute(
                """
                SELECT decision_id, person_id, score_top1, score_top2, policy_json, created_at
                FROM decisions
                WHERE face_id=? AND kind='identify'
                ORDER BY created_at DESC, decision_id DESC
                LIMIT 1
                """,
                (f["face_id"],),
            ).fetchone()
            bucket = _bucket(f, d, threshold)
            counts[bucket] += 1
            rec = {
                "face_id": f["face_id"],
                "bucket": bucket,
                "status": f["status"],
                "person_id": f["person_id"],
                "cluster_id": f["cluster_id"],
            }
            if d is not None:
                rec["identify_decision_id"] = d["decision_id"]
                rec["score_top1"] = d["score_top1"]
                rec["score_top2"] = d["score_top2"]
                rec["identified_person_id"] = d["person_id"]
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
