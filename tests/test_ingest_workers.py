"""Bounded ingest workers — hash parallelism + skip-before-embed + cancel/integrity."""

from __future__ import annotations

import io
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semblon.ingest import MAX_WORKERS, CancelledError, discover_media, ingest
from semblon.progress import KIND_CANCELLED, KIND_COMPLETED, KIND_PROGRESS, STAGE_INGEST, ProgressEvent


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


def test_workers_rejects_negative(tmp_path):
    folder = tmp_path / "p"
    _seed_images(folder, ["a.jpg"])
    with pytest.raises(ValueError, match="workers"):
        _run(folder, tmp_path / "s.sqlite", workers=-1)


def test_workers_rejects_above_max(tmp_path):
    folder = tmp_path / "p"
    _seed_images(folder, ["a.jpg"])
    with pytest.raises(ValueError, match="workers"):
        _run(folder, tmp_path / "s.sqlite", workers=MAX_WORKERS + 1)


def test_product_default_workers_is_one():
    import inspect

    from semblon import ingest as ingest_mod

    assert inspect.signature(ingest_mod.ingest).parameters["workers"].default == 1


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


def test_workers_four_matches_one_store_integrity(tmp_path):
    folder = tmp_path / "photos"
    _seed_images(folder, [f"{i}.jpg" for i in range(12)])
    r1 = _run(folder, tmp_path / "w1.sqlite", workers=1)
    r4 = _run(folder, tmp_path / "w4.sqlite", workers=4)
    for key in ("files", "faces", "ok", "low_quality", "rejected", "failed", "new_media"):
        assert r1[key] == r4[key], key

    conn = sqlite3.connect(str(tmp_path / "w4.sqlite"))
    n_media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    n_obs = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    n_faces = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
    n_sha = conn.execute("SELECT COUNT(DISTINCT sha256) FROM media").fetchone()[0]
    notes = conn.execute("SELECT notes FROM runs").fetchone()[0]
    conn.close()
    assert n_media == 12
    assert n_obs == 12
    assert n_faces == 24
    assert n_sha == 12
    assert notes is None


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


def test_cancel_under_workers_stamps_cancelled(tmp_path):
    folder = tmp_path / "photos"
    _seed_images(folder, [f"{i}.jpg" for i in range(6)])
    store = tmp_path / "s.sqlite"
    events: list[ProgressEvent] = []
    processed = {"n": 0}
    vec = np.zeros(4, dtype=np.float32)

    def faces_for(_app, _img):
        processed["n"] += 1
        return [
            {
                "bbox": (0.0, 0.0, 100.0, 100.0),
                "det_score": 0.9,
                "face_w": 100,
                "face_h": 100,
                "dim": 4,
                "embedding": vec,
            }
        ]

    def cancel():
        return processed["n"] >= 2

    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest.embed_bgr", side_effect=faces_for),
        patch("semblon.ingest.cv2.imread", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch("semblon.ingest.cv2.imdecode", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        with pytest.raises(CancelledError):
            ingest(folder, store, workers=4, on_event=events.append, cancel=cancel)

    assert any(e.kind == KIND_CANCELLED for e in events)
    assert not any(e.kind == KIND_COMPLETED and e.stage == STAGE_INGEST for e in events)
    conn = sqlite3.connect(str(store))
    notes, timings = conn.execute("SELECT notes, timings_json FROM runs").fetchone()
    n_media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    conn.close()
    assert notes == "cancelled"
    assert '"cancelled": true' in timings
    assert 1 <= n_media < 6


def test_pause_gate_under_workers_no_duplicate_media(tmp_path):
    """JobEngine-style gate: block while paused; resume same job; single writer."""
    folder = tmp_path / "photos"
    _seed_images(folder, [f"{i}.jpg" for i in range(4)])
    store = tmp_path / "s.sqlite"
    pause = threading.Event()
    cancel_ev = threading.Event()
    saw_pause = threading.Event()
    embed_threads: list[str] = []
    vec = np.zeros(4, dtype=np.float32)

    def gate() -> bool:
        if pause.is_set() and not cancel_ev.is_set():
            saw_pause.set()
        while pause.is_set() and not cancel_ev.is_set():
            time.sleep(0.01)
        return cancel_ev.is_set()

    def faces_for(_app, _img):
        embed_threads.append(threading.current_thread().name)
        if len(embed_threads) == 1:
            pause.set()
        return [
            {
                "bbox": (0.0, 0.0, 100.0, 100.0),
                "det_score": 0.9,
                "face_w": 100,
                "face_h": 100,
                "dim": 4,
                "embedding": vec,
            }
        ]

    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    result: dict = {}

    def run():
        with (
            patch("semblon.ingest.load_app", return_value=object()),
            patch("semblon.ingest.discover_weight_hashes", return_value={}),
            patch("semblon.ingest.embed_bgr", side_effect=faces_for),
            patch("semblon.ingest.cv2.imread", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
            patch("semblon.ingest.cv2.imdecode", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
            patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
        ):
            result.update(ingest(folder, store, workers=4, cancel=gate))

    t = threading.Thread(target=run, name="ingest-main")
    t.start()
    assert saw_pause.wait(5)
    time.sleep(0.05)
    pause.clear()
    t.join(10)
    assert not t.is_alive()
    assert result.get("files") == 4
    assert result.get("faces") == 4
    assert result.get("cancelled") is False
    # Decode/embed/SQLite stay on the ingest main thread (hash pool never embeds).
    assert embed_threads
    assert all(name == "ingest-main" for name in embed_threads)

    conn = sqlite3.connect(str(store))
    n_media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    n_sha = conn.execute("SELECT COUNT(DISTINCT sha256) FROM media").fetchone()[0]
    conn.close()
    assert n_media == 4
    assert n_sha == 4


def test_workers_hash_failure_counts(tmp_path):
    folder = tmp_path / "photos"
    _seed_images(folder, ["a.jpg", "b.jpg", "c.jpg"])
    store = tmp_path / "s.sqlite"
    real_hash = __import__("semblon.ingest", fromlist=["_hash_path"])._hash_path
    calls = {"n": 0}

    def flaky(path, index):
        calls["n"] += 1
        if Path(path).name == "b.jpg":
            return {"index": index, "path": path, "outcome": "failed", "error": "hash"}
        return real_hash(path, index)

    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest._hash_path", side_effect=flaky),
        patch(
            "semblon.ingest.embed_bgr",
            return_value=[
                {
                    "bbox": (0.0, 0.0, 100.0, 100.0),
                    "det_score": 0.9,
                    "face_w": 100,
                    "face_h": 100,
                    "dim": 4,
                    "embedding": np.zeros(4, dtype=np.float32),
                }
            ],
        ),
        patch("semblon.ingest.cv2.imread", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch("semblon.ingest.cv2.imdecode", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        rec = ingest(folder, store, workers=3)

    assert rec["failed"] == 1
    assert rec["new_media"] == 2
    assert rec["faces"] == 2


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
    assert "default 1" in help_text.lower() or "default: 1" in help_text.lower()
