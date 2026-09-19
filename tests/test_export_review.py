"""S8 Reviewability — static review.html video thumbs. No InsightFace."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path
from unittest.mock import patch

import pytest

from semblon.export import _crop_jpeg, export_review
from semblon.store import init_db


def _vec(*xs: float) -> bytes:
    return struct.pack(f"<{len(xs)}f", *xs)


def _seed_video(store: Path, *, frame_id: int | None = 1300) -> None:
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("rv", "t0", "t1", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute(
        "INSERT INTO media VALUES ('mv','video','C:/clips/a.mp4','vvv',1920,1080,0,1)"
    )
    conn.execute("INSERT INTO observations VALUES ('ov','mv',?,?, 'rv')", (frame_id, 64973))
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "fv",
            "ov",
            "rv",
            10,
            20,
            110,
            120,
            0.9,
            100,
            100,
            "80-119",
            "ok",
            _vec(1.0, 0.0),
            "pack-a",
            2,
        ),
    )
    conn.commit()
    conn.close()


def test_export_html_video_thumb_seeks_instead_of_imread(tmp_path):
    np = pytest.importorskip("numpy")
    store = tmp_path / "s.sqlite"
    _seed_video(store)
    out = tmp_path / "review.html"
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[20:120, 10:110] = 200
    with patch("semblon.temporal.read_bgr", return_value=frame) as rb:
        rec = export_review(store, "rv", out)
    assert rec["faces"] == 1
    html = out.read_text(encoding="utf-8")
    assert "data:image/jpeg;base64," in html
    assert 'class="missing"' not in html
    assert "video frame=1300 t_ms=64973" in html
    assert "held out of clustering" in html
    assert "video a.mp4" in html
    assert "not a person" in html
    rb.assert_called_once_with("C:/clips/a.mp4", 1300)


def test_export_html_video_without_frame_id_is_missing(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_video(store, frame_id=None)
    out = tmp_path / "review.html"
    with patch("semblon.temporal.read_bgr") as rb:
        export_review(store, "rv", out)
    html = out.read_text(encoding="utf-8")
    assert "data:image/jpeg;base64," not in html
    assert "fv" in html
    rb.assert_not_called()


def test_crop_jpeg_video_without_frame_id_returns_none():
    assert (
        _crop_jpeg("C:/clips/a.mp4", (0, 0, 10, 10), 96, source_type="video") is None
    )


def test_crop_jpeg_still_uses_read_bgr_without_frame():
    np = pytest.importorskip("numpy")
    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    frame[0:20, 0:20] = 180
    with patch("semblon.temporal.read_bgr", return_value=frame) as rb:
        uri = _crop_jpeg("/a.jpg", (0, 0, 20, 20), 96, source_type="folder")
    assert uri is not None
    assert uri.startswith("data:image/jpeg;base64,")
    rb.assert_called_once_with("/a.jpg", None)
