"""Immutable observation payloads. Graph mutation is out of scope for Inc 1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Region:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class PhotoRef:
    photo_id: str
    path: str | None = None
    content_hash: str | None = None


@dataclass(frozen=True)
class Observation:
    """One provider output. Never mutates the graph by itself."""

    photo_id: str
    capability_id: str
    provider_name: str
    payload: dict[str, Any] = field(default_factory=dict)
    model_pack_hash: str | None = None
    confidence: float | None = None
    region: Region | None = None
    content_hash: str | None = None
