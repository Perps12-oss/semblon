"""BrainObserver protocol. Increment 1 ships the protocol only — no adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from semblon.brain.observation import Observation, PhotoRef, Region


@runtime_checkable
class BrainObserver(Protocol):
    capability_id: str
    provider_name: str
    model_pack_hash: str | None

    def observe(
        self,
        photo: PhotoRef,
        regions: list[Region] | None = None,
    ) -> list[Observation]:
        """Emit immutable observations. Never mutates the graph."""
        ...
