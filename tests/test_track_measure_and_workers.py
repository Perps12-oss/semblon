"""Track fragmentation measurement and hash-worker bench (portable)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from semblon.bench_workers import BenchError, bench_hash_workers
from semblon.track_measure import (
    TrackMeasureError,
    measure_video_fragmentation,
    summarize_association,
    write_report,
)


def test_summarize_association_continuation_and_separation():
    # Two people, three frames — should stay two tracks when separated.
    dets = []
    for frame, t in ((0, 0), (1, 100), (2, 200)):
        dets.append(
            {
                "face_id": f"a{frame}",
                "observation_id": f"o{frame}",
                "media_id": "m",
                "path": "x",
                "frame_id": frame,
                "t_ms": t,
                "bbox": (10.0, 10.0, 50.0, 50.0),
                "face_w": 40,
                "face_h": 40,
                "person_id": None,
                "cluster_id": None,
            }
        )
        dets.append(
            {
                "face_id": f"b{frame}",
                "observation_id": f"o{frame}",
                "media_id": "m",
                "path": "x",
                "frame_id": frame,
                "t_ms": t,
                "bbox": (200.0, 10.0, 240.0, 50.0),
                "face_w": 40,
                "face_h": 40,
                "person_id": None,
                "cluster_id": None,
            }
        )
    summary = summarize_association(dets)
    assert summary["detections"] == 6
    assert summary["tracks"] == 2
    assert summary["fragmentation_index"] < 0.5
    assert summary["multi_face_frames"] == 3


def test_summarize_missed_detection_gap_creates_short_tracks():
    # Large temporal gap → fragmentation (new track after gap).
    dets = [
        {
            "face_id": "a0",
            "observation_id": "o0",
            "media_id": "m",
            "path": "x",
            "frame_id": 0,
            "t_ms": 0,
            "bbox": (10.0, 10.0, 50.0, 50.0),
            "face_w": 40,
            "face_h": 40,
            "person_id": None,
            "cluster_id": None,
        },
        {
            "face_id": "a1",
            "observation_id": "o1",
            "media_id": "m",
            "path": "x",
            "frame_id": 1,
            "t_ms": 8000,
            "bbox": (12.0, 12.0, 52.0, 52.0),
            "face_w": 40,
            "face_h": 40,
            "person_id": None,
            "cluster_id": None,
        },
    ]
    summary = summarize_association(dets, max_t_ms_gap=2500)
    assert summary["tracks"] == 2
    assert summary["short_lived_tracks"] == 2
    assert summary["fragmentation_index"] == 1.0


def test_measure_video_synthetic(tmp_path):
    import cv2

    path = tmp_path / "multi.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (320, 240))
    assert writer.isOpened()
    for i in range(30):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        frame[:] = (20, 20, 20)
        writer.write(frame)
    writer.release()

    def detect(frame, frame_index):
        dx = frame_index * 2
        return [
            {"bbox": (20.0 + dx, 30.0, 70.0 + dx, 90.0)},
            {"bbox": (200.0 - dx, 40.0, 250.0 - dx, 100.0)},
        ]

    rec = measure_video_fragmentation(path, detect=detect, sample_hz=10.0, max_frames=20)
    assert rec["samples"] >= 10
    assert rec["detections"] >= 20
    assert rec["max_simultaneous_faces"] == 2
    assert rec["tracks"] >= 1
    out = write_report(rec, tmp_path / "frag.json")
    assert out.is_file()


def test_measure_missing_video(tmp_path):
    with pytest.raises(TrackMeasureError):
        measure_video_fragmentation(tmp_path / "missing.mp4")


def test_bench_hash_workers_equivalence(tmp_path):
    folder = tmp_path / "lib"
    folder.mkdir()
    for i in range(12):
        (folder / f"a{i}.jpg").write_bytes(bytes([i % 256]) * (2000 + i * 17))
    store_dir = tmp_path / "stores"
    rec = bench_hash_workers(folder, store_dir, workers_list=[1, 2, 4])
    assert rec["phase"] == "hash_only"
    assert rec["inference_parallel"] is False
    assert rec["semantic_digest_equivalence"] is True
    assert len(rec["runs"]) == 3
    assert all(r["hashed_ok"] == 12 for r in rec["runs"])


def test_bench_empty_folder(tmp_path):
    with pytest.raises(BenchError):
        bench_hash_workers(tmp_path / "empty", tmp_path / "s")
    (tmp_path / "empty").mkdir()
    with pytest.raises(BenchError):
        bench_hash_workers(tmp_path / "empty", tmp_path / "s")
