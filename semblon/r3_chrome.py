"""R3 chrome vocabulary — toolkit-agnostic.

Implements display-state + processing grammar from `docs/R3-BRIEF.md`.
Consumable by Tk Home (compatibility frontend), future native shell, or tests.

Does **not** name WinUI vs Qt. Does **not** promote PySide. Does **not** turn
Tk Home into the permanent AppShell (SEM-ARCH §E).
Shell winner naming stays `docs/r3-artifacts/07-shell-decision.md` (blank / OPEN).
"""

from __future__ import annotations

from typing import Literal

# Evidence axis (machine) — R3-BRIEF §1
Evidence = Literal["none", "detected", "similar", "clustered"]

# Decision axis (human) — R3-BRIEF §1
Decision = Literal["undecided", "affirmed", "rejected", "deferred"]

# Five display states — R3-BRIEF §1 matrix
DisplayState = Literal["Unknown", "Possible", "Confirmed", "Ruled out", "Ignored"]

DISPLAY_STATES: tuple[DisplayState, ...] = (
    "Unknown",
    "Possible",
    "Confirmed",
    "Ruled out",
    "Ignored",
)

# Visual grammar tokens (not toolkit widgets) — R3-BRIEF §1
BORDER_TEXTURE: dict[DisplayState, str] = {
    "Unknown": "dashed-6/4",
    "Possible": "dashed-3/2",
    "Confirmed": "solid",
    "Ruled out": "dashed-6/4+≠",
    "Ignored": "none@35%",
}

NOTCH: dict[DisplayState, str] = {
    "Unknown": "empty-outline",
    "Possible": "half-filled",
    "Confirmed": "solid",
    "Ruled out": "empty+slash",
    "Ignored": "none",
}

# Processing grammar — shape, not hue (R3-BRIEF §2)
ProcessingGlyph = Literal[
    "hollow-ring",
    "partial-ring-sweep",
    "partial-ring-paused",
    "solid-ring",
    "ring-gap-bang",
    "hollow-ring-slash",
    "dotted-ring",
]

PROCESSING_GLYPH: dict[str, ProcessingGlyph] = {
    "queued": "hollow-ring",
    "started": "partial-ring-sweep",
    "progress": "partial-ring-sweep",
    "partial": "partial-ring-sweep",
    "paused": "partial-ring-paused",
    "completed": "solid-ring",
    "failed": "ring-gap-bang",
    "cancelled": "hollow-ring-slash",
    "stalled": "dotted-ring",
}

# Impossible cells in the display matrix are None.
_MATRIX: dict[tuple[Evidence, Decision], DisplayState | None] = {
    ("none", "undecided"): "Unknown",
    ("none", "affirmed"): None,
    ("none", "rejected"): None,
    ("none", "deferred"): "Ignored",
    ("detected", "undecided"): "Possible",
    ("detected", "affirmed"): "Confirmed",
    ("detected", "rejected"): "Ruled out",
    ("detected", "deferred"): "Ignored",
    ("similar", "undecided"): "Possible",
    ("similar", "affirmed"): "Confirmed",
    ("similar", "rejected"): "Ruled out",
    ("similar", "deferred"): "Ignored",
    ("clustered", "undecided"): "Possible",
    ("clustered", "affirmed"): "Confirmed",
    ("clustered", "rejected"): "Ruled out",
    ("clustered", "deferred"): "Ignored",
}

LIBRARY_LAYER = "Library is the source-media layer."
OBSERVATION_LAYER = "People/Unknown is the identity-observation layer."
IA_SPLIT = f"{LIBRARY_LAYER} {OBSERVATION_LAYER}"

SHELL_CHROME_NOTE = (
    "R3 chrome vocabulary is toolkit-agnostic. "
    "Tk Home is a compatibility frontend — not the permanent AppShell. "
    "Shell toolkit winner is unnamed until §I.5 / 07-shell-decision."
)


def display_state(evidence: Evidence, decision: Decision) -> DisplayState:
    """Map evidence × decision → five display states. Raises on impossible cells."""
    cell = _MATRIX.get((evidence, decision))
    if cell is None:
        raise ValueError(f"impossible display cell: evidence={evidence!r} decision={decision!r}")
    return cell


def processing_glyph(kind: str, *, paused: bool = False) -> ProcessingGlyph:
    """Shape-based processing token. Paused overrides in-flight kinds."""
    if paused and kind in {"started", "progress", "partial", "queued"}:
        return "partial-ring-paused"
    return PROCESSING_GLYPH.get(kind, "partial-ring-sweep")


def evidence_from_face(face: dict) -> Evidence:
    """Evidence axis only — never treat person_id as evidence chrome."""
    status = str(face.get("status") or "").lower()
    if status and status not in {"ok", ""}:
        return "none"
    if face.get("cluster_id"):
        return "clustered"
    # Detected face observation without a group hypothesis.
    if face.get("face_id") or face.get("bbox") or face.get("bbox_x1") is not None:
        return "detected"
    return "none"


def decision_from_face(face: dict, *, policy_action: str | None = None) -> Decision:
    """Decision axis from person link + optional policy action (ignore / rule_out)."""
    action = (policy_action or face.get("policy_action") or "").lower()
    if action == "rule_out":
        return "rejected"
    if action == "ignore" or face.get("ignored") or face.get("hidden"):
        return "deferred"
    if face.get("person_id"):
        return "affirmed"
    return "undecided"


def face_display_state(face: dict, *, policy_action: str | None = None) -> DisplayState:
    """Five-state label for a face observation. Cluster ≠ person."""
    return display_state(
        evidence_from_face(face),
        decision_from_face(face, policy_action=policy_action),
    )


def face_evidence_label(face: dict) -> str:
    """Brief evidence-axis token for overlay tags (not a decision)."""
    return evidence_from_face(face)


def chrome_legend_lines() -> list[str]:
    """Inspector/help lines — IA + display states; no toolkit name."""
    return [
        IA_SPLIT,
        "Display states: " + " · ".join(DISPLAY_STATES),
        "Evidence axis ≠ decision axis. Wrong identity > unknown.",
        "Processing uses shape (ring grammar), not hue.",
        SHELL_CHROME_NOTE,
    ]
