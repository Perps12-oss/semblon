"""P4 — capability handshake with three states only.

Extends existing probes (preflight / category / packs). Does not invent a
second capability framework or schema tables.
"""

from __future__ import annotations

from dataclasses import dataclass

AVAILABLE = "available"
UNAVAILABLE = "unavailable"
INCOMPATIBLE = "incompatible"

CAPABILITY_STATES = frozenset({AVAILABLE, UNAVAILABLE, INCOMPATIBLE})

FACE_INCOMPATIBLE_MESSAGE = (
    "Face recognition paused until update. "
    "Photos will still be indexed for objects, text, and regions. Details."
)

# Notes that mean the files are present but the contract does not match.
_INCOMPATIBLE_MARKERS = (
    "does not match",
    "hash",
    "mismatch",
    "truncated",
    "lfs pointer",
    "unexpected",
    "incompatible",
    "did not load",
    "load failed",
)


@dataclass(frozen=True)
class CapabilityStatus:
    """One capability's handshake result."""

    capability_id: str
    state: str
    provider_id: str
    contract: str
    message: str
    blocks_identity: bool = False

    def __post_init__(self) -> None:
        if self.state not in CAPABILITY_STATES:
            raise ValueError(f"unsupported capability state: {self.state!r}")


def classify_readiness(ready: bool, note: str | None = None) -> str:
    """Map a probe result onto available / unavailable / incompatible."""
    if ready:
        return AVAILABLE
    text = str(note or "").strip().lower()
    if any(marker in text for marker in _INCOMPATIBLE_MARKERS):
        return INCOMPATIBLE
    return UNAVAILABLE


def identity_capability() -> CapabilityStatus:
    """Face identification path only. Other capabilities stay independent."""
    from semblon.engine import (
        ModelPackError,
        assert_face_pack_ready,
        current_identity_space,
        discover_weight_hashes,
    )

    hashes = discover_weight_hashes()
    if not hashes:
        return CapabilityStatus(
            capability_id="identity",
            state=UNAVAILABLE,
            provider_id="yunet_sface",
            contract="",
            message=(
                "Face checking needs the face files already on this computer. "
                "Nothing was downloaded."
            ),
            blocks_identity=True,
        )
    try:
        assert_face_pack_ready()
    except ModelPackError as exc:
        note = str(exc) or "Face pack is not ready."
        state = classify_readiness(False, note)
        return CapabilityStatus(
            capability_id="identity",
            state=state,
            provider_id="yunet_sface",
            contract="",
            message=FACE_INCOMPATIBLE_MESSAGE if state == INCOMPATIBLE else note,
            blocks_identity=True,
        )
    try:
        import cv2
        import numpy as np

        cv2.cvtColor(np.zeros((2, 2, 3), dtype=np.uint8), cv2.COLOR_BGR2GRAY)
    except Exception as exc:  # noqa: BLE001 — load failure is the status
        return CapabilityStatus(
            capability_id="identity",
            state=INCOMPATIBLE,
            provider_id="yunet_sface",
            contract="",
            message=FACE_INCOMPATIBLE_MESSAGE,
            blocks_identity=True,
        )
    space = current_identity_space()
    return CapabilityStatus(
        capability_id="identity",
        state=AVAILABLE,
        provider_id="yunet_sface",
        contract=str(space.get("pack_id") or ""),
        message="",
        blocks_identity=False,
    )


def category_capability(category: str) -> CapabilityStatus:
    """Discover category handshake. People also consult identity_capability."""
    from semblon.category_backfill import (
        CATEGORY_OBJECTS,
        CATEGORY_PEOPLE,
        CATEGORY_REGIONS,
        CATEGORY_WORDS,
        probe_category,
    )

    if category == CATEGORY_PEOPLE:
        identity = identity_capability()
        if identity.state != AVAILABLE:
            return CapabilityStatus(
                capability_id=category,
                state=identity.state,
                provider_id=identity.provider_id,
                contract=identity.contract,
                message=identity.message,
                blocks_identity=True,
            )
    probe = probe_category(category)
    state = getattr(probe, "state", "") or classify_readiness(
        bool(probe.available), probe.reason
    )
    if state not in CAPABILITY_STATES:
        state = AVAILABLE if probe.available else UNAVAILABLE
    message = str(probe.reason or "")
    if state == INCOMPATIBLE and category == CATEGORY_PEOPLE and not message:
        message = FACE_INCOMPATIBLE_MESSAGE
    return CapabilityStatus(
        capability_id=category,
        state=state,
        provider_id=str(probe.provider_id or ""),
        contract=str(probe.provider_version or ""),
        message=message,
        blocks_identity=category == CATEGORY_PEOPLE and state != AVAILABLE,
    )


def capability_manifest() -> list[CapabilityStatus]:
    """Pinned capabilities used by product doors. Identity is listed once."""
    from semblon.category_backfill import (
        CATEGORY_OBJECTS,
        CATEGORY_REGIONS,
        CATEGORY_WORDS,
    )

    rows = [identity_capability()]
    for category in (CATEGORY_OBJECTS, CATEGORY_REGIONS, CATEGORY_WORDS):
        rows.append(category_capability(category))
    return rows


def identity_work_allowed() -> tuple[bool, CapabilityStatus]:
    """Whether face identify / people analysis may run."""
    status = identity_capability()
    return status.state == AVAILABLE, status


def incompatible_notice(statuses: list[CapabilityStatus] | None = None) -> str:
    """Non-blocking, capability-specific copy for the shell notice strip."""
    rows = statuses if statuses is not None else capability_manifest()
    for row in rows:
        if row.state == INCOMPATIBLE and row.blocks_identity:
            return FACE_INCOMPATIBLE_MESSAGE
        if row.state == INCOMPATIBLE and row.message:
            return row.message
    return ""
