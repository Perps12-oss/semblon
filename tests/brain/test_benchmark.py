"""Benchmark harness: fixture baselines, UNMEASURED rows, no model loads."""

from __future__ import annotations

from semblon.brain.benchmark import (
    FIXTURE_PROVIDER,
    BrainBenchmark,
    fixture_provider_fn,
    fixture_sample,
)
from semblon.brain.cache import EvidenceCache
from semblon.brain.registry import BASELINE_PROVIDERS, CapabilityRegistry
from semblon.store import connect, init_db


def test_fixture_run_records_latency(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    try:
        bench = BrainBenchmark(conn)
        result = bench.run(
            "C7",
            FIXTURE_PROVIDER,
            fixture_sample(n=8),
            provider_fn=fixture_provider_fn,
            cost_class="free",
        )
        assert result.unmeasured is False
        assert result.coverage == 1.0
        assert result.latency_p50_ms is not None
        assert result.latency_p50_ms >= 0
        bid = bench.record(result)
        row = conn.execute(
            "SELECT coverage, regressions_found FROM brain_benchmarks WHERE id=?",
            (bid,),
        ).fetchone()
        assert row[0] == 1.0
        assert row[1] == 0
    finally:
        conn.close()


def test_unmeasured_baselines_for_existing_providers(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    try:
        reg = CapabilityRegistry(conn)
        reg.seed_baselines()
        bench = BrainBenchmark(conn)
        existing = [
            (r.capability_id, r.provider_name, r.cost_class)
            for r in BASELINE_PROVIDERS
            if r.provider_kind == "existing"
        ]
        ids = bench.record_unmeasured_baselines(existing)
        assert len(ids) == len(existing)
        rows = conn.execute(
            "SELECT coverage FROM brain_benchmarks WHERE coverage < 0"
        ).fetchall()
        assert len(rows) == len(existing)
        assert reg.adopted_count() == 0
    finally:
        conn.close()


def test_evidence_cache_hit_rate_on_synthetic_fixtures():
    cache = EvidenceCache()
    sample = fixture_sample(n=5)
    for photo in sample.photos:
        obs = fixture_provider_fn(photo)[0]
        cache.put(obs)
    # Second pass: content-address + photo lookups should hit.
    for photo in sample.photos:
        assert cache.content_address_hit(photo.content_hash, None) is not None
        assert (
            cache.existing_observation(photo.photo_id, "C7", None) is not None
        )
    assert cache.hit_rate > 0
    assert cache.hits >= 10


def test_no_model_import_in_brain_package():
    """Inc 1 brain modules must not pull onnxruntime / insightface / torch."""
    import semblon.brain as brain
    import semblon.brain.benchmark as benchmark
    import semblon.brain.cache as cache
    import semblon.brain.policy as policy
    import semblon.brain.registry as registry

    banned = {"onnxruntime", "torch", "insightface", "open_clip", "cv2"}
    loaded = set(__import__("sys").modules) & banned
    # cv2 may already be loaded by the test process via other imports; brain
    # modules themselves must not appear as the importer of banned packs.
    for mod in (brain, benchmark, cache, policy, registry):
        src = Path_read(mod.__file__)
        for name in ("onnxruntime", "torch", "insightface", "open_clip"):
            assert f"import {name}" not in src
            assert f"from {name}" not in src


def Path_read(path: str) -> str:
    from pathlib import Path

    return Path(path).read_text(encoding="utf-8")
