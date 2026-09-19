"""S6 visual memory — no InsightFace. Time/place must not touch identity."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

from semblon.cli import main
from semblon.compare import compare
from semblon.memory import MemoryError, events, history, together
from semblon.review import name_cluster, name_face, name_faces
from tests.test_review import _clustered
import pytest


def _vec(*xs: float) -> bytes:
    return struct.pack(f"<{len(xs)}f", *xs)


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
    assert h["items"][0]["source_type"] == "folder"
    assert h["items"][0]["frame_id"] is None
    assert h["items"][0]["t_ms"] is None
    assert h["presence"] == []


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


def _prepare_named_video(store: Path):
    """Stills Alice/Bob plus named video faces on one lake clip."""
    _prepare(store)
    conn = sqlite3.connect(str(store))
    conn.execute(
        "INSERT INTO media VALUES ('mv','video',?,?,320,240,?,1)",
        (r"D:\photos\lake\20260509_140700.mp4", "vid1", 1_746_000_056_000_000_000),
    )
    conn.execute("INSERT INTO observations VALUES ('ov1','mv',0,0,'r1')")
    conn.execute("INSERT INTO observations VALUES ('ov2','mv',25,1000,'r1')")
    conn.execute("INSERT INTO observations VALUES ('ov3','mv',50,2000,'r1')")
    for fid, oid, blob in (
        ("fv1", "ov1", _vec(1.0, 0.0)),
        ("fv2", "ov2", _vec(0.707, 0.707)),
        ("fv3", "ov3", _vec(1.0, 0.0)),
    ):
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, oid, "r1", 10, 10, 110, 110, 0.9, 100, 100, "80-119", "ok", blob, "pack-a", 2),
        )
    conn.commit()
    conn.close()
    name_faces(store, "r1", ["fv1", "fv3"], "Alice")
    name_face(store, "r1", "fv2", "Bob")


def test_history_includes_named_video_presence(tmp_path):
    store = tmp_path / "s.sqlite"
    _prepare_named_video(store)
    h = history(store, person="Alice")
    video = [it for it in h["items"] if it["source_type"] == "video"]
    stills = [it for it in h["items"] if it["source_type"] == "folder"]
    assert len(stills) >= 1
    assert {it["face_id"] for it in video} == {"fv1", "fv3"}
    assert {it["t_ms"] for it in video} == {0, 2000}
    assert {it["frame_id"] for it in video} == {0, 50}
    assert all(it["folder"] == "lake" for it in video)
    assert all(it["when_source"] == "filename" for it in video)
    assert any(it["when"] and it["when"].startswith("2026-05-09T14:07:00") for it in video)
    assert any(it["when"] and it["when"].startswith("2026-05-09T14:07:02") for it in video)

    assert len(h["presence"]) == 1
    pr = h["presence"][0]
    assert pr["media_id"] == "mv"
    assert pr["source_type"] == "video"
    assert pr["t_ms_start"] == 0
    assert pr["t_ms_end"] == 2000
    assert pr["frame_id_start"] == 0
    assert pr["frame_id_end"] == 50
    assert pr["sightings"] == 2
    assert pr["folder"] == "lake"


def test_together_and_events_include_named_video(tmp_path):
    store = tmp_path / "s.sqlite"
    _prepare_named_video(store)
    t = together(store)
    video_pairs = [it for it in t["items"] if it["source_type"] == "video"]
    still_pairs = [it for it in t["items"] if it["source_type"] == "folder"]
    assert still_pairs
    assert {it["media_id"] for it in still_pairs} == {"m1"}
    assert len(video_pairs) == 1
    vp = video_pairs[0]
    assert vp["media_id"] == "mv"
    assert set(vp["names"]) == {"Alice", "Bob"}
    assert vp["t_ms_start"] == 0
    assert vp["t_ms_end"] == 2000
    assert vp["folder"] == "lake"

    ev = events(store)
    lake = next(f for f in ev["folders"] if f["folder"] == "lake")
    assert lake["media"] >= 3
    assert lake["people"] >= 2
    assert any(d["day"] == "2026-05-09" for d in ev["days"])
