"""C6 — Native accessibility tree on custom-drawn surfaces."""

from __future__ import annotations

from typing import Any


HUMAN_STEPS = [
    "Draw face-box overlays and Compare cells with the candidate toolkit’s custom visuals (not plain TextBlocks alone).",
    "Open Windows Accessibility Insights (or Inspect.exe / Narrator) against the live window.",
    "Confirm each face box and compare cell appears in the UIA tree with name/role (or toolkit equivalent) and correct bounds.",
    "Tab/arrow through overlays; screen reader must announce identity-display state without inventing a person conclusion.",
    "PASS only if custom-drawn surfaces are in the native a11y tree. Canvas-only pixels with no peers = FAIL.",
    "Export Accessibility Insights HTML/JSON under results/evidence/<toolkit>/c6/ and set evidence_path.",
    "Set criteria[5].pass true/false (human).",
]


def run(ctx: dict[str, Any]) -> dict[str, Any]:
    detail = (
        "UIA tree walk needs a live HWND and AutomationElement peers. Harness ships steps only; "
        "optional later: comtypes/UIAutomationClient probe against --hwnd."
    )
    return {
        "status": "pending_human",
        "pass": None,
        "measurements": {
            "face_box_peers": None,
            "compare_cell_peers": None,
            "narrator_smoke": None,
        },
        "notes": detail,
        "human_steps": list(HUMAN_STEPS),
        "probe": {
            "name": "c6_a11y_tree",
            "attempted": True,
            "auto_capable": False,
            "detail": detail,
        },
    }
