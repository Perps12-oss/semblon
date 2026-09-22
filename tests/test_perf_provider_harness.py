"""Provider harness — listing only; never claims GPU speedup."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "perf_provider_harness.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("perf_provider_harness", HARNESS)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_provider_harness_dry_record_honest():
    mod = _load_harness()
    rec = mod.build_record(execute=False)
    assert rec["harness"] == "perf_provider"
    assert rec["verified"] is False
    assert rec["status"] == "dry_run"
    assert "Azure" in rec["note"]
    assert "workers" in rec["note"].lower()
    assert "ARM64" in rec["note"]
    assert "execution" in rec
    assert rec["execution"]["chosen"]


def test_provider_harness_cli_writes_out(tmp_path):
    mod = _load_harness()
    out = tmp_path / "prov.json"
    assert mod.main(["--out", str(out), "--execute"]) == 0
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["status"] == "measured_listing"
    assert rec["verified"] is False
    assert rec["execution"]["gpu"] in (True, False)
