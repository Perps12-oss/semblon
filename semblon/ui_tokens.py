"""Toolkit-agnostic visual tokens for Semblon surfaces.

Screens read these names. They do not invent a second palette. Appearance
only — no widget trees and no identity or ingest behavior.

Tk has no weight 500. Hero and title use the bold flag as the nearest
emphasis; body, ui, meta, and caption stay regular (400). Letter-spacing
is not a Tk font attribute.

The previous warm-paper palette (#FBFAF7 / #4338CA) is retired. Light and
dark values below are the product tokens. Qt stylesheets and Tk both read
this module so the optional shell does not become a second Home.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

# System font stack: Segoe UI on Windows, Tk falls back when the family
# is missing. ``ui_theme.apply_theme`` remaps styles from installed families.
FONT_TEXT = "Segoe UI"
FONT_DISPLAY_FAMILY = "Segoe UI"
FONT_MONO = "Cascadia Code"
FONT_TEXT_FALLBACK = "Segoe UI"
FONT_MONO_FALLBACK = "Consolas"

FONT_FAMILY = FONT_TEXT
MONO_FAMILY = FONT_MONO

# Role → tk font tuple. Sizes are points.
# hero 32 / title 20 / body 16 / body-sm 15 / ui 14 / meta 13 / caption 12.
HERO: tuple[str, int, str] = (FONT_TEXT, 32, "bold")
TITLE: tuple[str, int, str] = (FONT_TEXT, 20, "bold")
BODY: tuple[str, int] = (FONT_TEXT, 16)
BODY_SM: tuple[str, int] = (FONT_TEXT, 15)
UI: tuple[str, int] = (FONT_TEXT, 14)
META: tuple[str, int] = (FONT_TEXT, 13)
CAPTION: tuple[str, int] = (FONT_TEXT, 12)
BODY_STRONG: tuple[str, int, str] = (FONT_TEXT, 16, "bold")
# Tabular-looking digits: Tk has no font-variant. Mono is the stand-in
# for counts that update during a scan.
META_TABULAR: tuple[str, int] = (FONT_MONO, 13)

# Legacy role names used by Home, Review, and diagnostics.
DISPLAY: tuple[str, int, str] = HERO
H1: tuple[str, int, str] = TITLE
H2: tuple[str, int, str] = TITLE
H3: tuple[str, int] = UI
BODY_SMALL: tuple[str, int] = BODY_SM
CAPTION_STRONG: tuple[str, int, str] = (FONT_TEXT, 12, "bold")
OVERLINE: tuple[str, int] = CAPTION
MONO: tuple[str, int] = META_TABULAR

FONT_ROLES: dict[str, tuple[Any, ...]] = {
    "hero": HERO,
    "title": TITLE,
    "display": DISPLAY,
    "h1": H1,
    "h2": H2,
    "h3": H3,
    "body": BODY,
    "body_sm": BODY_SM,
    "body_small": BODY_SMALL,
    "body_strong": BODY_STRONG,
    "ui": UI,
    "meta": META,
    "caption": CAPTION,
    "caption_strong": CAPTION_STRONG,
    "overline": OVERLINE,
    "mono": MONO,
}

# Spacing scale (px). 4 / 8 / 12 / 16 / 20 / 24 / 32 only for new chrome.
SP_4 = 4
SP_8 = 8
SP_12 = 12
SP_16 = 16
SP_20 = 20
SP_24 = 24
SP_32 = 32
# Existing landing rhythm still references these. New chrome should not.
SP_48 = 48
SP_64 = 64

# Motion durations (ms). Tk does not animate these; callers that add
# motion should read them and skip when reduced motion is on.
MOTION_FAST_MS = 120
MOTION_MED_MS = 160
MOTION_SLOW_MS = 240

# Geometry.
RADIUS_BUTTON = 8
RADIUS_INPUT = 10
RADIUS_CARD = 12
RADIUS_PILL = 999
RADIUS_XS = 4
RADIUS_SM = RADIUS_BUTTON
RADIUS_MD = RADIUS_INPUT
RADIUS_LG = RADIUS_CARD
BUTTON_RADIUS_PX = RADIUS_BUTTON

WINDOW_MIN = (960, 640)
WINDOW_DEFAULT = (1200, 780)
SIDEBAR_WIDTH = 228
INSPECTOR_WIDTH = 300
CONTENT_MAX_WIDTH = 860
CONTENT_PAD = SP_24

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
TERTIARY_FONT: tuple[str, int] = UI

INK_ON_ACCENT = "#FFFFFF"

# Cluster Review HTML chrome (semblon/review_chrome/tokens.css). Keep in sync.
REVIEW_NAVY_800 = "#0F1B2D"
REVIEW_BG_MAIN = "#F7F8FA"
REVIEW_STRONG_MIN_INTRA = 0.50
REVIEW_SIDEBAR_W = 240
REVIEW_INSPECTOR_W = 360
REVIEW_TOPBAR_H = 64


def mix(src: str, onto: str, amount: float) -> str:
    """Mix ``amount`` of ``src`` into ``onto`` (0 = onto, 1 = src)."""

    def rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    a = rgb(src)
    b = rgb(onto)
    t = min(1.0, max(0.0, amount))
    mixed = tuple(int(round(a[i] * t + b[i] * (1.0 - t))) for i in range(3))
    return "#{:02X}{:02X}{:02X}".format(*mixed)


@dataclass(frozen=True)
class Palette:
    """One appearance. Field names match the CSS custom properties."""

    name: str
    text_primary: str
    text_secondary: str
    text_tertiary: str
    text_quaternary: str
    surface: str
    surface_muted: str
    surface_raised: str
    border: str
    accent: str
    danger: str
    warning: str
    positive: str
    focus_ring: str

    @property
    def hover(self) -> str:
        """6% text-primary on surface."""
        return mix(self.text_primary, self.surface, 0.06)

    @property
    def active_nav(self) -> str:
        """9% text-primary on surface."""
        return mix(self.text_primary, self.surface, 0.09)

    @property
    def chip_accent(self) -> str:
        return mix(self.accent, self.surface, 0.14)

    @property
    def chip_warning(self) -> str:
        return mix(self.warning, self.surface, 0.18)

    @property
    def danger_hover(self) -> str:
        return mix(self.danger, self.surface, 0.10)

    @property
    def chip_positive(self) -> str:
        return mix(self.positive, self.surface, 0.14)

    @property
    def accent_hover(self) -> str:
        """Derived. The spec does not name a second accent."""
        shade = "#FFFFFF" if self.name == "dark" else "#000000"
        return mix(shade, self.accent, 0.12)

    @property
    def accent_pressed(self) -> str:
        shade = "#FFFFFF" if self.name == "dark" else "#000000"
        return mix(shade, self.accent, 0.20)

    def css_vars(self) -> dict[str, str]:
        return {
            "--text-primary": self.text_primary,
            "--text-secondary": self.text_secondary,
            "--text-tertiary": self.text_tertiary,
            "--text-quaternary": self.text_quaternary,
            "--surface": self.surface,
            "--surface-muted": self.surface_muted,
            "--surface-raised": self.surface_raised,
            "--border": self.border,
            "--accent": self.accent,
            "--danger": self.danger,
            "--warning": self.warning,
            "--positive": self.positive,
            "--focus-ring": self.focus_ring,
            "--hover": self.hover,
            "--active-nav": self.active_nav,
            "--chip-accent": self.chip_accent,
            "--chip-warning": self.chip_warning,
            "--danger-hover": self.danger_hover,
            "--chip-positive": self.chip_positive,
        }


LIGHT = Palette(
    name="light",
    text_primary="#171717",
    text_secondary="#565656",
    text_tertiary="#8A8A8A",
    text_quaternary="#B9B9B9",
    surface="#FFFFFF",
    surface_muted="#F5F5F4",
    surface_raised="#FFFFFF",
    border="#E4E4E2",
    accent="#2E6BE6",
    danger="#C92A2A",
    warning="#9C6500",
    positive="#1A7F37",
    focus_ring="#171717",
)

# Dark focus ring is text-primary. The spec lists a focus ring on light only.
DARK = Palette(
    name="dark",
    text_primary="#F1F1F1",
    text_secondary="#B4B4B4",
    text_tertiary="#868686",
    text_quaternary="#5E5E5E",
    surface="#1C1C1D",
    surface_muted="#242425",
    surface_raised="#2B2B2C",
    border="#363637",
    accent="#4C8DFF",
    danger="#E5484D",
    warning="#D9A13B",
    positive="#3FB27F",
    focus_ring="#F1F1F1",
)

_ACTIVE: Palette = LIGHT

# Names already imported by Home, Review, diagnostics, and empty states.
# ``publish`` rebinds these and the same names on already-imported consumers.
BG_CANVAS = LIGHT.surface
BG_SURFACE = LIGHT.surface_raised
BG_SUBTLE = LIGHT.surface_muted
BG_PRESSED = LIGHT.hover
BG_HOVER = LIGHT.hover
BG_INSET = LIGHT.surface_muted
BG_DARK = DARK.surface
BORDER_SUBTLE = LIGHT.border
BORDER_DEFAULT = LIGHT.border
BORDER_STRONG = LIGHT.border
INK_PRIMARY = LIGHT.text_primary
INK_SECONDARY = LIGHT.text_secondary
INK_TERTIARY = LIGHT.text_tertiary
INK_DISABLED = LIGHT.text_quaternary
INK_ON_DARK = DARK.text_secondary
ACCENT = LIGHT.accent
ACCENT_HOVER = LIGHT.accent_hover
ACCENT_PRESSED = LIGHT.accent_pressed
ACCENT_SUBTLE = LIGHT.chip_accent
NAV_ACTIVE = LIGHT.active_nav
SUCCESS = LIGHT.positive
WARNING = LIGHT.warning
DANGER = LIGHT.danger
FOCUS_RING = LIGHT.focus_ring
INFO = LIGHT.accent
SURFACE_PRIMARY = BG_SURFACE
SURFACE_SECONDARY = BG_SUBTLE
TEXT_PRIMARY = INK_PRIMARY
TEXT_SECONDARY = INK_SECONDARY
TEXT_DISABLED = INK_DISABLED
BORDER_FOCUS = FOCUS_RING

# Parallel dark constants for callers that read them without switching.
DARK_BG_CANVAS = DARK.surface
DARK_BG_SURFACE = DARK.surface_raised
DARK_BG_SUBTLE = DARK.surface_muted
DARK_BG_PRESSED = DARK.hover
DARK_BG_INSET = DARK.surface_muted
DARK_BORDER_SUBTLE = DARK.border
DARK_BORDER_DEFAULT = DARK.border
DARK_BORDER_STRONG = DARK.border
DARK_INK_PRIMARY = DARK.text_primary
DARK_INK_SECONDARY = DARK.text_secondary
DARK_INK_TERTIARY = DARK.text_tertiary
DARK_INK_DISABLED = DARK.text_quaternary
DARK_ACCENT = DARK.accent
DARK_ACCENT_HOVER = DARK.accent_hover
DARK_ACCENT_PRESSED = DARK.accent_pressed
DARK_ACCENT_SUBTLE = DARK.chip_accent

_ALIAS_NAMES = (
    "BG_CANVAS",
    "BG_SURFACE",
    "BG_SUBTLE",
    "BG_PRESSED",
    "BG_HOVER",
    "BG_INSET",
    "BG_DARK",
    "BORDER_SUBTLE",
    "BORDER_DEFAULT",
    "BORDER_STRONG",
    "INK_PRIMARY",
    "INK_SECONDARY",
    "INK_TERTIARY",
    "INK_DISABLED",
    "INK_ON_DARK",
    "ACCENT",
    "ACCENT_HOVER",
    "ACCENT_PRESSED",
    "ACCENT_SUBTLE",
    "NAV_ACTIVE",
    "SUCCESS",
    "WARNING",
    "DANGER",
    "FOCUS_RING",
    "INFO",
    "SURFACE_PRIMARY",
    "SURFACE_SECONDARY",
    "TEXT_PRIMARY",
    "TEXT_SECONDARY",
    "TEXT_DISABLED",
    "BORDER_FOCUS",
)

_CONSUMERS = (
    "semblon.ui_widgets",
    "semblon.ui_theme",
    "semblon.home_ui",
    "semblon.canvas",
    "semblon.review_ui",
    "semblon.empty_states",
    "semblon.live_overlay",
    "semblon.advanced_diagnostics",
)


def active_palette() -> Palette:
    return _ACTIVE


def _bind(palette: Palette) -> None:
    """Point the legacy names at ``palette`` inside this module."""
    global _ACTIVE
    global BG_CANVAS, BG_SURFACE, BG_SUBTLE, BG_PRESSED, BG_HOVER, BG_INSET, BG_DARK
    global BORDER_SUBTLE, BORDER_DEFAULT, BORDER_STRONG
    global INK_PRIMARY, INK_SECONDARY, INK_TERTIARY, INK_DISABLED, INK_ON_DARK
    global ACCENT, ACCENT_HOVER, ACCENT_PRESSED, ACCENT_SUBTLE, NAV_ACTIVE
    global SUCCESS, WARNING, DANGER, FOCUS_RING, INFO
    global SURFACE_PRIMARY, SURFACE_SECONDARY, TEXT_PRIMARY, TEXT_SECONDARY
    global TEXT_DISABLED, BORDER_FOCUS

    _ACTIVE = palette
    # Photo stage stays on the dark surface in both appearances so stills
    # are not sitting on the page white.
    stage = DARK.surface
    ink_on_stage = DARK.text_secondary
    BG_CANVAS = palette.surface
    BG_SURFACE = palette.surface_raised
    BG_SUBTLE = palette.surface_muted
    BG_PRESSED = palette.hover
    BG_HOVER = palette.hover
    BG_INSET = palette.surface_muted
    BG_DARK = stage
    BORDER_SUBTLE = palette.border
    BORDER_DEFAULT = palette.border
    BORDER_STRONG = palette.border
    INK_PRIMARY = palette.text_primary
    INK_SECONDARY = palette.text_secondary
    INK_TERTIARY = palette.text_tertiary
    INK_DISABLED = palette.text_quaternary
    INK_ON_DARK = ink_on_stage
    ACCENT = palette.accent
    ACCENT_HOVER = palette.accent_hover
    ACCENT_PRESSED = palette.accent_pressed
    ACCENT_SUBTLE = palette.chip_accent
    NAV_ACTIVE = palette.active_nav
    SUCCESS = palette.positive
    WARNING = palette.warning
    DANGER = palette.danger
    FOCUS_RING = palette.focus_ring
    INFO = palette.accent
    SURFACE_PRIMARY = BG_SURFACE
    SURFACE_SECONDARY = BG_SUBTLE
    TEXT_PRIMARY = INK_PRIMARY
    TEXT_SECONDARY = INK_SECONDARY
    TEXT_DISABLED = INK_DISABLED
    BORDER_FOCUS = FOCUS_RING


def publish(palette: Palette) -> None:
    """Apply ``palette`` to this module and to consumers already imported.

    ``from ui_tokens import ACCENT`` binds a name in the consumer. Rebinding
    here is what lets a theme switch reach the next redraw.
    """
    _bind(palette)
    values = {name: globals()[name] for name in _ALIAS_NAMES}
    for mod_name in _CONSUMERS:
        mod = sys.modules.get(mod_name)
        if mod is None:
            continue
        for name, value in values.items():
            if name in vars(mod):
                setattr(mod, name, value)


def qt_stylesheet(palette: Palette | None = None) -> str:
    """QSS for the optional Qt shell. Not a second product Home."""
    p = palette or active_palette()
    return (
        "QWidget { background: %s; color: %s; font-family: 'Segoe UI'; font-size: 14px; }\n"
        "QLabel { background: transparent; color: %s; }\n"
        "QPushButton { background: %s; color: %s; border: 1px solid %s; "
        "border-radius: 8px; padding: 8px 16px; }\n"
        "QPushButton:hover { background: %s; }\n"
        "QPushButton:focus { border: 1px solid %s; }\n"
        "QListWidget { background: %s; color: %s; border: 1px solid %s; "
        "border-radius: 12px; }\n"
        "QStatusBar { background: %s; color: %s; }\n"
        % (
            p.surface,
            p.text_primary,
            p.text_primary,
            p.surface_raised,
            p.text_primary,
            p.border,
            p.hover,
            p.focus_ring,
            p.surface_raised,
            p.text_primary,
            p.border,
            p.surface_muted,
            p.text_secondary,
        )
    )


def font(role: str) -> tuple[Any, ...]:
    """Return a tk font tuple for a named role (``hero``, ``body``, ``mono``, …)."""
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
    """Build a tk ``pack``/``grid`` padding kwargs dict from spacing tokens."""
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
    """Approximate overline tracking. Tk fonts cannot set letter-spacing."""
    chars = [ch for ch in text.upper() if not ch.isspace()]
    return " ".join(chars)


_bind(LIGHT)
