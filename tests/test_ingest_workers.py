"""Bounded ingest workers — hash parallelism + skip-before-embed."""

from __future__ import annotations

import io
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semblon.ingest import discover_media, ingest
from semblon.progress import KIND_PROGRESS, STAGE_INGEST, ProgressEvent


def _seed_images(folder: Path, names: list[str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"\xff\xd8\xfffake" + name.encode())


def _run(folder: Path, store: Path, workers: int, **kwargs) -> dict:
    vec = np.zeros(4, dtype=np.float32)

    def faces_for(_path):
        return [
            {
                "bbox": (0.0, 0.0, 100.0, 100.0),
                "det_score": 0.9,
                "face_w": 100,
                "face_h": 100,
                "dim": 4,
                "embedding": vec,
            }
            for _ in range(2)
        ]

    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()

    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest.embed_bgr", side_effect=lambda app, img: faces_for("x")),
        patch("semblon.ingest.cv2.imread", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch("semblon.ingest.cv2.imdecode", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        return ingest(folder, store, workers=workers, **kwargs)


def test_workers_rejects_zero(tmp_path):
    folder = tmp_path / "p"
    _seed_images(folder, ["a.jpg"])
    with pytest.raises(ValueError, match="workers"):
        _run(folder, tmp_path / "s.sqlite", workers=0)


def test_workers_two_matches_one_counts(tmp_path):
    folder = tmp_path / "photos"
    _seed_images(folder, ["a.jpg", "b.jpg", "c.jpg"])
    r1 = _run(folder, tmp_path / "w1.sqlite", workers=1)
    r2 = _run(folder, tmp_path / "w2.sqlite", workers=2)
    for key in ("files", "faces", "ok", "low_quality", "rejected", "failed", "new_media"):
        assert r1[key] == r2[key], key
    assert r1["files"] == 3
    assert r1["faces"] == 6
    assert r1["workers"] == 1
    assert r2["workers"] == 2
    assert "batch" not in r1
    assert "batch" not in r2

    conn = sqlite3.connect(str(tmp_path / "w2.sqlite"))
    n_obs = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    n_faces = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
    conn.close()
    assert n_obs == 3
    assert n_faces == 6


def test_workers_skip_before_embed(tmp_path):
    folder = tmp_path / "photos"
    _seed_images(folder, ["a.jpg", "b.jpg"])
    store = tmp_path / "s.sqlite"
    first = _run(folder, store, workers=2)
    assert first["new_media"] == 2
    assert first["faces"] == 4

    embed = MagicMock(return_value=[])
    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest.embed_bgr", embed),
        patch("semblon.ingest.cv2.imread", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch("semblon.ingest.cv2.imdecode", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        second = ingest(folder, store, workers=2)

    assert second["skipped_seen"] == 2
    assert second["new_media"] == 0
    assert second["faces"] == 0
    embed.assert_not_called()


def test_progress_monotonic_under_workers(tmp_path):
    folder = tmp_path / "photos"
    _seed_images(folder, [f"{i}.jpg" for i in range(8)])
    events: list[ProgressEvent] = []
    _run(folder, tmp_path / "s.sqlite", workers=4, on_event=events.append)
    currents = [
        e.current
        for e in events
        if e.stage == STAGE_INGEST and e.kind == KIND_PROGRESS and e.current is not None
    ]
    assert currents
    assert currents == sorted(currents)
    assert currents[-1] == 8


def test_discover_media_one_pass(tmp_path):
    folder = tmp_path / "mix"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"x")
    (folder / "b.MP4").write_bytes(b"y")
    (folder / "c.txt").write_text("z")
    stills, videos = discover_media(folder)
    assert [p.name for p in stills] == ["a.jpg"]
    assert [p.name for p in videos] == ["b.MP4"]


def test_video_frames_streamed_not_listed(tmp_path):
    folder = tmp_path / "mix"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"video")
    store = tmp_path / "s.sqlite"
    frames = [
        (0, 0, np.zeros((40, 40, 3), dtype=np.uint8)),
        (10, 500, np.zeros((40, 40, 3), dtype=np.uint8)),
    ]
    calls = {"n": 0}

    def gen(_path, _hz):
        calls["n"] += 1
        yield from frames

    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch(
            "semblon.ingest.embed_bgr",
            return_value=[
                {
                    "bbox": (0.0, 0.0, 10.0, 10.0),
                    "det_score": 0.9,
                    "face_w": 10,
                    "face_h": 10,
                    "dim": 4,
                    "embedding": np.zeros(4, dtype=np.float32),
                }
            ],
        ),
        patch("semblon.ingest.iter_sampled_frames", side_effect=gen),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        rec = ingest(folder, store)

    assert calls["n"] == 1
    assert rec["video_frames"] == 2
    assert rec["videos"] == 1


def test_cli_ingest_workers_flag_no_batch():
    from semblon.cli import main

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        with pytest.raises(SystemExit) as ei:
            main(["ingest", "--help"])
    assert ei.value.code == 0
    help_text = buf.getvalue()
    assert "--workers" in help_text
    assert "--batch" not in help_text
