"""S7b derived tracks. No InsightFace. Embeddings must not vote."""

from __future__ import annotations

import io
import sqlite3
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from semblon.cli import main
from semblon.store import init_db
from semblon.tracks import TracksError, bbox_iou, derive_tracks


def _vec(*xs: float) -> bytes:
    return struct.pack(f"<{len(xs)}f", *xs)


def _seed(store: Path) -> None:
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("rt", "t0", "t1", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('mv1','video','C:/clips/a.mp4','v1',320,240,0,1)")
    conn.execute("INSERT INTO media VALUES ('mv2','video','C:/clips/b.mp4','v2',320,240,0,1)")
    conn.execute("INSERT INTO media VALUES ('ms','folder','C:/stills/a.jpg','s1',100,100,0,1)")
    # Unique (media_id, frame_id, run_id)
    conn.execute("INSERT INTO observations VALUES ('o1','mv1',0,0,'rt')")
    conn.execute("INSERT INTO observations VALUES ('o2','mv1',25,1000,'rt')")
    conn.execute("INSERT INTO observations VALUES ('o3','mv1',50,2000,'rt')")
    conn.execute("INSERT INTO observations VALUES ('o4','mv1',150,6000,'rt')")
    conn.execute("INSERT INTO observations VALUES ('o6','mv2',0,0,'rt')")
    conn.execute("INSERT INTO observations VALUES ('o7','mv2',25,1000,'rt')")
    conn.execute("INSERT INTO observations VALUES ('os','ms',NULL,NULL,'rt')")

    def face(fid, oid, bbox, blob):
        x1, y1, x2, y2 = bbox
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, oid, "rt", x1, y1, x2, y2, 0.9, x2 - x1, y2 - y1, "80-119", "ok", blob, "pack-a", 2),
        )

    # Track 1: overlapping boxes, opposite embeddings (firewall).
    face("fa", "o1", (10, 10, 110, 110), _vec(1.0, 0.0))
    face("fb", "o2", (12, 12, 112, 112), _vec(0.0, 1.0))
    # Same frame as fa, other side — exclusive, stays untracked.
    face("fx", "o1", (200, 10, 300, 110), _vec(0.5, 0.5))
    # No overlap with fa/fb → untracked.
    face("fc", "o3", (200, 10, 300, 110), _vec(1.0, 0.0))
    # Overlaps fc's box but 4000ms later → fragment stays separate.
    face("fd", "o4", (200, 10, 300, 110), _vec(1.0, 0.0))
    # Second video: own track, never joined to mv1.
    face("fe", "o6", (0, 0, 80, 80), _vec(0.7, 0.7))
    face("ff", "o7", (2, 2, 82, 82), _vec(0.7, 0.7))
    face("fs", "os", (0, 0, 20, 20), _vec(1.0, 0.0))
    conn.commit()
    conn.close()


def test_bbox_iou_overlap_and_miss():
    assert bbox_iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert bbox_iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert bbox_iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(1 / 3)


def test_derive_tracks_iou_time_not_embeddings(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store)
    rec = derive_tracks(store, "rt")
    groups = {tuple(t["face_ids"]): t for t in rec["tracks"]}
    assert ("fa", "fb") in groups
    assert ("fx", "fc") in groups
    assert ("fe", "ff") in groups
    assert groups[("fa", "fb")]["media_id"] == "mv1"
    assert groups[("fe", "ff")]["media_id"] == "mv2"
    assert groups[("fa", "fb")]["t_ms_end"] == 1000
    un_ids = {u["face_id"] for u in rec["untracked"]}
    assert un_ids == {"fd"}
    assert rec["counts"]["tracks"] == 3
    assert rec["counts"]["tracked_faces"] == 6
    assert rec["counts"]["untracked"] == 1
    assert rec["counts"]["video_ok_faces"] == 7
    assert rec["note"].startswith("derived S7b")
    tracked_ids = {fid for t in rec["tracks"] for fid in t["face_ids"]}
    assert "fs" not in tracked_ids
    assert "fs" not in {u["face_id"] for u in rec["untracked"]}


def test_gap_keeps_fragments_separate(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store)
    rec = derive_tracks(store, "rt", max_t_ms_gap=2500)
    un_ids = {u["face_id"] for u in rec["untracked"]}
    assert "fd" in un_ids
    right = next(t for t in rec["tracks"] if t["face_ids"] == ["fx", "fc"])
    assert right["t_ms_end"] == 2000
    assert "fd" not in right["face_ids"]


def test_same_frame_exclusive(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store)
    rec = derive_tracks(store, "rt")
    for t in rec["tracks"]:
        tms = [m["t_ms"] for m in t["members"]]
        assert len(tms) == len(set(tms))
    left = next(t for t in rec["tracks"] if t["face_ids"] == ["fa", "fb"])
    assert "fx" not in left["face_ids"]


def test_does_not_write_store(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store)
    before = store.stat().st_mtime_ns
    derive_tracks(store, "rt")
    conn = sqlite3.connect(str(store))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert "tracks" not in tables
    assert store.stat().st_mtime_ns == before


def test_unknown_run(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store)
    with pytest.raises(TracksError, match="unknown run"):
        derive_tracks(store, "nope")


def test_cli_tracks_json(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store)
    buf = io.StringIO()
    with patch("sys.stdout", buf):
        code = main(["tracks", "--run", "rt", "--store", str(store)])
    assert code == 0
    out = buf.getvalue()
    assert "derived S7b" in out
    assert "fa" in out
    assert '"tracks"' in out
