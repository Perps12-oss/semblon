"""Central feature gates for Semblon.

**Wired 2026-09-21** after human verify. Product defaults are **ON**.
Opt out with env `0` / `false` / `no` / `off`. This module never writes env vars.

Bake-off runners and CI must still never auto-set SEMBLON_BAKEOFF_WINNER;
the default-ON state records human authorization, not an invented toolkit name.
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
_FALSY = frozenset({"0", "false", "no", "off"})

_HUMAN_NOTES: dict[str, str] = {
    RULED_OUT: (
        "Ruled out WIRED (human verify 2026-09-21). Product default ON. "
        "Opt out: SEMBLON_RULED_OUT=0. Ignore remains a separate verb."
    ),
    LIVE_OVERLAY: (
        "Live overlay WIRED (human verify 2026-09-21). Lab/CLI default ON. "
        "Opt out: SEMBLON_LIVE_OVERLAY=0. Overlay must not write faces.person_id."
    ),
    WIRE_HOME_LIVE: (
        "Home live entry WIRED (human verify 2026-09-21). Explicit Home control; "
        "no auto-start webcam. Opt out: SEMBLON_WIRE_HOME_LIVE=0."
    ),
    MODALITY_PRODUCT: (
        "Modality product surfaces WIRED (human verify 2026-09-21). Settings may "
        "show honesty notes. Observers still never vote on identity. "
        "Opt out: SEMBLON_MODALITY_PRODUCT=0."
    ),
    BAKEOFF_WINNER: (
        "Bake-off gate WIRED (human verify 2026-09-21) — authorization to proceed "
        "to R3 shell decision. Does not invent WinUI vs Qt; human still names the "
        "toolkit in SEM-ARCH. Never auto-set by bake-off runners or CI. "
        "Opt out: SEMBLON_BAKEOFF_WINNER=0."
    ),
}


def _parse_env(raw: str | None) -> bool | None:
    """None = unset (use product default); True/False = explicit."""
    if raw is None:
        return None
    text = raw.strip().lower()
    if text == "":
        return None
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    return False


def enabled(name: str) -> bool:
    """Return whether a gate is active.

    Unknown names fail closed (False).
    Unset env → product default ON (wired).
    Explicit truthy/falsy env overrides the default.
    """
    if name not in _HUMAN_NOTES:
        return False
    parsed = _parse_env(os.environ.get(name))
    if parsed is None:
        return True
    return parsed


def require_human_note(name: str) -> str:
    """Return the human-verify / wiring note for a known gate.

    Raises KeyError for unknown names so callers cannot invent silent flags.
    """
    return _HUMAN_NOTES[name]


def wired_default() -> bool:
    """Product default after human verify (always True for known gates)."""
    return True
