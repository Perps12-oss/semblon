"""UX Rescue §1 — ui_tokens vocabulary."""

from __future__ import annotations

import pytest

from semblon import ui_tokens as t


def test_type_scale_sizes_and_family():
    assert t.DISPLAY == ("Segoe UI", 28, "bold")
    assert t.H1 == ("Segoe UI", 20, "bold")
    assert t.H2 == ("Segoe UI", 16, "bold")
    assert t.BODY == ("Segoe UI", 11)
    assert t.BODY_STRONG == ("Segoe UI", 11, "bold")
    assert t.CAPTION == ("Segoe UI", 9)
    assert t.CAPTION_STRONG == ("Segoe UI", 9, "bold")
    assert t.CAPTION[1] >= 9  # nothing user-facing below 9pt


def test_spacing_rhythm_4px_base():
    assert (t.SP_4, t.SP_8, t.SP_12, t.SP_16, t.SP_24, t.SP_32) == (4, 8, 12, 16, 24, 32)


def test_color_tokens_match_ux_rescue_spec():
    assert t.SURFACE_PRIMARY == "#FFFFFF"
    assert t.SURFACE_SECONDARY == "#F5F5F5"
    assert t.SURFACE_DARK == "#1A1A1A"
    assert t.TEXT_PRIMARY == "#1A1A1A"
    assert t.TEXT_SECONDARY == "#6B6B6B"
    assert t.TEXT_DISABLED == "#A0A0A0"
    assert t.ACCENT == "#0A6CFF"
    assert t.ACCENT_HOVER == "#0857CC"
    assert t.ACCENT_PRESSED == "#0645A0"
    assert t.BORDER_SUBTLE == "#E0E0E0"
    assert t.BORDER_FOCUS == "#0A6CFF"
    assert t.SUCCESS == "#0F7B3A"
    assert t.WARNING == "#B25000"


def test_button_heights_three_classes_only():
    assert t.PRIMARY_HEIGHT == 40
    assert t.SECONDARY_HEIGHT == 32
    assert t.TERTIARY_HEIGHT == 28


def test_font_helper_and_pad():
    assert t.font("display") == t.DISPLAY
    assert t.font("BODY_STRONG") == t.BODY_STRONG
    assert t.font("mono") == t.MONO
    with pytest.raises(KeyError):
        t.font("headline")
    assert t.pad(t.SP_8) == {"padx": 8, "pady": 8}
    assert t.pad(t.SP_16, t.SP_4) == {"padx": 16, "pady": 4}
    assert t.pad(x=t.SP_12, y=t.SP_8) == {"padx": 12, "pady": 8}
