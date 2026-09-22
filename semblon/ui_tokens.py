"""UX Rescue §1 — global design tokens for tk/ttk Home.

Additive vocabulary only. Does not construct widgets or change identity/ingest.
Hex values match the Semblon UX Rescue specification (light chrome + dark canvas).

Tk note: Segoe UI "Semibold" is expressed as weight ``bold`` in font tuples —
ttk/Tk on Windows does not expose a portable ``semibold`` weight token.
"""

from __future__ import annotations

from typing import Any

# ── Type scale (Segoe UI) ───────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"

# Role → tk font tuple. Sizes: Display 28 / H1 20 / H2 16 / Body 11 / Caption 9.
DISPLAY: tuple[str, int, str] = (FONT_FAMILY, 28, "bold")
H1: tuple[str, int, str] = (FONT_FAMILY, 20, "bold")  # Semibold in spec
H2: tuple[str, int, str] = (FONT_FAMILY, 16, "bold")  # Semibold in spec
BODY: tuple[str, int] = (FONT_FAMILY, 11)
BODY_STRONG: tuple[str, int, str] = (FONT_FAMILY, 11, "bold")  # Semibold in spec
CAPTION: tuple[str, int] = (FONT_FAMILY, 9)
CAPTION_STRONG: tuple[str, int, str] = (FONT_FAMILY, 9, "bold")  # Semibold in spec

# Diagnostics / paths / IDs (UX Rescue §7 visual: Consolas 10).
MONO: tuple[str, int] = (MONO_FAMILY, 10)

FONT_ROLES: dict[str, tuple[Any, ...]] = {
    "display": DISPLAY,
    "h1": H1,
    "h2": H2,
    "body": BODY,
    "body_strong": BODY_STRONG,
    "caption": CAPTION,
    "caption_strong": CAPTION_STRONG,
    "mono": MONO,
}

# ── Spacing rhythm (4px base) ───────────────────────────────────────────────
SP_4 = 4
SP_8 = 8
SP_12 = 12
SP_16 = 16
SP_24 = 24
SP_32 = 32

# ── Color tokens (exact UX Rescue hex) ──────────────────────────────────────
SURFACE_PRIMARY = "#FFFFFF"
SURFACE_SECONDARY = "#F5F5F5"
SURFACE_DARK = "#1A1A1A"
TEXT_PRIMARY = "#1A1A1A"
TEXT_SECONDARY = "#6B6B6B"
TEXT_DISABLED = "#A0A0A0"
ACCENT = "#0A6CFF"
ACCENT_HOVER = "#0857CC"
ACCENT_PRESSED = "#0645A0"
BORDER_SUBTLE = "#E0E0E0"
BORDER_FOCUS = "#0A6CFF"
SUCCESS = "#0F7B3A"
WARNING = "#B25000"

# ── Button geometry (three classes only) ────────────────────────────────────
# Primary: height 40, pad 20×10, BODY_STRONG, accent bg / white text.
# Secondary: height 32, pad 16×6, Segoe 10 regular, white bg + subtle border.
# Tertiary: height 28, pad 12×4, Segoe 10 regular, no chrome; text-secondary.
PRIMARY_HEIGHT = 40
SECONDARY_HEIGHT = 32
TERTIARY_HEIGHT = 28

PRIMARY_PAD_X = 20
PRIMARY_PAD_Y = 10
SECONDARY_PAD_X = 16
SECONDARY_PAD_Y = 6
TERTIARY_PAD_X = 12
TERTIARY_PAD_Y = 4

SECONDARY_FONT: tuple[str, int] = (FONT_FAMILY, 10)
TERTIARY_FONT: tuple[str, int] = (FONT_FAMILY, 10)

BUTTON_RADIUS_PX = 6  # Intent; ttk may approximate with flat + focus border.


def font(role: str) -> tuple[Any, ...]:
    """Return a tk font tuple for a named role (``display``, ``h1``, …, ``mono``)."""
    key = role.strip().lower().replace("-", "_").replace(" ", "_")
    try:
        return FONT_ROLES[key]
    except KeyError as e:
        raise KeyError(f"unknown font role {role!r}; known={sorted(FONT_ROLES)}") from e


def pad(
    *values: int,
    x: int | None = None,
    y: int | None = None,
    padx: int | None = None,
    pady: int | None = None,
) -> dict[str, int]:
    """Build a tk ``pack``/``grid`` padding kwargs dict from spacing tokens.

    Examples::

        pad(SP_8)           → {"padx": 8, "pady": 8}
        pad(SP_16, SP_8)    → {"padx": 16, "pady": 8}
        pad(x=SP_12, y=SP_4)
    """
    if values:
        if len(values) == 1:
            return {"padx": values[0], "pady": values[0]}
        if len(values) == 2:
            return {"padx": values[0], "pady": values[1]}
        raise TypeError("pad() accepts 1 or 2 positional spacing values")
    out: dict[str, int] = {}
    px = padx if padx is not None else x
    py = pady if pady is not None else y
    if px is not None:
        out["padx"] = px
    if py is not None:
        out["pady"] = py
    return out
