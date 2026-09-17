"""Bounded ingest workers — plumbing + count parity with mocked FaceAnalysis."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.ingest import ingest


def _seed_images(folder: Path, names: list[str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"\xff\xd8\xfffake" + name.encode())


def _run(folder: Path, store: Path, workers: int) -> dict:
    vec = np.zeros(4, dtype=np.float32)

    def faces_for(path):
        # Deterministic: one face for a.jpg, two for others (same as progress test).
        n = 1 if Path(path).name == "a.jpg" else 2
        return [
            {
                "bbox": (0.0, 0.0, 100.0, 100.0),
                "det_score": 0.9,
                "face_w": 100,
                "face_h": 100,
                "dim": 4,
                "embedding": vec,
            }
            for _ in range(n)
        ]

    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()

    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest.embed_image", side_effect=lambda app, path: faces_for(path)),
        patch("semblon.ingest.cv2.imread", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        return ingest(folder, store, workers=workers)


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
    assert r1["faces"] == 5  # 1 + 2 + 2
    assert r1["workers"] == 1
    assert r2["workers"] == 2

    conn = sqlite3.connect(str(tmp_path / "w2.sqlite"))
    n_obs = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    n_faces = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
    conn.close()
    assert n_obs == 3
    assert n_faces == 5


def test_cli_ingest_workers_flag():
    from semblon.cli import main
    import io
    from unittest.mock import patch

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        with pytest.raises(SystemExit) as ei:
            main(["ingest", "--help"])
    assert ei.value.code == 0
    assert "--workers" in buf.getvalue()
