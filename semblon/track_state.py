"""Track-state semantics for temporal UX.

A track is a temporal hypothesis, not a person. Identity remains a separate
decision layer (identify/name/review). This module maps tracks to user-facing
state labels without collapsing track == person.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class TrackStateError(ValueError):
    pass


def _open_ro(store: Path) -> sqlite3.Connection:
    p = Path(store)
    if not p.is_file():
        raise TrackStateError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _state_label(rec: dict) -> str:
    state = rec.get("state")
    if state == "identified":
        name = rec.get("display_name") or rec.get("person_id") or "identified"
        return f"{name} ✓ identified"
    if state == "unknown":
        return "UNKNOWN ? unresolved"
    short_id = str(rec.get("track_id") or "")[:8]
    return f"Track {short_id} ○ hypothesis"


def _decisions_by_face(conn, run_id: str) -> dict[str, list[sqlite3.Row]]:
    rows = conn.execute(
        """
        WITH latest_identify AS (
            SELECT
              d.face_id,
              d.decision_id,
              d.person_id,
              d.score_top1,
              d.score_top2,
              d.margin,
              d.created_at,
              ROW_NUMBER() OVER (
                PARTITION BY d.face_id
                ORDER BY d.created_at DESC, d.decision_id DESC
              ) AS rn
            FROM decisions d
            WHERE d.kind='identify' AND d.run_id=?
        )
        SELECT * FROM latest_identify WHERE rn=1
        """,
        (run_id,),
    ).fetchall()
    by_face: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        by_face.setdefault(str(r["face_id"]), []).append(r)
    return by_face


def _person_name_map(conn) -> dict[str, str]:
    rows = conn.execute(
        "SELECT person_id, display_name FROM persons WHERE status='active'"
    ).fetchall()
    return {str(r["person_id"]): str(r["display_name"] or "") for r in rows}


def _track_rows(conn, run_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
          t.track_id, t.media_id, t.t_ms_start, t.t_ms_end, t.item_count, t.kind, t.status,
          m.path, m.source_type
        FROM tracks t
        JOIN media m ON m.media_id = t.media_id
        WHERE t.run_id=?
        ORDER BY m.path, COALESCE(t.t_ms_start, -1), t.track_id
        """,
        (run_id,),
    ).fetchall()


def _member_rows(conn, track_ids: list[str]) -> list[sqlite3.Row]:
    if not track_ids:
        return []
    marks = ",".join(["?"] * len(track_ids))
    return conn.execute(
        f"""
        SELECT
          tm.track_id, tm.item_id, tm.t_ms,
          oi.face_id, oi.observation_id,
          f.person_id
        FROM track_members tm
        JOIN observation_items oi ON oi.item_id = tm.item_id
        LEFT JOIN faces f ON f.face_id = oi.face_id
        WHERE tm.track_id IN ({marks})
        ORDER BY tm.track_id, COALESCE(tm.t_ms, -1), tm.item_id
        """,
        track_ids,
    ).fetchall()


def derive_track_states_from_conn(conn, run_id: str) -> dict:
    run = conn.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise TrackStateError(f"unknown run: {run_id}")

    tracks = _track_rows(conn, run_id)
    track_ids = [str(t["track_id"]) for t in tracks]
    members = _member_rows(conn, track_ids)
    people = _person_name_map(conn)
    latest_decision = _decisions_by_face(conn, run_id)

    by_track: dict[str, dict] = {}
    for t in tracks:
        tid = str(t["track_id"])
        by_track[tid] = {
            "track_id": tid,
            "media_id": t["media_id"],
            "path": t["path"],
            "source_type": t["source_type"],
            "t_ms_start": t["t_ms_start"],
            "t_ms_end": t["t_ms_end"],
            "item_count": int(t["item_count"] or 0),
            "kind": t["kind"],
            "status": t["status"],
            "state": "hypothesis",
            "person_id": None,
            "display_name": None,
            "decision_id": None,
            "score_top1": None,
            "score_top2": None,
            "margin": None,
            "faces": 0,
            "identify_total": 0,
            "identify_accept": 0,
            "identify_unknown": 0,
            "note": "track is temporal hypothesis; identity is separate",
        }

    # Track-level evidence from members.
    for m in members:
        tid = str(m["track_id"])
        rec = by_track.get(tid)
        if rec is None:
            continue
        face_id = m["face_id"]
        if face_id:
            rec["faces"] += 1
            rows = latest_decision.get(str(face_id)) or []
            for d in rows:
                rec["identify_total"] += 1
                if d["person_id"]:
                    rec["identify_accept"] += 1
                    better = (
                        rec["score_top1"] is None
                        or d["score_top1"] is None
                        or float(d["score_top1"]) > float(rec["score_top1"])
                    )
                    if better:
                        pid = str(d["person_id"])
                        rec["state"] = "identified"
                        rec["person_id"] = pid
                        rec["display_name"] = people.get(pid) or pid
                        rec["decision_id"] = d["decision_id"]
                        rec["score_top1"] = d["score_top1"]
                        rec["score_top2"] = d["score_top2"]
                        rec["margin"] = d["margin"]
                else:
                    rec["identify_unknown"] += 1
            # Manual assignment evidence (name/name_track path).
            if rec["state"] != "identified" and m["person_id"]:
                pid = str(m["person_id"])
                rec["state"] = "identified"
                rec["person_id"] = pid
                rec["display_name"] = people.get(pid) or pid

    # Any track with identify evidence but no accepted/assigned identity is unknown.
    for rec in by_track.values():
        if rec["state"] == "identified":
            rec["label"] = _state_label(rec)
            continue
        if rec["identify_total"] > 0 or rec["identify_unknown"] > 0:
            rec["state"] = "unknown"
        else:
            rec["state"] = "hypothesis"
        rec["label"] = _state_label(rec)

    items = list(by_track.values())
    items.sort(key=lambda r: (str(r.get("path") or ""), str(r.get("track_id") or "")))
    counts = {
        "total": len(items),
        "identified": sum(1 for r in items if r["state"] == "identified"),
        "unknown": sum(1 for r in items if r["state"] == "unknown"),
        "hypothesis": sum(1 for r in items if r["state"] == "hypothesis"),
    }
    return {
        "run_id": run_id,
        "tracks": items,
        "counts": counts,
        "note": "track states are UX summaries; track != person remains enforced",
    }


def derive_track_states(store: Path, run_id: str) -> dict:
    conn = _open_ro(store)
    try:
        return derive_track_states_from_conn(conn, run_id)
    finally:
        conn.close()
