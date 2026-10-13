"""Quiet Studio chrome tokens for the PySide6 shell.

Cool near-monochrome values mapped onto the existing token keys. The accent
is a moonlight edge, not a fill. Light values are the cool paper pair for
the existing ``light`` atmosphere id. Named atmospheres stay persisted in
appearance.json; this module does not invent a second theme stack.
"""

from __future__ import annotations

DARK = {
    "bg0": "#0f1015",
    "bg1": "#161821",
    "bg2": "#1d1f29",
    "bg3": "#262932",
    "border1": "#2a2e38",
    "border2": "#3a3f4c",
    "text1": "#e7eaf0",
    "text2": "#aeb3bf",
    "text3": "#80858f",
    "accent": "#9eb3d4",
    "accentDim": "#2c3a4e",
    "danger": "#c47373",
    "warn": "#c4a36a",
    "ok": "#7ea291",
    "review": "#8e7aab",
    "advanced": "#8ea0c4",
}

# Cool paper. Not a second product palette name.
LIGHT = {
    "bg0": "#f4f5f3",
    "bg1": "#fafaf8",
    "bg2": "#ebeceb",
    "bg3": "#dee0dd",
    "border1": "#d2d4d2",
    "border2": "#c5c8c5",
    "text1": "#15171c",
    "text2": "#3a3d44",
    "text3": "#797d85",
    "accent": "#466996",
    "accentDim": "#d7e3f0",
    "danger": "#a85a5a",
    "warn": "#8a6a32",
    "ok": "#4f6f5e",
    "review": "#6d5a86",
    "advanced": "#3d5a7a",
}

# Blueprint sizes. Cozy is the shell default when the prefs key is absent.
# Shared load_grid_density() still falls back to comfortable for other clients.
DENSITY_PX = {
    "comfortable": 220,
    "cozy": 160,
    "compact": 110,
}
SHELL_DENSITY_DEFAULT = "cozy"
FONT_STACK = "Segoe UI Variable, Segoe UI, sans-serif"


def tokens_for(atmosphere_id: str | None) -> dict[str, str]:
    if str(atmosphere_id or "").strip().lower() == "light":
        return dict(LIGHT)
    return dict(DARK)


def cell_size(density: str | None) -> int:
    key = str(density or SHELL_DENSITY_DEFAULT).strip().lower()
    return int(DENSITY_PX.get(key, DENSITY_PX[SHELL_DENSITY_DEFAULT]))
