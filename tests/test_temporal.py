"""S7a sampling + video ingest. No InsightFace."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.cluster import cluster_run
from semblon.ingest import ingest
from semblon.temporal import (
    DEFAULT_SAMPLE_HZ,
    VideoError,
    discover_videos,
    frame_t_ms,
    read_bgr,
    sample_frame_indices,
)


def test_sample_frame_indices_is_not_every_native_frame():
    # 25 fps, 3s, 1 Hz → 3 samples, not 75
    idx = sample_frame_indices(75, 25.0, 1.0)
    assert idx == [0, 25, 50]
    assert len(idx) < 75
    # 30 fps, 3s
    assert sample_frame_indices(90, 30.0, 1.0) == [0, 30, 60]
    assert sample_frame_indices(0, 25.0) == []
    with pytest.raises(VideoError):
        sample_frame_indices(10, 25.0, 0.0)


def test_frame_t_ms_matches_index_over_fps():
    assert frame_t_ms(0, 25.0) == 0
    assert frame_t_ms(25, 25.0) == 1000
    assert frame_t_ms(0, 0.0) == 0


def test_read_bgr_still_uses_imread(tmp_path):
    img_path = tmp_path / "a.jpg"
    img_path.write_bytes(b"not-a-real-jpeg")
    with patch("semblon.temporal.cv2.imread", return_value=np.zeros((10, 10, 3), dtype=np.uint8)) as im:
        out = read_bgr(img_path, None)
    assert out is not None
    assert out.shape == (10, 10, 3)
    im.assert_called_once_with(str(img_path))


def test_read_bgr_video_seeks_frame():
    fake = np.ones((20, 20, 3), dtype=np.uint8) * 7

    class Cap:
        def __init__(self, *_a, **_k):
            self.pos = None

        def isOpened(self):
            return True

        def set(self, _prop, value):
            self.pos = value
            return True

        def read(self):
            assert self.pos == 42.0
            return True, fake

        def release(self):
            pass

    with patch("semblon.temporal.cv2.VideoCapture", return_value=Cap()):
        out = read_bgr("clip.mp4", 42)
    assert out is not None
    assert int(out[0, 0, 0]) == 7


def test_discover_videos_ignores_stills(tmp_path):
    folder = tmp_path / "lib"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"x")
    (folder / "clip.mp4").write_bytes(b"v")
    (folder / "notes.txt").write_text("no")
    found = discover_videos(folder)
    assert [p.name for p in found] == ["clip.mp4"]


def _fake_face(vec):
    return {
        "bbox": (0.0, 0.0, 100.0, 100.0),
        "det_score": 0.9,
        "face_w": 100,
        "face_h": 100,
        "dim": 4,
        "embedding": vec,
    }


def test_ingest_video_uses_sampled_observations(tmp_path):
    folder = tmp_path / "mix"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"still")
    (folder / "clip.mp4").write_bytes(b"video-bytes")
    store = tmp_path / "store.sqlite"
    vec = np.zeros(4, dtype=np.float32)
    sampled = [
        (0, 0, np.zeros((80, 80, 3), dtype=np.uint8)),
        (25, 1000, np.zeros((80, 80, 3), dtype=np.uint8)),
        (50, 2000, np.zeros((80, 80, 3), dtype=np.uint8)),
    ]
    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()

    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest.embed_image", return_value=[_fake_face(vec)]),
        patch("semblon.ingest.embed_bgr", return_value=[_fake_face(vec)]),
        patch("semblon.ingest.cv2.imread", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch("semblon.ingest.iter_sampled_frames", return_value=sampled),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        rec = ingest(folder, store)

    assert rec["stills"] == 1
    assert rec["videos"] == 1
    assert rec["video_frames"] == 3
    assert rec["files"] == 2
    assert rec["new_media"] == 2

    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    types = {
        r["path"].split("\\")[-1].split("/")[-1]: r["source_type"]
        for r in conn.execute("SELECT path, source_type FROM media")
    }
    assert types["a.jpg"] == "folder"
    assert types["clip.mp4"] == "video"
    video_obs = conn.execute(
        """SELECT o.frame_id, o.t_ms FROM observations o
           JOIN media m ON m.media_id = o.media_id
           WHERE m.source_type='video' ORDER BY o.frame_id"""
    ).fetchall()
    assert [(r["frame_id"], r["t_ms"]) for r in video_obs] == [(0, 0), (25, 1000), (50, 2000)]
    still_obs = conn.execute(
        """SELECT o.frame_id FROM observations o
           JOIN media m ON m.media_id = o.media_id
           WHERE m.source_type='folder'"""
    ).fetchall()
    assert still_obs[0]["frame_id"] is None
    conn.close()


def test_ingest_skips_seen_video_hash(tmp_path):
    folder = tmp_path / "lib"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"same-video")
    store = tmp_path / "store.sqlite"
    vec = np.zeros(4, dtype=np.float32)
    sampled = [(0, 0, np.zeros((80, 80, 3), dtype=np.uint8))]
    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest.embed_bgr", return_value=[_fake_face(vec)]),
        patch("semblon.ingest.iter_sampled_frames", return_value=sampled),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        first = ingest(folder, store)
        second = ingest(folder, store)
    assert first["videos"] == 1
    assert first["new_media"] == 1
    assert second["skipped_seen"] == 1
    assert second["new_media"] == 0


def test_cluster_holds_out_video_faces(tmp_path):
    from semblon.store import init_db
    import struct

    store = tmp_path / "s.sqlite"
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',100,100,0,1)")
    conn.execute("INSERT INTO media VALUES ('m2','video','/c.mp4','vvv',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',0,0,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o3','m2',25,1000,'r1')")

    def vec(x, y):
        return struct.pack("<2f", x, y)

    for fid, oid, blob in (
        ("f1", "o1", vec(1.0, 0.0)),
        ("f2", "o1", vec(0.99, 0.141)),
        ("v1", "o2", vec(1.0, 0.0)),
        ("v2", "o3", vec(0.99, 0.141)),
    ):
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, oid, "r1", 0, 0, 20, 20, 0.9, 20, 20, "80-119", "ok", blob, "pack-a", 2),
        )
    conn.commit()
    conn.close()

    rec = cluster_run(store, "r1", eps=0.15, min_samples=2)
    assert rec["clustered"] == 2
    assert rec["unassigned"] == 0
    conn = sqlite3.connect(str(store))
    video_assigned = conn.execute(
        "SELECT cluster_id FROM faces WHERE face_id IN ('v1','v2')"
    ).fetchall()
    assert all(r[0] is None for r in video_assigned)
    still = conn.execute("SELECT cluster_id FROM faces WHERE face_id='f1'").fetchone()[0]
    assert still is not None
    conn.close()


def test_default_sample_hz_frozen():
    assert DEFAULT_SAMPLE_HZ == 1.0
