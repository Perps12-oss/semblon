"""CapabilityRegistry: seed baselines, refuse faith adoption."""

from __future__ import annotations

import pytest

from semblon.brain.benchmark import BrainBenchmark, fixture_provider_fn, fixture_sample
from semblon.brain.registry import BASELINE_PROVIDERS, CapabilityRegistry
from semblon.store import connect, init_db


def _reg(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    return conn, CapabilityRegistry(conn)


def test_seed_baselines_adopted_zero(tmp_path):
    conn, reg = _reg(tmp_path)
    try:
        n = reg.seed_baselines()
        assert n == len(BASELINE_PROVIDERS)
        assert reg.adopted_count() == 0
        assert reg.seed_baselines() == 0  # idempotent
        c1 = reg.list_for("C1")
        names = {r.provider_name for r in c1}
        assert "existing_nanodet_tags" in names
        assert "ram_plus" in names
        assert all(not r.adopted for r in c1)
    finally:
        conn.close()


def test_no_faiss_in_baselines():
    names = {r.provider_name for r in BASELINE_PROVIDERS}
    assert "existing_index" in names
    assert not any("faiss" in n.lower() for n in names)


def test_adopt_requires_benchmark(tmp_path):
    conn, reg = _reg(tmp_path)
    try:
        reg.seed_baselines()
        with pytest.raises(ValueError, match="benchmark_run_id missing"):
            reg.adopt("C7", "existing_compare", benchmark_run_id=99999)
        assert reg.adopted_count() == 0
    finally:
        conn.close()


def test_adopt_refuses_regressions(tmp_path):
    conn, reg = _reg(tmp_path)
    try:
        reg.seed_baselines()
        bench = BrainBenchmark(conn)
        result = bench.run(
            "C7",
            "existing_compare",
            fixture_sample(),
            provider_fn=fixture_provider_fn,
            cost_class="free",
        )
        # Force a regression flag before record.
        from dataclasses import replace

        bad = replace(result, regressions_found=1)
        bid = bench.record(bad)
        with pytest.raises(ValueError, match="regressions"):
            reg.adopt("C7", "existing_compare", bid)
        assert reg.adopted_count() == 0
    finally:
        conn.close()


def test_adopt_ok_when_benchmark_clean(tmp_path):
    """Adoption path exists for later increments; Inc 1 still leaves count at caller choice."""
    conn, reg = _reg(tmp_path)
    try:
        reg.seed_baselines()
        bench = BrainBenchmark(conn)
        bid = bench.record(
            bench.run(
                "C7",
                "existing_compare",
                fixture_sample(),
                provider_fn=fixture_provider_fn,
            )
        )
        reg.adopt("C7", "existing_compare", bid)
        assert reg.adopted_count() == 1
        assert reg.adopted_provider("C7").provider_name == "existing_compare"
    finally:
        conn.close()
