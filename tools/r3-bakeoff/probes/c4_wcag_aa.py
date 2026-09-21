"""C4 — WCAG AA on custom controls (both themes).

If --pairs JSON is supplied, compute contrast ratios. Never sets pass; human owns AA coverage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.contrast import aa_pass, contrast_ratio

HUMAN_STEPS = [
    "Enumerate all custom (non-OS-chrome) controls in the candidate shell for light and dark themes.",
    "For each control state (default/hover/press/focus/selected/disabled), record foreground and background #RRGGBB.",
    "Write a JSON array of objects: {\"name\",\"theme\",\"fg\",\"bg\",\"large_text\"?:bool,\"ui_component\"?:bool}.",
    "Example path: tools/r3-bakeoff/results/evidence/<toolkit>/c4/pairs.json",
    "Run: py -3 tools/r3-bakeoff/run_bakeoff.py --toolkit <name> --wcag-pairs <path>",
    "Inspect measurements.pairs[*].ratio and .aa_ok. Any false aa_ok → criterion FAIL once human confirms the pair is in-scope.",
    "PASS only when every custom control in both themes meets WCAG AA. Harness never sets pass.",
]


def _load_pairs(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("wcag pairs file must be a JSON array")
    return data


def run(ctx: dict[str, Any]) -> dict[str, Any]:
    path_str = ctx.get("wcag_pairs_path")
    if not path_str:
        detail = (
            "No --wcag-pairs file. Contrast math is ready; human must supply fg/bg samples from the real app."
        )
        return {
            "status": "pending_human",
            "pass": None,
            "measurements": {"pair_count": 0},
            "notes": detail,
            "human_steps": list(HUMAN_STEPS),
            "probe": {
                "name": "c4_wcag_aa",
                "attempted": True,
                "auto_capable": True,
                "detail": detail,
            },
        }

    path = Path(path_str)
    try:
        raw = _load_pairs(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "status": "error",
            "pass": None,
            "measurements": {},
            "notes": str(exc),
            "human_steps": list(HUMAN_STEPS),
            "probe": {
                "name": "c4_wcag_aa",
                "attempted": True,
                "auto_capable": True,
                "detail": str(exc),
            },
        }

    rows: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        name = str(item.get("name", f"pair_{i}"))
        theme = str(item.get("theme", "unspecified"))
        fg = str(item["fg"])
        bg = str(item["bg"])
        large = bool(item.get("large_text", False))
        ui = bool(item.get("ui_component", False))
        ratio = contrast_ratio(fg, bg)
        ok = aa_pass(ratio, large_text=large, ui_component=ui)
        rows.append(
            {
                "name": name,
                "theme": theme,
                "fg": fg,
                "bg": bg,
                "large_text": large,
                "ui_component": ui,
                "ratio": round(ratio, 3),
                "aa_ok": ok,
            }
        )

    failing = [r["name"] for r in rows if not r["aa_ok"]]
    detail = (
        f"Computed {len(rows)} pair(s); {len(failing)} below AA math threshold. "
        "pass left null — human confirms coverage of all custom controls before recording pass/fail."
    )
    return {
        "status": "measured",
        "pass": None,
        "measurements": {
            "pair_count": len(rows),
            "failing_names": failing,
            "pairs": rows,
        },
        "evidence_path": str(path.resolve()),
        "notes": detail,
        "human_steps": list(HUMAN_STEPS),
        "probe": {
            "name": "c4_wcag_aa",
            "attempted": True,
            "auto_capable": True,
            "detail": detail,
        },
    }
