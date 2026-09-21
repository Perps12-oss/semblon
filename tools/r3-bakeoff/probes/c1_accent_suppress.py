"""C1 — OS accent suppress. Cannot auto-assert without a real shell HWND/theme."""

from __future__ import annotations

from typing import Any


HUMAN_STEPS = [
    "Build or open the candidate shell (WinUI 3 or Qt/PySide6) with Semblon achromatic chrome applied.",
    "Set Windows Settings → Personalization → Colors → Accent color to a vivid non-gray (e.g. magenta).",
    "Exercise native controls: focus ring, list/grid selection, toggle/switch, progress bar/ring.",
    "Photograph or screenshot each control family on light and dark system themes if both are supported.",
    "PASS only if no OS accent appears on focus, selection, toggle, or progress. Any accent bleed = FAIL.",
    "Copy evidence into tools/r3-bakeoff/results/evidence/<toolkit>/c1/ and set criteria[0].evidence_path.",
    "Set criteria[0].pass to true or false in the results JSON (human only). Leave harness status as measured.",
]


def run(ctx: dict[str, Any]) -> dict[str, Any]:
    """Attempt probe. Without a toolkit HWND, record pending_human."""
    toolkit = (ctx.get("toolkit") or "").strip()
    detail = (
        "No HWND/theme API attached in this harness. OS accent suppress requires visual inspection "
        "of the candidate app under a forced Windows accent color."
    )
    if toolkit:
        detail += f" Target toolkit label recorded as {toolkit!r}."

    return {
        "status": "pending_human",
        "pass": None,
        "measurements": {
            "accent_forced": None,
            "controls_checked": ["focus", "selection", "toggle", "progress"],
            "accent_observed": None,
        },
        "notes": detail,
        "human_steps": list(HUMAN_STEPS),
        "probe": {
            "name": "c1_accent_suppress",
            "attempted": True,
            "auto_capable": False,
            "detail": detail,
        },
    }
