"""Suggest band — additive to identify confirm threshold. Does not retune confirm.

Band:
  score >= CONFIRM_THRESHOLD              → leave to existing P1 identify path
  SUGGEST_FLOOR <= score < CONFIRM        → outcome='suggested'
  score < SUGGEST_FLOOR or empty gallery  → no suggested row
"""

from __future__ import annotations

# Import confirm from the identity contract — read-only; never assign back.
from semblon.identity_config import DEFAULT_THRESHOLD as CONFIRM_THRESHOLD

# New additive floor. Not a retune of CONFIRM_THRESHOLD / DEFAULT_THRESHOLD.
# provisional_until: 100k pilot — tune on false-suggest rate; 0.40 is a guess.
SUGGEST_FLOOR = 0.40

SUGGEST_REASON = "below_confirm_threshold"
SUGGEST_POLICY_VERSION = (
    f"brain-suggest-v1;confirm={CONFIRM_THRESHOLD};suggest_floor={SUGGEST_FLOOR}"
)


def in_suggest_band(score: float | None) -> bool:
    if score is None:
        return False
    return SUGGEST_FLOOR <= float(score) < CONFIRM_THRESHOLD


def band_reason() -> str:
    return (
        f"{SUGGEST_REASON};confirm={CONFIRM_THRESHOLD};suggest_floor={SUGGEST_FLOOR}"
    )
