"""C5 — 10k-thumbnail virtualized grid without jank."""

from __future__ import annotations

from typing import Any

TARGET_COUNT = 10000

HUMAN_STEPS = [
    "Implement or open a virtualized thumbnail grid in the candidate toolkit with ≥ 10 000 items.",
    "Use synthetic placeholders if needed; do not require FaceKit or identity data.",
    "Scroll rapidly through the full range (keyboard page-down / flick) for ≥ 20 s.",
    "Optionally capture UI-thread frame times to a text log and note hitch count (frames > 32 ms).",
    "PASS only if scroll stays visually smooth (no multi-frame stalls) with 10k items bound via virtualization.",
    "FAIL if the toolkit materializes all 10k visuals, or jank is obvious under fast scroll.",
    "Store a short screen recording or PresentMon snippet under results/evidence/<toolkit>/c5/.",
    "Set criteria[4].pass true/false (human). Harness cannot see the grid without a real app.",
]


def run(ctx: dict[str, Any]) -> dict[str, Any]:
    detail = (
        f"No in-process grid host. Need a real WinUI/Qt virtualized list with {TARGET_COUNT} items."
    )
    return {
        "status": "pending_human",
        "pass": None,
        "measurements": {
            "item_count_target": TARGET_COUNT,
            "virtualized": None,
            "jank_observed": None,
        },
        "notes": detail,
        "human_steps": list(HUMAN_STEPS),
        "probe": {
            "name": "c5_virtualized_grid",
            "attempted": True,
            "auto_capable": False,
            "detail": detail,
        },
    }
