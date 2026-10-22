"""Home FTUE completion persistence via existing schema_meta.

Uses the store's schema_meta key/value table — no new DDL, no ftue_state.json.
Presentation only: which completion summary to show on next launch.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from semblon.store import connect_readonly

_META_KIND = "home_completion_kind"
_META_JSON = "home_completion_json"
_META_ACK = "home_completion_ack_run"


def _connect(store: Path) -> sqlite3.Connection | None:
    p = Path(store)
    if not p.is_file():
        return None
    conn = sqlite3.connect(str(p.resolve()))
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_meta (
             key   TEXT PRIMARY KEY,
             value TEXT NOT NULL
           )"""
    )
    return conn


def _get(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key=?", (key,)
    ).fetchone()
    if row is None:
        return None
    return str(row[0])


def _set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
        (key, value),
    )


def save_unseen_completion(
    store: Path,
    *,
    kind: str,
    payload: dict[str, Any],
) -> None:
    """Persist a completion summary the user has not yet acknowledged."""
    conn = _connect(store)
    if conn is None:
        return
    try:
        _set(conn, _META_KIND, kind)
        _set(conn, _META_JSON, json.dumps(payload, separators=(",", ":")))
        # Clearing ack for this run so restart re-shows the card.
        run_id = payload.get("run_id")
        if run_id:
            ack = _get(conn, _META_ACK)
            if ack == str(run_id):
                conn.execute("DELETE FROM schema_meta WHERE key=?", (_META_ACK,))
        conn.commit()
    finally:
        conn.close()


def load_unseen_completion(store: Path) -> dict[str, Any] | None:
    """Return {kind, payload} if a completion is waiting; else None."""
    conn = _connect(store)
    if conn is None:
        return None
    try:
        kind = _get(conn, _META_KIND)
        raw = _get(conn, _META_JSON)
        if not kind or not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        run_id = payload.get("run_id")
        if run_id and _get(conn, _META_ACK) == str(run_id):
            return None
        return {"kind": kind, "payload": payload}
    finally:
        conn.close()


def acknowledge_completion(store: Path, run_id: str | None = None) -> None:
    """Mark completion as seen so next launch goes to Library."""
    conn = _connect(store)
    if conn is None:
        return
    try:
        if run_id:
            _set(conn, _META_ACK, str(run_id))
        conn.execute("DELETE FROM schema_meta WHERE key=?", (_META_KIND,))
        conn.execute("DELETE FROM schema_meta WHERE key=?", (_META_JSON,))
        conn.commit()
    finally:
        conn.close()


def clear_completion(store: Path) -> None:
    """Drop unseen completion (new ingest starting)."""
    conn = _connect(store)
    if conn is None:
        return
    try:
        conn.execute("DELETE FROM schema_meta WHERE key=?", (_META_KIND,))
        conn.execute("DELETE FROM schema_meta WHERE key=?", (_META_JSON,))
        conn.commit()
    finally:
        conn.close()


def latest_unfinished_run_info(store: Path) -> dict[str, Any] | None:
    """{run_id, folder?} for a leftover unfinished run (restart-during-ingest)."""
    p = Path(store)
    if not p.is_file():
        return None
    conn = connect_readonly(p.resolve())
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        row = conn.execute(
            """SELECT run_id, config_json FROM runs
               WHERE finished_at IS NULL
               ORDER BY started_at DESC, run_id DESC
               LIMIT 1"""
        ).fetchone()
        if row is None:
            return None
        folder = None
        try:
            cfg = json.loads(row["config_json"] or "{}")
        except json.JSONDecodeError:
            cfg = {}
        if isinstance(cfg, dict):
            raw = cfg.get("folder")
            if raw:
                folder = str(raw)
        return {"run_id": str(row["run_id"]), "folder": folder}
    except sqlite3.DatabaseError:
        return None
    finally:
        conn.close()
