"""Item 01 — integrity_report counts media with zero observations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.store import init_db, integrity_report


def _init(store: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def test_integrity_reports_media_missing_observations(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _init(store)
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',10,10,0,1)")
    conn.commit()
    conn.close()

    rec = integrity_report(store)
    assert "media_missing_observations" in rec
    assert rec["media_missing_observations"] == 1
    assert rec["media"] == 1
    # Measurement only: same policy as media_missing_path.
    assert rec["ok"] is True
    assert "media_missing_observations" in rec["note"]


def test_integrity_zero_when_observation_exists(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _init(store)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',10,10,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.commit()
    conn.close()

    rec = integrity_report(store)
    assert rec["media_missing_observations"] == 0
    assert rec["ok"] is True
