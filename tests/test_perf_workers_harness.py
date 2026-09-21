"""PERF workers harness — dry-run / pending_human without a real corpus."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "perf_workers_harness.py"


def _load_harness():
    """Import harness as a module without installing tools/ on PYTHONPATH."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("perf_workers_harness", HARNESS)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pending_record_is_unverified():
    mod = _load_harness()
    rec = mod.pending_record()
    assert rec["verified"] is False
    assert rec["status"] == "pending_human"
    assert rec["workers_sweep"] == [1, 2, 4]
    assert rec["face_count_equal"] is None
    assert rec["runs"] == []
    assert "workers=1" in rec["note"] or "workers remain 1" in rec["note"]
    assert len(rec["human_steps"]) >= 1


def test_cli_without_folder_writes_pending_human(tmp_path):
    out = tmp_path / "results.json"
    proc = subprocess.run(
        [sys.executable, str(HARNESS), "--out", str(out)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["verified"] is False
    assert rec["status"] == "pending_human"
    assert rec["harness"] == "perf_workers"
    assert rec["folder"] is None


def test_execute_without_folder_stays_pending(tmp_path):
    out = tmp_path / "results.json"
    proc = subprocess.run(
        [sys.executable, str(HARNESS), "--out", str(out), "--execute"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["verified"] is False
    assert rec["status"] == "pending_human"
    assert "folder" in (rec.get("error") or "").lower() or rec["folder"] is None


def test_face_counts_equal_helper():
    mod = _load_harness()
    a = {"files": 3, "faces": 6, "ok": 6, "low_quality": 0, "rejected": 0, "failed": 0}
    b = dict(a)
    c = dict(a)
    assert mod.face_counts_equal([a, b, c]) is True
    c["faces"] = 5
    assert mod.face_counts_equal([a, b, c]) is False


def test_run_sweep_mocked_no_corpus(tmp_path, monkeypatch):
    """verified:true path without InsightFace — ingest patched."""
    import types

    mod = _load_harness()
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"\xff\xd8\xff")

    calls: list[int] = []

    def fake_ingest(fld, store, workers=1, **_kwargs):
        calls.append(workers)
        return {
            "run_id": f"r-w{workers}",
            "files": 1,
            "faces": 2,
            "ok": 2,
            "low_quality": 0,
            "rejected": 0,
            "failed": 0,
            "ingest_s": 0.5,
            "images_per_second": 2.0,
            "faces_per_second": 4.0,
        }

    fake_mod = types.ModuleType("semblon.ingest")
    fake_mod.ingest = fake_ingest
    monkeypatch.setitem(sys.modules, "semblon.ingest", fake_mod)

    out = tmp_path / "results.json"
    out_dir = tmp_path / "stores"
    rec = mod.run_sweep(folder=folder, out_dir=out_dir, out_path=out)
    assert rec["verified"] is True
    assert rec["status"] == "measured"
    assert rec["face_count_equal"] is True
    assert calls == [1, 2, 4]
    assert len(rec["runs"]) == 3
    assert all(r["images_per_second"] == 2.0 for r in rec["runs"])
    assert all(r["faces_per_second"] == 4.0 for r in rec["runs"])
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["verified"] is True
