"""Visual design language — one token vocabulary."""

from __future__ import annotations

import pytest

from semblon import ui_tokens as t


def test_type_scale_sizes_and_family():
    assert t.HERO == ("Segoe UI", 22, "bold")
    assert t.TITLE == ("Segoe UI", 15, "bold")
    assert t.DISPLAY == t.HERO
    assert t.H1 == t.TITLE
    assert t.BODY == ("Segoe UI", 12)
    assert t.BODY_SM == ("Segoe UI", 11)
    assert t.UI == ("Segoe UI", 12)
    assert t.META == ("Segoe UI", 11)
    assert t.CAPTION == ("Segoe UI", 10)
    assert t.STAT == ("Segoe UI", 20, "bold")
    assert t.BODY_STRONG[0] == "Segoe UI"
    assert "bold" not in t.BODY
    assert t.CAPTION[1] >= 10
    assert t.MONO[0] == "Cascadia Code"
    assert t.MONO[1] == 11
    # Product type stays compact — oversized Tk fonts look soft on Windows DPI.
    assert t.HERO[1] <= 24
    assert t.BODY[1] <= 13


def test_spacing_rhythm_4px_base():
    assert (t.SP_4, t.SP_8, t.SP_12, t.SP_16, t.SP_20, t.SP_24, t.SP_32) == (
        4, 8, 12, 16, 20, 24, 32,
    )


def test_color_tokens_match_visual_design():
    light = t.LIGHT
    assert light.text_primary == "#171717"
    assert light.text_secondary == "#565656"
    assert light.text_tertiary == "#8A8A8A"
    assert light.text_quaternary == "#B9B9B9"
    assert light.surface == "#FFFFFF"
    assert light.surface_muted == "#F5F5F4"
    assert light.surface_raised == "#FFFFFF"
    assert light.border == "#E4E4E2"
    assert light.accent == "#2E6BE6"
    assert light.danger == "#C92A2A"
    assert light.warning == "#9C6500"
    assert light.positive == "#1A7F37"
    assert light.focus_ring == "#171717"
    assert t.BG_CANVAS == light.surface
    assert t.ACCENT == light.accent
    assert t.FOCUS_RING == light.focus_ring
    assert t.SIDEBAR_WIDTH == 228
    assert t.RADIUS_BUTTON == 8
    assert t.RADIUS_INPUT == 10
    assert t.RADIUS_CARD == 12
    assert t.RADIUS_PILL == 999
    assert t.BUTTON_RADIUS_PX == 8
    assert t.CONTENT_MAX_WIDTH == 860
    assert t.WINDOW_MIN == (960, 640)
    # Legacy names point at the active palette. No second system.
    assert t.SURFACE_PRIMARY == t.BG_SURFACE
    assert t.TEXT_PRIMARY == t.INK_PRIMARY
    assert t.TEXT_SECONDARY == t.INK_SECONDARY
    assert t.BORDER_FOCUS == t.FOCUS_RING
    assert "#000000" not in (
        t.BG_CANVAS, t.BG_DARK, t.INK_PRIMARY, t.BG_SURFACE,
    )
    hover = light.hover
    assert hover == t.mix(light.text_primary, light.surface, 0.06)
    assert light.active_nav == t.mix(light.text_primary, light.surface, 0.09)
    assert light.chip_accent == t.mix(light.accent, light.surface, 0.14)


def test_button_heights_four_classes():
    assert t.PRIMARY_HEIGHT == 32
    assert t.SECONDARY_HEIGHT == 28
    assert t.TERTIARY_HEIGHT == 24
    assert t.NAV_HEIGHT == 28
    assert t.BUTTON_RADIUS_PX == 8


def test_font_helper_and_pad():
    assert t.font("display") == t.DISPLAY
    assert t.font("BODY_STRONG") == t.BODY_STRONG
    assert t.font("body.small") == t.BODY_SMALL
    assert t.font("mono") == t.MONO
    with pytest.raises(KeyError):
        t.font("headline")
    assert t.pad(t.SP_8) == {"padx": 8, "pady": 8}
    assert t.pad(t.SP_16, t.SP_4) == {"padx": 16, "pady": 4}
    assert t.pad(x=t.SP_12, y=t.SP_8) == {"padx": 12, "pady": 8}
    assert t.tracked("Library") == "L I B R A R Y"


def test_dark_tokens_exist_parallel():
    """DARK mirrors Mica Dark atmosphere (docs/ATMOSPHERE.md)."""
    dark = t.DARK
    assert dark.text_primary == "#FAFAFA"
    assert dark.text_secondary == "#A1A1AA"
    assert dark.text_tertiary == "#71717A"
    assert dark.text_quaternary == "#52525B"
    assert dark.surface == "#121215"
    assert dark.surface_muted == "#161618"
    assert dark.surface_raised == "#1A1A1F"
    assert dark.border == "#27272A"
    assert dark.accent == "#5B8DEF"
    assert dark.danger == "#E5484D"
    assert dark.warning == "#D9A13B"
    assert dark.positive == "#3FB27F"
    assert dark.focus_ring == dark.text_primary
    # Body canvas is deepest stage; chrome is surface one step up.
    assert t.DARK_BG_CANVAS == "#0A0A0C"
    assert t.DARK_BG_CHROME == dark.surface
    assert t.INK_ON_ACCENT == "#0A0A0C"
    assert t.DARK_ACCENT == dark.accent
    css = dark.css_vars()
    assert css["--accent"] == "#5B8DEF"
    assert "QWidget" in t.qt_stylesheet(dark)


def test_dark_publish_splits_canvas_and_chrome():
    """Dark atmospheres: BG_CANVAS = stage, BG_CHROME = surface."""
    from semblon.atmosphere import get_atmosphere

    mica = get_atmosphere("mica_dark")
    t.publish(mica.as_palette())
    assert t.BG_CANVAS == mica.surface_stage == "#0A0A0C"
    assert t.BG_CHROME == mica.surface == "#121215"
    assert t.BG_SURFACE == mica.surface_raised == "#1A1A1F"
    t.publish(t.LIGHT)
    assert t.BG_CANVAS == t.LIGHT.surface
    assert t.BG_CHROME == t.LIGHT.surface
