"""Visual design language — one token vocabulary."""

from __future__ import annotations

import pytest

from semblon import ui_tokens as t


def test_type_scale_sizes_and_family():
    assert t.DISPLAY == ("Segoe UI Variable Display", 32, "bold")
    assert t.H1 == ("Segoe UI Variable Display", 24, "bold")
    assert t.H2 == ("Segoe UI Variable Text", 18, "bold")
    assert t.H3 == ("Segoe UI Variable Text", 14, "bold")
    assert t.BODY == ("Segoe UI Variable Text", 13)
    assert t.BODY_STRONG == ("Segoe UI Variable Text", 13, "bold")
    assert t.BODY_SMALL == ("Segoe UI Variable Text", 12)
    assert t.CAPTION == ("Segoe UI Variable Text", 11)
    assert t.CAPTION_STRONG == ("Segoe UI Variable Text", 11, "bold")
    assert t.OVERLINE == ("Segoe UI Variable Text", 10, "bold")
    assert t.CAPTION[1] >= 11
    assert t.MONO[0] == "Cascadia Code"
    assert t.MONO[1] == 12


def test_spacing_rhythm_4px_base():
    assert (t.SP_4, t.SP_8, t.SP_12, t.SP_16, t.SP_24, t.SP_32, t.SP_48, t.SP_64) == (
        4, 8, 12, 16, 24, 32, 48, 64,
    )


def test_color_tokens_match_visual_design():
    assert t.BG_CANVAS == "#FBFAF7"
    assert t.BG_SURFACE == "#FFFFFF"
    assert t.BG_SUBTLE == "#F6F4EF"
    assert t.BG_DARK == "#14130F"
    assert t.INK_PRIMARY == "#1A1815"
    assert t.INK_SECONDARY == "#5E5A52"
    assert t.INK_TERTIARY == "#8F8A80"
    assert t.INK_DISABLED == "#B8B3A8"
    assert t.ACCENT == "#4338CA"
    assert t.ACCENT_HOVER == "#3730A3"
    assert t.ACCENT_PRESSED == "#312E81"
    assert t.ACCENT_SUBTLE == "#EEF0FB"
    assert t.SUCCESS == "#15803D"
    assert t.WARNING == "#B45309"
    assert t.DANGER == "#B91C1C"
    assert t.BORDER_SUBTLE == "#E9E6DE"
    assert t.BORDER_DEFAULT == "#DCD8CE"
    # Legacy names point at the same palette. No second system.
    assert t.SURFACE_PRIMARY == t.BG_SURFACE
    assert t.TEXT_PRIMARY == t.INK_PRIMARY
    assert t.TEXT_SECONDARY == t.INK_SECONDARY
    assert t.BORDER_FOCUS == t.ACCENT
    assert "#000000" not in (
        t.BG_CANVAS, t.BG_DARK, t.INK_PRIMARY, t.BG_SURFACE,
    )


def test_button_heights_four_classes():
    assert t.PRIMARY_HEIGHT == 40
    assert t.SECONDARY_HEIGHT == 36
    assert t.TERTIARY_HEIGHT == 28
    assert t.NAV_HEIGHT == 36
    assert t.BUTTON_RADIUS_PX == 6


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
    assert t.DARK_BG_CANVAS == "#14130F"
    assert t.DARK_ACCENT == "#818CF8"
    assert t.DARK_INK_PRIMARY == "#F5F3EE"
