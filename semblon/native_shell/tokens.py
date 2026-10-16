"""Blueprint v3 chrome tokens for the PySide6 shell.

Dark values are the blueprint contract. Light values are derived from them
for the existing ``light`` atmosphere id. Named atmospheres stay persisted
in appearance.json; this module does not invent a second theme stack.

Elevation planes (Phase 1–2 media-first):
  bg0 — L0 canvas (deep cool slate floor)
  bg1 — L1 chrome (nav / panels)
  bg2 — L2 content wells (calendar cells, Field tiles)
  bg3 — lifted hover / segment pill
"""

from __future__ import annotations

DARK = {
    # Phase 2 atmosphere: cool slate-blue charcoal (not flat mica grey).
    "bg0": "#0a0b10",
    "bg1": "#151820",
    "bg2": "#22252d",
    "bg3": "#2c303a",
    "border1": "#2a2f3a",
    "border2": "#3a4150",
    "text1": "#f2f3f5",
    "text2": "#a8adb7",
    "text3": "#6b7280",
    "accent": "#4f8cff",
    "accentDim": "#2b4d8f",
    "danger": "#e5484d",
    "warn": "#f5a524",
    "ok": "#30a46c",
    "review": "#a15cf5",
    "advanced": "#5b6bff",
}

# Derived light. Not a second product palette name.
LIGHT = {
    "bg0": "#f4f5f7",
    "bg1": "#ffffff",
    "bg2": "#eef0f3",
    "bg3": "#e4e7ec",
    "border1": "#d5d9e0",
    "border2": "#c5cad3",
    "text1": "#121417",
    "text2": "#4b5160",
    "text3": "#6b7280",
    "accent": "#2f6fe0",
    "accentDim": "#d6e4ff",
    "danger": "#c5363b",
    "warn": "#b7791f",
    "ok": "#1f7a4d",
    "review": "#7a3ec4",
    "advanced": "#3d4ed6",
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
