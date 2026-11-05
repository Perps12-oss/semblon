"""Capability arbitration over real observations — Inc 2 entry point."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from semblon.brain.cache import PersistEvidenceCache
from semblon.brain.evidence import WriteResult, record_observations
from semblon.brain.observer import BrainObserver
from semblon.brain.policy import BrainPolicy, Selection, SelectionContext
from semblon.brain.observation import PhotoRef


@dataclass(frozen=True)
class PipelineResult:
    selection: Selection
    write: WriteResult | None


class BrainPipeline:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: str,
        policy: BrainPolicy | None = None,
    ) -> None:
        self._conn = conn
        self._run_id = run_id
        self._cache = PersistEvidenceCache(conn)
        self._policy = policy or BrainPolicy(cache=self._cache)

    @property
    def cache(self) -> PersistEvidenceCache:
        return self._cache

    def run_observer(
        self,
        observer: BrainObserver,
        photo: PhotoRef,
        *,
        capability_needed: bool = True,
        registered_providers: dict[str, list[str]] | None = None,
    ) -> PipelineResult:
        cap = observer.capability_id
        ctx = SelectionContext(
            photo=photo,
            capability_needed=capability_needed,
            registered_providers=registered_providers
            or {cap: [observer.provider_name]},
        )
        # Persist cache drives reuse via has_observation.
        selection = self._policy.select(cap, ctx)
        if selection.action == "reuse":
            existing = self._cache.existing_observation(
                photo.photo_id, cap, observer.model_pack_hash
            )
            oid = None
            if existing is not None:
                row = self._conn.execute(
                    """SELECT id FROM brain_observations
                       WHERE media_id=? AND capability_id=?
                         AND IFNULL(model_pack_hash, '')=IFNULL(?, '')""",
                    (photo.photo_id, cap, observer.model_pack_hash),
                ).fetchone()
                oid = int(row[0]) if row else None
            return PipelineResult(
                selection,
                WriteResult(
                    observation_ids=[oid] if oid is not None else [],
                    evidence_ids=[],
                    evaluation_ids=[],
                    reused=True,
                ),
            )
        if selection.action != "invoke":
            return PipelineResult(selection, None)

        observations = observer.observe(photo)
        if not observations:
            return PipelineResult(selection, WriteResult([], [], [], reused=False))
        write = record_observations(
            self._conn,
            observations,
            run_id=self._run_id,
            write_tagged=(cap == "C1"),
        )
        return PipelineResult(selection, write)
