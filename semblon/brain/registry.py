"""Capability registry over brain_capabilities / brain_benchmarks."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ProviderRecord:
    capability_id: str
    provider_name: str
    provider_kind: str
    cost_class: str
    model_pack_hash: str | None = None
    coverage: float | None = None
    quality: float | None = None
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    benchmark_run_id: int | None = None
    adopted: bool = False
    notes: str | None = None


# Existing baselines + dormant candidates from docs/brain/INVENTORY.md.
# All start adopted=0. No model is loaded by seeding.
BASELINE_PROVIDERS: tuple[ProviderRecord, ...] = (
    ProviderRecord("C1", "existing_nanodet_tags", "existing", "cheap", notes="NanoDet COCO labels"),
    ProviderRecord("C1", "ram_plus", "brain_model", "moderate", notes="dormant candidate"),
    ProviderRecord("C2", "existing_nanodet_localise", "existing", "cheap", notes="NanoDet bbox"),
    ProviderRecord("C2", "existing_sam2", "existing", "moderate", notes="optional SAM2 refine"),
    ProviderRecord("C2", "grounding_dino", "brain_model", "heavy", notes="dormant; SHIP-GATES"),
    ProviderRecord(
        "C3",
        "existing_region_encoder",
        "existing",
        "cheap",
        model_pack_hash="f22797eabf810a75",
        notes="DINOv2 ViT-S/14 CLS",
    ),
    ProviderRecord("C4", "existing_face_embedder", "existing", "cheap", notes="yunet_sface"),
    ProviderRecord("C4", "adaface_ir18", "brain_model", "cheap", notes="dormant candidate"),
    ProviderRecord("C5", "existing_dbscan", "existing", "free", notes="cluster.py face DBSCAN"),
    ProviderRecord(
        "C5",
        "existing_object_dbscan",
        "existing",
        "free",
        notes="batch ObjectCluster DBSCAN over region embeddings (Inc 4)",
    ),
    ProviderRecord("C5", "hdbscan", "brain_model", "cheap", notes="dormant candidate"),
    ProviderRecord("C6", "existing_index", "existing", "free", notes="exact-derived; no FAISS"),
    ProviderRecord("C7", "existing_compare", "existing", "free", notes="compare.py"),
    ProviderRecord(
        "C8",
        "existing_scene_embedding",
        "existing",
        "cheap",
        model_pack_hash="f22797eabf810a75",
        notes="DINOv2 scene modality; not a classifier",
    ),
    ProviderRecord("C9", "existing_ocr", "existing", "cheap", notes="tesseract observer"),
)


class CapabilityRegistry:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def seed_baselines(self) -> int:
        """Insert inventory providers with adopted=0. Idempotent."""
        inserted = 0
        for rec in BASELINE_PROVIDERS:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO brain_capabilities(
                  capability_id, provider_name, provider_kind, model_pack_hash,
                  cost_class, coverage, quality, latency_p50_ms, latency_p95_ms,
                  benchmark_run_id, adopted, notes
                ) VALUES (?,?,?,?,?,?,?,?,?,?,0,?)
                """,
                (
                    rec.capability_id,
                    rec.provider_name,
                    rec.provider_kind,
                    rec.model_pack_hash,
                    rec.cost_class,
                    rec.coverage,
                    rec.quality,
                    rec.latency_p50_ms,
                    rec.latency_p95_ms,
                    rec.benchmark_run_id,
                    rec.notes,
                ),
            )
            inserted += int(cur.rowcount or 0)
        self._conn.commit()
        return inserted

    def register(
        self,
        record: ProviderRecord,
        *,
        adopted: bool = False,
    ) -> int:
        if adopted and record.benchmark_run_id is None:
            raise ValueError("adopted=1 requires benchmark_run_id")
        cur = self._conn.execute(
            """
            INSERT INTO brain_capabilities(
              capability_id, provider_name, provider_kind, model_pack_hash,
              cost_class, coverage, quality, latency_p50_ms, latency_p95_ms,
              benchmark_run_id, adopted, adopted_at, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(capability_id, provider_name) DO UPDATE SET
              provider_kind=excluded.provider_kind,
              model_pack_hash=excluded.model_pack_hash,
              cost_class=excluded.cost_class,
              coverage=excluded.coverage,
              quality=excluded.quality,
              latency_p50_ms=excluded.latency_p50_ms,
              latency_p95_ms=excluded.latency_p95_ms,
              benchmark_run_id=excluded.benchmark_run_id,
              adopted=excluded.adopted,
              adopted_at=excluded.adopted_at,
              notes=excluded.notes
            """,
            (
                record.capability_id,
                record.provider_name,
                record.provider_kind,
                record.model_pack_hash,
                record.cost_class,
                record.coverage,
                record.quality,
                record.latency_p50_ms,
                record.latency_p95_ms,
                record.benchmark_run_id,
                1 if adopted else 0,
                datetime.now(timezone.utc).isoformat() if adopted else None,
                record.notes,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def adopt(self, capability_id: str, provider_name: str, benchmark_run_id: int) -> None:
        """Mark adopted only when a benchmark row exists. Never on faith."""
        row = self._conn.execute(
            "SELECT id FROM brain_benchmarks WHERE id=?",
            (benchmark_run_id,),
        ).fetchone()
        if row is None:
            raise ValueError("benchmark_run_id missing — cannot adopt")
        bench = self._conn.execute(
            """SELECT capability_id, provider_name, regressions_found
               FROM brain_benchmarks WHERE id=?""",
            (benchmark_run_id,),
        ).fetchone()
        if bench[0] != capability_id or bench[1] != provider_name:
            raise ValueError("benchmark does not match capability/provider")
        if int(bench[2] or 0) > 0:
            raise ValueError("regressions_found > 0 — adoption refused")
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            """
            UPDATE brain_capabilities
               SET adopted=1, adopted_at=?, benchmark_run_id=?
             WHERE capability_id=? AND provider_name=?
            """,
            (now, benchmark_run_id, capability_id, provider_name),
        )
        if cur.rowcount == 0:
            raise ValueError("provider not registered")
        self._conn.commit()

    def list_for(self, capability_id: str) -> list[ProviderRecord]:
        rows = self._conn.execute(
            """
            SELECT capability_id, provider_name, provider_kind, model_pack_hash,
                   cost_class, coverage, quality, latency_p50_ms, latency_p95_ms,
                   benchmark_run_id, adopted, notes
              FROM brain_capabilities
             WHERE capability_id=?
             ORDER BY id
            """,
            (capability_id,),
        ).fetchall()
        return [_row_to_record(r) for r in rows]

    def adopted_provider(self, capability_id: str) -> ProviderRecord | None:
        row = self._conn.execute(
            """
            SELECT capability_id, provider_name, provider_kind, model_pack_hash,
                   cost_class, coverage, quality, latency_p50_ms, latency_p95_ms,
                   benchmark_run_id, adopted, notes
              FROM brain_capabilities
             WHERE capability_id=? AND adopted=1
             ORDER BY id
             LIMIT 1
            """,
            (capability_id,),
        ).fetchone()
        return None if row is None else _row_to_record(row)

    def adopted_count(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM brain_capabilities WHERE adopted=1"
        ).fetchone()
        return int(row[0])


def _row_to_record(row) -> ProviderRecord:
    return ProviderRecord(
        capability_id=row[0],
        provider_name=row[1],
        provider_kind=row[2],
        model_pack_hash=row[3],
        cost_class=row[4],
        coverage=row[5],
        quality=row[6],
        latency_p50_ms=row[7],
        latency_p95_ms=row[8],
        benchmark_run_id=row[9],
        adopted=bool(row[10]),
        notes=row[11],
    )
