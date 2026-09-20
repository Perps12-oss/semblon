"""Read-only stats. Does not write the store."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.observatory import ObservatoryError, snapshot


class StatsError(ValueError):
    pass


def _connect_ro(store: Path) -> sqlite3.Connection:
    p = Path(store).resolve()
    if not p.is_file():
        raise StatsError(f"store not found: {p}")
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def stats(store: Path, run_id: str) -> dict:
    try:
        board = snapshot(store, run_id)
    except ObservatoryError as e:
        raise StatsError(str(e)) from e
    conn = _connect_ro(store)
    try:
        persons = int(
            conn.execute(
                "SELECT COUNT(*) FROM persons WHERE status='active'"
            ).fetchone()[0]
        )
        named = int(
            conn.execute(
                """SELECT COUNT(*) FROM faces
                   WHERE run_id=? AND person_id IS NOT NULL AND status='ok'""",
                (run_id,),
            ).fetchone()[0]
        )
        decisions = int(
            conn.execute(
                "SELECT COUNT(*) FROM decisions WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        )
        by_kind = {
            r["kind"]: r["n"]
            for r in conn.execute(
                """SELECT kind, COUNT(*) AS n FROM decisions
                   WHERE run_id=? GROUP BY kind ORDER BY kind""",
                (run_id,),
            )
        }
    finally:
        conn.close()
    acc = board.get("accuracy") or {}
    return {
        "run_id": run_id,
        "pack_id": board.get("pack_id"),
        "arch": board.get("arch"),
        "execution": board.get("execution"),
        "detection": board.get("detection"),
        "clustering": board.get("clustering"),
        "effort": board.get("effort"),
        "speed": board.get("speed"),
        "persons_active": persons,
        "faces_named": named,
        "decisions": decisions,
        "decisions_by_kind": by_kind,
        "accuracy": {
            "status": acc.get("status"),
            "reason": acc.get("reason"),
            "far": acc.get("far") if acc.get("status") == "measurable" else None,
            "frr": acc.get("frr") if acc.get("status") == "measurable" else None,
        },
        "note": "stats is read-only; FAR/FRR only when confirmatory is measurable",
    }
