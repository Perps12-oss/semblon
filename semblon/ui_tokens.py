"""Visual design language for the Tk product surfaces.

One token module. Screens import these names; they do not invent a second
palette. Appearance only — no widget trees and no identity or ingest behavior.

Tk has no semibold weight. Weight 600 in the design scale is ``bold``.
Letter-spacing is not a Tk font attribute; overlines add tracking in the
widget that draws them.
"""

from __future__ import annotations

from typing import Any

# Segoe UI Variable on Windows 11. Tk falls back to a default face if the
# family is missing; ``ui_theme.apply_theme`` remaps styles when it can see
# the installed families. Cascadia Code ships with Windows Terminal.
FONT_TEXT = "Segoe UI Variable Text"
FONT_DISPLAY_FAMILY = "Segoe UI Variable Display"
FONT_MONO = "Cascadia Code"
FONT_TEXT_FALLBACK = "Segoe UI"
FONT_MONO_FALLBACK = "Consolas"

FONT_FAMILY = FONT_TEXT
MONO_FAMILY = FONT_MONO

# Role → tk font tuple. Sizes are points (Display 32 / H1 24 / H2 18 / Body 13).
DISPLAY: tuple[str, int, str] = (FONT_DISPLAY_FAMILY, 32, "bold")
H1: tuple[str, int, str] = (FONT_DISPLAY_FAMILY, 24, "bold")
H2: tuple[str, int, str] = (FONT_TEXT, 18, "bold")
H3: tuple[str, int, str] = (FONT_TEXT, 14, "bold")
BODY: tuple[str, int] = (FONT_TEXT, 13)
BODY_STRONG: tuple[str, int, str] = (FONT_TEXT, 13, "bold")
BODY_SMALL: tuple[str, int] = (FONT_TEXT, 12)
CAPTION: tuple[str, int] = (FONT_TEXT, 11)
CAPTION_STRONG: tuple[str, int, str] = (FONT_TEXT, 11, "bold")
OVERLINE: tuple[str, int, str] = (FONT_TEXT, 10, "bold")
MONO: tuple[str, int] = (FONT_MONO, 12)

FONT_ROLES: dict[str, tuple[Any, ...]] = {
    "display": DISPLAY,
    "h1": H1,
    "h2": H2,
    "h3": H3,
    "body": BODY,
    "body_strong": BODY_STRONG,
    "body_small": BODY_SMALL,
    "caption": CAPTION,
    "caption_strong": CAPTION_STRONG,
    "overline": OVERLINE,
    "mono": MONO,
}

# Spacing rhythm (4px base).
SP_4 = 4
SP_8 = 8
SP_12 = 12
SP_16 = 16
SP_24 = 24
SP_32 = 32
SP_48 = 48
SP_64 = 64

# Light mode. Photographs are the only full-spectrum color.
# ``bg.surface`` is the one pure white. Never pure black.
BG_CANVAS = "#FBFAF7"
BG_SURFACE = "#FFFFFF"
BG_SUBTLE = "#F6F4EF"
BG_PRESSED = "#EFEDE7"
BG_INSET = "#F0EDE6"
BG_DARK = "#14130F"
BORDER_SUBTLE = "#E9E6DE"
BORDER_DEFAULT = "#DCD8CE"
BORDER_STRONG = "#C4BFB2"
INK_PRIMARY = "#1A1815"
INK_SECONDARY = "#5E5A52"
INK_TERTIARY = "#8F8A80"
INK_DISABLED = "#B8B3A8"
INK_ON_ACCENT = "#FFFFFF"
# Dark-canvas caption (Canvas / Review preview). Not a second accent.
INK_ON_DARK = "#B5B1A8"
ACCENT = "#4338CA"
ACCENT_HOVER = "#3730A3"
ACCENT_PRESSED = "#312E81"
ACCENT_SUBTLE = "#EEF0FB"
SUCCESS = "#15803D"
WARNING = "#B45309"
DANGER = "#B91C1C"
INFO = "#0369A1"

# Names already imported by Home, Review, diagnostics, and empty states.
SURFACE_PRIMARY = BG_SURFACE
SURFACE_SECONDARY = BG_SUBTLE
SURFACE_DARK = BG_DARK
TEXT_PRIMARY = INK_PRIMARY
TEXT_SECONDARY = INK_SECONDARY
TEXT_DISABLED = INK_DISABLED
BORDER_FOCUS = ACCENT

# Dark mode tokens. Stored so a later appearance switch does not invent a
# second palette. Light mode is what the product applies today.
DARK_BG_CANVAS = "#14130F"
DARK_BG_SURFACE = "#1C1B17"
DARK_BG_SUBTLE = "#232220"
DARK_BG_PRESSED = "#2A2825"
DARK_BG_INSET = "#1F1E1A"
DARK_BORDER_SUBTLE = "#2E2D28"
DARK_BORDER_DEFAULT = "#3A3833"
DARK_BORDER_STRONG = "#4E4B43"
DARK_INK_PRIMARY = "#F5F3EE"
DARK_INK_SECONDARY = "#B5B1A8"
DARK_INK_TERTIARY = "#807B72"
DARK_INK_DISABLED = "#5A564E"
DARK_ACCENT = "#818CF8"
DARK_ACCENT_HOVER = "#A5B4FC"
DARK_ACCENT_PRESSED = "#6366F1"
DARK_ACCENT_SUBTLE = "#1E1B33"

# Button geometry. Four classes, defined once.
PRIMARY_HEIGHT = 40
SECONDARY_HEIGHT = 36
TERTIARY_HEIGHT = 28
NAV_HEIGHT = 36

PRIMARY_PAD_X = 20
PRIMARY_PAD_Y = 10
SECONDARY_PAD_X = 16
SECONDARY_PAD_Y = 8
TERTIARY_PAD_X = 12
TERTIARY_PAD_Y = 4

SECONDARY_FONT: tuple[str, int] = BODY
TERTIARY_FONT: tuple[str, int] = BODY

RADIUS_XS = 4
RADIUS_SM = 6
RADIUS_MD = 10
RADIUS_LG = 14
BUTTON_RADIUS_PX = RADIUS_SM

WINDOW_MIN = (960, 640)
WINDOW_DEFAULT = (1200, 780)
SIDEBAR_WIDTH = 220
INSPECTOR_WIDTH = 300


def font(role: str) -> tuple[Any, ...]:
    """Return a tk font tuple for a named role (``display``, ``h1``, …, ``mono``)."""
    key = role.strip().lower().replace("-", "_").replace(" ", "_").replace(".", "_")
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


def tracked(text: str) -> str:
    """Approximate +0.08em overline tracking. Tk fonts cannot set letter-spacing."""
    chars = [ch for ch in text.upper() if not ch.isspace()]
    return " ".join(chars)
