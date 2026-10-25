"""Unit tests for PERF-6 owner orchestrator (no Windows ARM64 required)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from semblon.experimental.inference.runtime_verify import verify_runtime

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "perf_inference_owner_arm64.py"


def _load():
    spec = importlib.util.spec_from_file_location("perf_inference_owner_arm64", HARNESS)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runtime_verify_smoke():
    rec = verify_runtime()
    assert "process_arch" in rec
    assert "process_execution" in rec
    assert "labels" in rec
    assert "onnxruntime" in rec


def test_refuse_lab_stand_in(tmp_path: Path):
    owner = _load()
    corpus = tmp_path / "perf-inference-48still" / "stills"
    corpus.mkdir(parents=True)
    try:
        owner._refuse_lab_stand_in(corpus, allow=False)
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "Refusing lab stand-in" in str(exc)


def test_decide_recommend_when_faster_and_identity(tmp_path: Path):
    owner = _load()
    bench_a = tmp_path / "a.json"
    bench_b = tmp_path / "b.json"
    ident = tmp_path / "i.json"
    out = tmp_path / "d.json"
    bench_a.write_text(
        json.dumps(
            {
                "steady_state": {"images_per_s": 1.0, "wall_s": 10.0},
                "runtime": {
                    "process_arch": "x64",
                    "process_execution": "emulated",
                    "labels": {"emulated_x64_on_arm64": True},
                },
            }
        ),
        encoding="utf-8",
    )
    bench_b.write_text(
        json.dumps(
            {
                "steady_state": {"images_per_s": 2.0, "wall_s": 5.0},
                "runtime": {"process_arch": "arm64", "process_execution": "native"},
            }
        ),
        encoding="utf-8",
    )
    ident.write_text(
        json.dumps({"owner_agreement_gate": {"pass": True}}),
        encoding="utf-8",
    )
    rep = owner.cmd_decide(
        bench_a=bench_a,
        bench_b=bench_b,
        identity=ident,
        bench_c=None,
        out=out,
    )
    assert rep["verdict"] == "RECOMMEND_CONTROLLED_EXPERIMENTAL_INTEGRATION"
    assert rep["production_cutover"] is False


def test_decide_investigate_when_slower(tmp_path: Path):
    owner = _load()
    bench_a = tmp_path / "a.json"
    bench_b = tmp_path / "b.json"
    ident = tmp_path / "i.json"
    out = tmp_path / "d.json"
    bench_a.write_text(
        json.dumps(
            {
                "steady_state": {"images_per_s": 2.0, "wall_s": 5.0},
                "runtime": {
                    "process_arch": "x64",
                    "process_execution": "emulated",
                    "labels": {"emulated_x64_on_arm64": True},
                },
            }
        ),
        encoding="utf-8",
    )
    bench_b.write_text(
        json.dumps(
            {
                "steady_state": {"images_per_s": 1.0, "wall_s": 10.0},
                "runtime": {"process_arch": "arm64", "process_execution": "native"},
            }
        ),
        encoding="utf-8",
    )
    ident.write_text(
        json.dumps({"owner_agreement_gate": {"pass": True}}),
        encoding="utf-8",
    )
    rep = owner.cmd_decide(
        bench_a=bench_a,
        bench_b=bench_b,
        identity=ident,
        bench_c=None,
        out=out,
    )
    assert rep["verdict"] == "INVESTIGATE_SETTINGS"
