"""Blueprint v3 chrome tokens for the PySide6 shell.

Dark values are the blueprint fallback before the bridge is ready. The shell
paints a chosen atmosphere from ``semblon.atmosphere``, not from ``DARK``.

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


def _hex(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text.startswith("#"):
        text = "#" + text
    if len(text) == 4:
        text = "#" + "".join(ch * 2 for ch in text[1:])
    return text


def tokens_for(atmosphere_id: str | None) -> dict[str, str]:
    """Shell colors for one stored atmosphere. Unknown ids stay Mica Dark."""
    from semblon.atmosphere import ATMOSPHERES, get_atmosphere

    raw = str(atmosphere_id or "").strip().lower()
    if raw == "dark":
        raw = "mica_dark"
    if raw not in ATMOSPHERES:
        raw = "mica_dark"
    spec = get_atmosphere(raw)
    return {
        "bg0": _hex(spec.surface_muted),
        "bg1": _hex(spec.surface),
        "bg2": _hex(spec.surface_inset),
        "bg3": _hex(spec.surface_raised),
        "border1": _hex(spec.border),
        "border2": _hex(spec.border_strong),
        "text1": _hex(spec.text_primary),
        "text2": _hex(spec.text_secondary),
        "text3": _hex(spec.text_tertiary),
        "accent": _hex(spec.accent),
        "accentDim": _hex(spec.mist),
        "danger": _hex(spec.danger),
        "warn": _hex(spec.warning),
        "ok": _hex(spec.positive),
        "review": _hex(spec.accent_b),
        "advanced": _hex(spec.accent_b),
    }


def cell_size(density: str | None) -> int:
    key = str(density or SHELL_DENSITY_DEFAULT).strip().lower()
    return int(DENSITY_PX.get(key, DENSITY_PX[SHELL_DENSITY_DEFAULT]))
