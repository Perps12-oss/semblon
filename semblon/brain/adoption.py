"""Adoption helpers — §6 gates. First-adoption of existing providers allowed."""

from __future__ import annotations

import sqlite3

from semblon.brain.benchmark import BrainBenchmark, fixture_sample
from semblon.brain.registry import CapabilityRegistry


UNMEASURED = -1.0


def _first_adopt_unmeasured(
    conn: sqlite3.Connection,
    *,
    capability_id: str,
    provider_name: str,
    cost_class: str,
    library_id: str,
) -> int:
    reg = CapabilityRegistry(conn)
    reg.seed_baselines()
    bench = BrainBenchmark(conn)
    result = bench.run(
        capability_id,
        provider_name,
        fixture_sample(n=8, library_id=library_id),
        cost_class=cost_class,
        unmeasured=True,
    )
    bid = bench.record(result)
    conn.execute(
        """UPDATE brain_capabilities
              SET coverage=?, quality=?, latency_p50_ms=NULL, latency_p95_ms=NULL,
                  benchmark_run_id=?
            WHERE capability_id=? AND provider_name=?""",
        (UNMEASURED, None, bid, capability_id, provider_name),
    )
    conn.commit()
    reg.adopt(capability_id, provider_name, bid)
    return bid


def adopt_existing_nanodet_tags(conn: sqlite3.Connection) -> int:
    """First-adoption of C1 existing_nanodet_tags against an UNMEASURED baseline row."""
    return _first_adopt_unmeasured(
        conn,
        capability_id="C1",
        provider_name="existing_nanodet_tags",
        cost_class="cheap",
        library_id="inc3-nanodet-baseline",
    )


def adopt_existing_object_dbscan(conn: sqlite3.Connection) -> int:
    """First-adoption of C5 existing_object_dbscan (batch ObjectCluster path)."""
    return _first_adopt_unmeasured(
        conn,
        capability_id="C5",
        provider_name="existing_object_dbscan",
        cost_class="free",
        library_id="inc4-object-dbscan-baseline",
    )
