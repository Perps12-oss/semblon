"""bench_ingest harness contract/scaling reporting."""

from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path
from unittest.mock import patch


def _load_bench_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "bench_ingest.py"
    spec = importlib.util.spec_from_file_location("bench_ingest_mod", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_bench_worker_sweep_reports_efficiency(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"fake")
    out = tmp_path / "bench.json"

    fake_ingest = types.ModuleType("semblon.ingest")

    def ingest(_folder, _store, workers=1, prefer_gpu=False):
        ingest_s = {1: 10.0, 2: 6.0, 4: 8.0}[int(workers)]
        return {
            "run_id": f"r{workers}",
            "files": 10,
            "faces": 20,
            "ok": 20,
            "failed": 0,
            "ingest_s": ingest_s,
            "images_per_second": round(10.0 / ingest_s, 4),
            "faces_per_second": round(20.0 / ingest_s, 4),
            "seconds_per_image": round(ingest_s / 10.0, 6),
            "seconds_per_face": round(ingest_s / 20.0, 6),
        }

    fake_ingest.ingest = ingest

    fake_contract = types.ModuleType("semblon.perf_contract")

    def build_semantic_snapshot(_store, run_id, embedding_tol=1e-6):
        worker = int(str(run_id).lstrip("r"))
        return {
            "run_id": run_id,
            "runtime_evidence": {
                "execution_provider": "CPUExecutionProvider",
                "workers": worker,
            },
        }

    def compare_semantic_snapshots(_before, _after, score_tol=1e-6):
        return {"ok": True, "diffs": []}

    fake_contract.build_semantic_snapshot = build_semantic_snapshot
    fake_contract.compare_semantic_snapshots = compare_semantic_snapshots

    mod = _load_bench_module()
    with patch.dict(
        "sys.modules",
        {
            "semblon.ingest": fake_ingest,
            "semblon.perf_contract": fake_contract,
        },
    ):
        rc = mod.main(
            [
                "--folder",
                str(folder),
                "--out",
                str(out),
                "--execute",
                "--sweep",
                "1,2,4",
            ]
        )
    assert rc == 0
    rec = json.loads(out.read_text(encoding="utf-8"))
    assert rec["verified"] is True
    assert rec["worker_sweep"] == [1, 2, 4]
    assert rec["semantic_contract_ok"] is True
    assert rec["recommended_worker_ceiling"] == 2
    rows = rec["results"]
    assert rows[1]["scaling_efficiency_t1_over_tw"] == round(10.0 / 6.0, 4)
