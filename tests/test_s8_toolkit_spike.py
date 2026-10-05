"""S8 toolkit spike — bridge loads review_ui board; mutations via apply_*. No display."""

from __future__ import annotations

import sqlite3
import struct
import sys
from pathlib import Path

import pytest

SPIKE = Path(__file__).resolve().parents[1] / "tools" / "s8_toolkit_spike"
sys.path.insert(0, str(SPIKE))

from windows.backdrop import WindowsBackdropAdapter  # noqa: E402


def _vec(*xs: float) -> bytes:
    return struct.pack(f"<{len(xs)}f", *xs)


def _seed_clustered(path: Path) -> None:
    from semblon.cluster import cluster_run
    from semblon.store import init_db

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t0", "t1", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',100,100,0,1)")
    conn.execute("INSERT INTO media VALUES ('m2','folder','/b.jpg','bbb',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',NULL,NULL,'r1')")
    faces = [
        ("f1", "o1", _vec(1.0, 0.0)),
        ("f2", "o1", _vec(0.99, 0.141)),
        ("f3", "o2", _vec(0.0, 1.0)),
        ("f4", "o2", _vec(0.141, 0.99)),
    ]
    for fid, oid, blob in faces:
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, oid, "r1", 0, 0, 20, 20, 0.9, 20, 20, "80-119", "ok", blob, "pack-a", 2),
        )
    conn.commit()
    conn.close()
    cluster_run(path, "r1", eps=0.15, min_samples=2)


def test_backdrop_without_hwnd_is_solid():
    assert WindowsBackdropAdapter().apply(None) == "solid"
    assert WindowsBackdropAdapter().apply(0) == "solid"


def test_shell_bridge_missing_store(tmp_path):
    pytest.importorskip("PySide6")
    from bridge import ShellBridge

    b = ShellBridge(tmp_path / "missing.sqlite", None)
    assert b.runId == ""
    assert b.items == []
    assert b.message == "no_store"


def test_shell_bridge_loads_board_and_names(tmp_path):
    pytest.importorskip("PySide6")
    from bridge import ShellBridge
    from semblon.review_ui import load_board

    store = tmp_path / "s.sqlite"
    _seed_clustered(store)
    b = ShellBridge(store, "r1")
    assert b.runId == "r1"
    assert b.packId == "pack-a"
    assert b.clusters >= 1
    assert len(b.items) >= 1
    assert b.section == "Review"

    b.selectSection("People")
    assert b.section == "People"
    b.selectSection("Nope")
    assert b.section == "People"
    b.selectSection("Review")

    b.selectItem(0)
    assert b.selectedIndex == 0
    assert b.selectedLabel
    b.nameSelected("Alice")
    board = load_board(store, "r1", strong_min_intra=0.0)
    named = [it for it in board["items"] if it.get("named")]
    assert any("Alice" in (it.get("person_names") or []) for it in named)
    assert "named" in b.message.lower() or "Alice" in b.message


def test_shell_bridge_ignore_and_note(tmp_path):
    pytest.importorskip("PySide6")
    from bridge import ShellBridge

    store = tmp_path / "s.sqlite"
    _seed_clustered(store)
    b = ShellBridge(store, "r1")
    b.selectItem(0)
    b.noteSelected("looks like one person")
    assert "note" in b.message.lower()
    b.selectItem(0)
    b.ignoreSelected()
    assert "ignored" in b.message.lower()
