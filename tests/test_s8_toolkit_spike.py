"""S8 toolkit spike — no FaceKit, no GUI display required for these tests."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

SPIKE = Path(__file__).resolve().parents[1] / "tools" / "s8_toolkit_spike"
sys.path.insert(0, str(SPIKE))

from windows.backdrop import WindowsBackdropAdapter  # noqa: E402


def test_backdrop_without_hwnd_is_solid():
    assert WindowsBackdropAdapter().apply(None) == "solid"
    assert WindowsBackdropAdapter().apply(0) == "solid"


def test_spike_snapshot_missing_store(tmp_path):
    pytest.importorskip("PySide6")
    from bridge import load_spike_snapshot

    rec = load_spike_snapshot(tmp_path / "missing.sqlite", None)
    assert rec["status"] == "no-store"
    assert rec["run_id"] == ""
    assert rec["images"] == []


def test_spike_snapshot_reads_run_counts(tmp_path):
    pytest.importorskip("PySide6")
    from bridge import load_spike_snapshot
    from semblon.store import init_db

    store = tmp_path / "s.sqlite"
    conn = sqlite3.connect(str(store))
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r-spike", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/nope.jpg','aaa',10,10,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r-spike')")
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("f1", "o1", "r-spike", 0, 0, 20, 20, 0.9, 20, 20, "80-119", "ok"),
    )
    conn.commit()
    conn.close()
    rec = load_spike_snapshot(store, "r-spike")
    assert rec["status"] == "ready"
    assert rec["run_id"] == "r-spike"
    assert rec["ok"] == 1
    assert rec["unassigned"] == 1
    assert rec["clusters"] == 0
    assert rec["images"] == []


def test_shell_bridge_selects_section():
    pytest.importorskip("PySide6")
    from bridge import ShellBridge

    b = ShellBridge({"run_id": "r1", "clusters": 2, "unassigned": 3, "ok": 5, "persons": 1, "images": []})
    assert b.runId == "r1"
    assert b.section == "Review"
    b.selectSection("People")
    assert b.section == "People"
    b.selectSection("Nope")
    assert b.section == "People"
