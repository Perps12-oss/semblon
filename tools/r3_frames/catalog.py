"""Data catalog of R3 test frames — collision, state-triple, hierarchy.

No GUI. ``generate_catalog()`` returns list[dict] with ids, left/right
states, and the falsification question. Source: ``docs/R3-BRIEF.md`` §7–§8
and ``docs/R3-FRAMES.md``.
"""

from __future__ import annotations

from typing import Any

FRAME_SETS: tuple[str, ...] = (
    "collision_ledger",
    "state_triple",
    "hierarchy",
)

# §7 minimum + fill to ~15 comparison frames (§8.3).
_COLLISION_PAIRS: tuple[tuple[str, str, str], ...] = (
    # Disabled vs Unknown vs Processing — pairwise so all three stay distinct.
    (
        "Disabled",
        "Unknown",
        "Can you tell unavailable (no border) from unresolved (dashed + notch)?",
    ),
    (
        "Unknown",
        "Processing",
        "Can you tell unresolved (dashed + notch) from working (partial ring)?",
    ),
    (
        "Disabled",
        "Processing",
        "Can you tell unavailable (silent, no border) from working (shape-based ring)?",
    ),
    (
        "Possible",
        "Confirmed",
        "Is the link still adjectival Possible, or has the human affirmed Confirmed?",
    ),
    (
        "Ruled out",
        "Ignored",
        "Is this a durable reject (≠) or deferred leave-observation (no border, faded)?",
    ),
    (
        "Paused",
        "Unknown",
        "Does Paused share any visual property with Unknown? (Must not.)",
    ),
    (
        "Failed",
        "Cancelled",
        "Gap+! versus hollow ring + slash — which failure mode is which?",
    ),
    (
        "Queued",
        "Cancelled",
        "Both hollow-ring family — is cancel marked with a slash?",
    ),
    (
        "Completed",
        "Confirmed",
        "Solid ring (job done) versus solid notch (identity affirmed) — same channel?",
    ),
    (
        "Stale",
        "Ignored",
        "Dotted ring (stale work) versus no-border fade (human deferred) — distinguishable?",
    ),
    (
        "Possible",
        "Unknown",
        "Weak evidence asking vs no evidence asking — textures still differ?",
    ),
    (
        "Armed destructive",
        "Error",
        "Red on the object (armed) versus red chrome/error — not the same?",
    ),
    (
        "Selected",
        "Focus",
        "Inset/notch selection versus focus ring offset — still separate?",
    ),
    (
        "Loading",
        "Processing",
        "Control spinner versus observation-layer processing ring — collapsible?",
    ),
    (
        "Paused",
        "Disabled",
        "Static partial ring + pause bar versus 40% inert control — still distinct?",
    ),
)

# §8.4 — 5 ingest × 6 analysis; identity notch stepped through 5 display values.
_INGEST_STATUSES: tuple[str, ...] = (
    "queued",
    "running",
    "paused",
    "completed",
    "failed",
)

_ANALYSIS_STATUSES: tuple[str, ...] = (
    "none",
    "detecting",
    "detected",
    "embedding",
    "clustered",
    "stale",
)

_IDENTITY_NOTCHES: tuple[str, ...] = (
    "Unknown",
    "Possible",
    "Confirmed",
    "Ruled out",
    "Ignored",
)


def _collision_frames() -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for i, (left, right, question) in enumerate(_COLLISION_PAIRS, start=1):
        frames.append(
            {
                "id": f"collision-{i:02d}",
                "set": "collision_ledger",
                "left": left,
                "right": right,
                "question": question,
            }
        )
    return frames


def _state_triple_frames() -> list[dict[str, Any]]:
    """30 cards: one ingest×analysis cell per card; notch stepped 0..4."""
    frames: list[dict[str, Any]] = []
    n = 0
    for ingest in _INGEST_STATUSES:
        for analysis in _ANALYSIS_STATUSES:
            notch = _IDENTITY_NOTCHES[n % len(_IDENTITY_NOTCHES)]
            n += 1
            frames.append(
                {
                    "id": f"triple-{n:02d}",
                    "set": "state_triple",
                    "left": f"ingest={ingest}",
                    "right": f"analysis={analysis} | notch={notch}",
                    "question": (
                        "If two cards look alike, which channel changed — "
                        "ingest, analysis, or identity notch?"
                    ),
                    "ingest": ingest,
                    "analysis": analysis,
                    "notch": notch,
                }
            )
    return frames


def _hierarchy_frames() -> list[dict[str, Any]]:
    """Clickable IA frames — §8.6 last; catalog only until VERIFY."""
    pairs: tuple[tuple[str, str, str], ...] = (
        (
            "Library media row",
            "People / Unknown observation",
            "Source-media layer versus identity-observation layer — still separate?",
        ),
        (
            "Evidence relationship",
            "Proposed action",
            "Group Inspector: machine similarity vs human Merge/Assign — buttons split?",
        ),
        (
            "Merge observations",
            "Assign to person",
            "Does chrome imply Semblon already knows these are the same person?",
        ),
        (
            "Unknown nested triage",
            "Top-level Unknown chrome",
            "Is Unknown nested under People, not a second product Home?",
        ),
        (
            "Compare ≤8 entry",
            "Compare >8 progressive",
            "Banner + prune in place versus hard refuse above 8?",
        ),
    )
    frames: list[dict[str, Any]] = []
    for i, (left, right, question) in enumerate(pairs, start=1):
        frames.append(
            {
                "id": f"hierarchy-{i:02d}",
                "set": "hierarchy",
                "left": left,
                "right": right,
                "question": question,
                "note": "§8.6 last — do not wire before collision + triple VERIFY",
            }
        )
    return frames


def generate_catalog() -> list[dict[str, Any]]:
    """Return the full frame catalog (collision + state-triple + hierarchy)."""
    return _collision_frames() + _state_triple_frames() + _hierarchy_frames()
