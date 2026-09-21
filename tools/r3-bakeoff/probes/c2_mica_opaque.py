"""C2 — Opaque achromatic surface over Mica without bleed."""

from __future__ import annotations

from typing import Any


HUMAN_STEPS = [
    "Enable Mica (or system backdrop) on the shell window where OS build supports it.",
    "Place an opaque achromatic Surface-0 / media panel over the Mica backdrop (desktop wallpaper visible elsewhere).",
    "Change desktop wallpaper to high-chroma content; confirm the opaque panel does not tint or bleed wallpaper color.",
    "Sample panel pixels (Snipping Tool + color picker or PIX/GPU capture). Record mean RGB; chroma must stay near zero.",
    "PASS only if the overlay stays opaque and achromatic with no Mica/wallpaper bleed. Soft translucency that shifts hue = FAIL.",
    "Store screenshots under tools/r3-bakeoff/results/evidence/<toolkit>/c2/ and set evidence_path.",
    "Set criteria[1].pass true/false (human). Harness does not decide.",
]


def run(ctx: dict[str, Any]) -> dict[str, Any]:
    detail = (
        "Requires a live WinUI/Qt window with DWM backdrop. Harness records steps only; "
        "optional later: attach HWND and sample client pixels."
    )
    return {
        "status": "pending_human",
        "pass": None,
        "measurements": {
            "mica_enabled": None,
            "panel_mean_rgb": None,
            "bleed_detected": None,
        },
        "notes": detail,
        "human_steps": list(HUMAN_STEPS),
        "probe": {
            "name": "c2_mica_opaque",
            "attempted": True,
            "auto_capable": False,
            "detail": detail,
        },
    }
