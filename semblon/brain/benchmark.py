"""BrainBenchmark harness. Fixture baselines only in Increment 1 — no model loads."""

from __future__ import annotations

import hashlib
import sqlite3
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Sequence

from semblon.brain.observation import Observation, PhotoRef

# Synthetic fixture provider: zero model I/O. Used to prove the harness + DB path.
FIXTURE_PROVIDER = "fixture_baseline"


@dataclass(frozen=True)
class BenchmarkResult:
    capability_id: str
    provider_name: str
    sample_hash: str
    coverage: float | None
    quality: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    cost_class: str
    regressions_found: int = 0
    unmeasured: bool = False


@dataclass(frozen=True)
class SampleSpec:
    photos: Sequence[PhotoRef]
    sample_hash: str


def sample_hash_for(photos: Sequence[PhotoRef], *, library_id: str = "fixture") -> str:
    seed = hashlib.sha256(library_id.encode("utf-8"))
    for p in photos:
        seed.update(b"\0")
        seed.update(p.photo_id.encode("utf-8"))
        if p.content_hash:
            seed.update(p.content_hash.encode("utf-8"))
    return seed.hexdigest()[:32]


def fixture_sample(n: int = 8, *, library_id: str = "fixture") -> SampleSpec:
    photos = [
        PhotoRef(photo_id=f"fixture-{i:03d}", content_hash=f"sha-{i:03d}")
        for i in range(n)
    ]
    return SampleSpec(photos=photos, sample_hash=sample_hash_for(photos, library_id=library_id))


class BrainBenchmark:
    """Run and persist local benchmarks. Never exports."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def run(
        self,
        capability_id: str,
        provider_name: str,
        sample: SampleSpec | Sequence[PhotoRef],
        *,
        provider_fn: Callable[[PhotoRef], list[Observation] | None] | None = None,
        cost_class: str = "free",
        unmeasured: bool = False,
    ) -> BenchmarkResult:
        if isinstance(sample, SampleSpec):
            photos = list(sample.photos)
            digest = sample.sample_hash
        else:
            photos = list(sample)
            digest = sample_hash_for(photos)

        if unmeasured or provider_fn is None:
            return BenchmarkResult(
                capability_id=capability_id,
                provider_name=provider_name,
                sample_hash=digest,
                coverage=None,
                quality=None,
                latency_p50_ms=None,
                latency_p95_ms=None,
                cost_class=cost_class,
                regressions_found=0,
                unmeasured=True,
            )

        latencies: list[float] = []
        ok = 0
        for photo in photos:
            t0 = time.perf_counter()
            out = provider_fn(photo)
            latencies.append((time.perf_counter() - t0) * 1000.0)
            if out is not None:
                ok += 1

        coverage = ok / len(photos) if photos else 0.0
        p50 = statistics.median(latencies) if latencies else None
        p95 = (
            statistics.quantiles(latencies, n=20)[18]
            if len(latencies) >= 20
            else (max(latencies) if latencies else None)
        )
        return BenchmarkResult(
            capability_id=capability_id,
            provider_name=provider_name,
            sample_hash=digest,
            coverage=coverage,
            quality=None,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            cost_class=cost_class,
            regressions_found=0,
            unmeasured=False,
        )

    def record(self, result: BenchmarkResult) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            """
            INSERT INTO brain_benchmarks(
              capability_id, provider_name, sample_hash,
              coverage, quality, latency_p50_ms, latency_p95_ms,
              cost_class, regressions_found, run_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                result.capability_id,
                result.provider_name,
                result.sample_hash,
                -1.0 if result.coverage is None else result.coverage,
                result.quality,
                result.latency_p50_ms,
                result.latency_p95_ms,
                result.cost_class,
                result.regressions_found,
                now,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def record_unmeasured_baselines(
        self,
        providers: Sequence[tuple[str, str, str]],
        *,
        sample: SampleSpec | None = None,
    ) -> list[int]:
        """Register UNMEASURED rows for (capability_id, provider_name, cost_class)."""
        spec = sample or fixture_sample()
        ids: list[int] = []
        for capability_id, provider_name, cost_class in providers:
            result = self.run(
                capability_id,
                provider_name,
                spec,
                cost_class=cost_class,
                unmeasured=True,
            )
            ids.append(self.record(result))
        return ids


def fixture_provider_fn(photo: PhotoRef) -> list[Observation]:
    """Deterministic zero-I/O provider for harness self-test."""
    return [
        Observation(
            photo_id=photo.photo_id,
            capability_id="C7",
            provider_name=FIXTURE_PROVIDER,
            payload={"ok": True},
            content_hash=photo.content_hash,
            confidence=1.0,
        )
    ]
