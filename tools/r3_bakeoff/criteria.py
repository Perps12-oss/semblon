"""Six R3 §6 bake-off criteria — data + unverified measure stubs.

Source of truth: docs/R3-BRIEF.md §6. Stubs never invent PASS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

# Still rejected for the production shell (R3-BRIEF §6 / SEM-ARCH-V1.4).
REJECTED_TOOLKITS: tuple[str, ...] = (
    "Electron",
    "Tauri",
    "permanent Tk AppShell",
    "CustomTkinter",
)


def _unverified_result(criterion_id: str, label: str) -> dict:
    """Stub measurement: no host run → never PASS."""
    return {
        "id": criterion_id,
        "label": label,
        "status": "unverified",
        "verified": False,
        "pass": False,
        "detail": "not measured; stub only",
    }


@dataclass(frozen=True)
class Criterion:
    """One named §6 pass/fail criterion."""

    id: str
    label: str
    measure_fn: Callable[[], dict]


def _stub_measure(criterion_id: str, label: str) -> Callable[[], dict]:
    def _measure() -> dict:
        return _unverified_result(criterion_id, label)

    _measure.__name__ = f"measure_{criterion_id}"
    _measure.__doc__ = f"Stub for {criterion_id}; returns unverified until measured."
    return _measure


def _c(criterion_id: str, label: str) -> Criterion:
    return Criterion(
        id=criterion_id,
        label=label,
        measure_fn=_stub_measure(criterion_id, label),
    )


# Order matches docs/R3-BRIEF.md §6 (1–6).
CRITERIA: tuple[Criterion, ...] = (
    _c(
        "accent_suppress",
        "Fully suppress OS accent in every native control (focus, selection, toggle, progress).",
    ),
    _c(
        "opaque_mica",
        "Opaque achromatic surface over Mica without bleed.",
    ),
    _c(
        "scrub_4k_16ms",
        "< 16 ms frame time on 4K/60 video scrub.",
    ),
    _c(
        "wcag_aa",
        "WCAG AA on all custom controls, both themes.",
    ),
    _c(
        "virtualized_grid_10k",
        "10k-thumbnail virtualized grid without jank.",
    ),
    _c(
        "a11y_tree",
        "Native accessibility tree on custom-drawn surfaces (face boxes, compare cells).",
    ),
)


def criterion_ids() -> list[str]:
    return [c.id for c in CRITERIA]


def default_results() -> list[dict]:
    """Run all stub measure_fns (unverified / not executed)."""
    return [c.measure_fn() for c in CRITERIA]
