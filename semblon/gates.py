"""Central feature gates for Semblon scaffolds.

All gated features default OFF. Human verify authorizes wiring
(flipping defaults / Home entry). Other agents import helpers here;
do not invent parallel env checks.

This module never writes env vars. SEMBLON_BAKEOFF_WINNER must not
be auto-set by bake-off tooling or CI.
"""

from __future__ import annotations

import os

# Canonical env names — import these; do not hard-code strings elsewhere.
RULED_OUT = "SEMBLON_RULED_OUT"
LIVE_OVERLAY = "SEMBLON_LIVE_OVERLAY"
WIRE_HOME_LIVE = "SEMBLON_WIRE_HOME_LIVE"
MODALITY_PRODUCT = "SEMBLON_MODALITY_PRODUCT"
BAKEOFF_WINNER = "SEMBLON_BAKEOFF_WINNER"

KNOWN_FLAGS: tuple[str, ...] = (
    RULED_OUT,
    LIVE_OVERLAY,
    WIRE_HOME_LIVE,
    MODALITY_PRODUCT,
    BAKEOFF_WINNER,
)

_TRUTHY = frozenset({"1", "true", "yes", "on"})

_HUMAN_NOTES: dict[str, str] = {
    RULED_OUT: (
        "Ruled-out scaffold only. Human must verify reject-vs-ignore semantics "
        "(action=rule_out under kind=reject, board visibility, optional person_id) "
        "before product wire. Set SEMBLON_RULED_OUT=1 to exercise the scaffold."
    ),
    LIVE_OVERLAY: (
        "Live overlay scaffold only. Human must verify real webcam/RTSP with two "
        "simultaneous people (stable track ids + ACCEPT/UNKNOWN) before Home wiring. "
        "Set SEMBLON_LIVE_OVERLAY=1 for lab/CLI. Overlay must not write faces.person_id."
    ),
    WIRE_HOME_LIVE: (
        "Stronger gate: Home live entry. Flip only after SEMBLON_LIVE_OVERLAY human "
        "verify passes. Set SEMBLON_WIRE_HOME_LIVE=1 to show/launch overlay from Home. "
        "Default OFF; do not enable with overlay alone."
    ),
    MODALITY_PRODUCT: (
        "Modality product surfaces (non-identity observers as product UI). Flip only "
        "after honesty verify that extra observers never vote on identity / faces.person_id. "
        "Set SEMBLON_MODALITY_PRODUCT=1 to expose product chrome."
    ),
    BAKEOFF_WINNER: (
        "R3 bake-off winner selection. Must be set only by explicit human decision — "
        "never auto-set by bake-off runners, probes, or CI. Set SEMBLON_BAKEOFF_WINNER=1 "
        "only after human names a winner."
    ),
}


def _truthy(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.strip().lower() in _TRUTHY


def enabled(name: str) -> bool:
    """Return True only when the named gate env var is explicitly truthy.

    Unknown names are False (fail closed). Never defaults On.
    """
    if name not in _HUMAN_NOTES:
        return False
    return _truthy(os.environ.get(name))


def require_human_note(name: str) -> str:
    """Return the human-verify note for a known gate.

    Raises KeyError for unknown names so callers cannot invent silent flags.
    """
    return _HUMAN_NOTES[name]
