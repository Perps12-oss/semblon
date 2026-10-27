"""Hash-worker semantic equivalence. Timing is recorded by the tool, not asserted."""

from __future__ import annotations

from pathlib import Path

from semblon.hash_workers_measure import measure_folder


def test_workers_1_2_4_hash_the_same_bytes(tmp_path: Path):
    folder = tmp_path / "stills"
    folder.mkdir()
    payload = b"semblon-hash-worker-"
    for index in range(12):
        blob = payload + bytes([index]) * (4096 + index * 128)
        (folder / f"img-{index:02d}.bin").write_bytes(blob)
    report = measure_folder(folder)
    assert report["inference_parallel"] is False
    assert report["product_default_workers"] == 1
    assert report["default_changed"] is False
    assert report["semantic_equivalent"] is True
    assert [row["workers"] for row in report["runs"]] == [1, 2, 4]
    assert all(row["files"] == 12 for row in report["runs"])
    assert all(row["inference"] is False for row in report["runs"])
