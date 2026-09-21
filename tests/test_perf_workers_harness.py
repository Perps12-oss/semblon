"""PERF workers measure harness — hash-phase only; default stays 1."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from semblon import ingest
from semblon.perf_workers_harness import (
    DEFAULT_PRODUCT_WORKERS,
    HASH_PHASE_NOTE,
    measure_hash_workers,
)


def _seed_tiny(folder: Path, n: int = 6) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (folder / f"{i:04d}.jpg").write_bytes(b"\xff\xd8\xff" + bytes([i % 256]) * 128)


def test_measure_includes_workers_1_2_4(tmp_path: Path):
    folder = tmp_path / "media"
    _seed_tiny(folder, 8)
    report = measure_hash_workers(folder)

    assert report["verified"] is True
    assert report["file_count"] == 8
    assert report["default_product_workers"] == 1
    assert report["default_product_workers"] == DEFAULT_PRODUCT_WORKERS
    assert report["recommend_change_default"] is False
    assert "keep" in str(report.get("recommendation", "")).lower()
    assert "hash" in str(report["note"]).lower() or "hash" in str(report["phase"]).lower()
    assert "hash-phase" in HASH_PHASE_NOTE

    workers = [r["workers"] for r in report["runs"]]
    assert workers == [1, 2, 4]
    w1 = report["runs"][0]
    assert w1["workers"] == 1
    assert w1["speedup_vs_w1"] == 1.0
    assert w1["hashed"] + w1["failed"] == 8
    for row in report["runs"]:
        assert "speedup_vs_w1" in row
        assert row["wall_s"] is not None
        assert row["wall_s"] >= 0


def test_missing_folder_verified_false(tmp_path: Path):
    missing = tmp_path / "no-such-dir"
    report = measure_hash_workers(missing)
    assert report["verified"] is False
    assert report["default_product_workers"] == 1
    assert report["recommend_change_default"] is False
    assert [r["workers"] for r in report["runs"]] == [1, 2, 4]
    assert "hash" in str(report["note"]).lower() or report["phase"] == "hash"


def test_none_folder_verified_false():
    report = measure_hash_workers(None)
    assert report["verified"] is False
    assert report["default_product_workers"] == 1
    assert report["recommend_change_default"] is False


def test_ingest_default_workers_unchanged():
    sig = inspect.signature(ingest.ingest)
    assert sig.parameters["workers"].default == 1


def test_cli_writes_json(tmp_path: Path):
    folder = tmp_path / "media"
    _seed_tiny(folder, 4)
    out = tmp_path / "out" / "report.json"
    import runpy

    tool_path = Path(__file__).resolve().parents[1] / "tools" / "perf_workers_measure.py"
    ns = runpy.run_path(str(tool_path))
    rc = ns["main"](["--folder", str(folder), "--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["verified"] is True
    assert data["default_product_workers"] == 1
    assert data["recommend_change_default"] is False
    assert [r["workers"] for r in data["runs"]] == [1, 2, 4]
    assert "hash" in str(data["note"]).lower()
    blob = json.dumps(data).lower()
    assert "should change default" not in blob
    assert data["recommendation"] == "keep product default workers=1"


def test_cli_missing_folder_honest(tmp_path: Path):
    out = tmp_path / "missing.json"
    import runpy

    tool_path = Path(__file__).resolve().parents[1] / "tools" / "perf_workers_measure.py"
    ns = runpy.run_path(str(tool_path))
    rc = ns["main"](["--out", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["verified"] is False
    assert data["default_product_workers"] == 1
    assert data["recommend_change_default"] is False
