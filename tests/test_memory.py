"""S6 visual memory — no InsightFace. Time/place must not touch identity."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.cli import main
from semblon.compare import compare
from semblon.memory import MemoryError, events, history, together
from semblon.review import name_cluster, name_face
from tests.test_review import _clustered
import pytest


def _conn(store: Path):
    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    return conn


def _prepare(store: Path):
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_cluster(store, "r1", assigned["f3"], "Alice")
    name_face(store, "r1", "f5", "Bob")
    conn = sqlite3.connect(str(store))
    conn.execute(
        "UPDATE media SET path=?, mtime_ns=? WHERE media_id='m1'",
        (r"D:\photos\lake\20260509_140604.jpg", 1_746_000_000_000_000_000),
    )
    conn.execute(
        "UPDATE media SET path=?, mtime_ns=? WHERE media_id='m2'",
        (r"D:\photos\lake\20260509_140630.jpg", 1_746_000_026_000_000_000),
    )
    conn.commit()
    conn.close()
    return assigned


def test_history_together_events(tmp_path):
    store = tmp_path / "s.sqlite"
    _prepare(store)
    h = history(store, person="Alice")
    assert h["display_name"] == "Alice"
    assert h["sightings"] >= 1
    assert h["items"][0]["when_source"] == "filename"
    assert h["items"][0]["folder"] == "lake"
    assert "not identity" in h["note"]

    t = together(store)
    assert t["pairs"] >= 1
    names = set(t["items"][0]["names"])
    assert names == {"Alice", "Bob"}

    ev = events(store)
    assert any(b["kind"] == "burst" and b["folder"] == "lake" for b in ev["bursts"])
    assert any(d["day"] == "2026-05-09" for d in ev["days"])
    assert any(f["folder"] == "lake" for f in ev["folders"])


def test_memory_does_not_change_compare(tmp_path):
    """S6 must not alter pack_id compare."""
    a = bytes.fromhex("0000803f00000000")  # 1,0
    b = bytes.fromhex("000000000000803f")  # 0,1
    s = compare("pack-a", 2, a, "pack-a", 2, b)
    store = tmp_path / "s.sqlite"
    _prepare(store)
    history(store, person="Alice")
    s2 = compare("pack-a", 2, a, "pack-a", 2, b)
    assert s == s2


def test_cli_memory(tmp_path):
    store = tmp_path / "s.sqlite"
    _prepare(store)
    assert main(["memory", "history", "--person", "Alice", "--store", str(store)]) == 0
    assert main(["memory", "together", "--store", str(store)]) == 0
    assert main(["memory", "events", "--store", str(store)]) == 0
    assert main(["memory", "history", "--person", "nobody", "--store", str(store)]) == 2
    with pytest.raises(MemoryError):
        history(store, person="nobody")
