"""Appearance file beside the library. Not a schema column."""

from __future__ import annotations

import json

from semblon.atmosphere import get_atmosphere
from semblon.ui_prefs import (
    appearance_path,
    load_theme_mode,
    resolve_atmosphere_id,
    resolve_palette,
    save_theme_mode,
)
from semblon.ui_tokens import LIGHT, publish


def test_missing_file_is_system_and_resolves_light_when_unknown(tmp_path):
    store = tmp_path / "store.sqlite"
    assert load_theme_mode(store) == "system"
    assert resolve_atmosphere_id("system", system_dark=None) == "light"
    assert resolve_atmosphere_id("system", system_dark=False) == "light"
    assert resolve_atmosphere_id("system", system_dark=True) == "mica_dark"
    mica = get_atmosphere("mica_dark")
    dark_pal = resolve_palette("dark")
    assert dark_pal.accent == mica.accent
    assert dark_pal.surface == mica.surface
    assert resolve_palette("nope").accent == LIGHT.accent


def test_save_roundtrip_and_rejects_unknown(tmp_path):
    store = tmp_path / "lib" / "store.sqlite"
    assert save_theme_mode("dark", store) == "dark"
    path = appearance_path(store)
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8"))["theme"] == "dark"
    assert load_theme_mode(store) == "dark"
    assert save_theme_mode("neon", store) == "system"
    assert load_theme_mode(store) == "system"
    assert save_theme_mode("tokyo_synth", store) == "tokyo_synth"
    assert load_theme_mode(store) == "tokyo_synth"


def test_damaged_file_falls_back_to_system(tmp_path):
    store = tmp_path / "store.sqlite"
    appearance_path(store).write_text("{", encoding="utf-8")
    assert load_theme_mode(store) == "system"


def test_publish_rebinds_consumer_names():
    import semblon.ui_tokens as tokens

    from semblon.atmosphere_render import publish_atmosphere

    publish_atmosphere("mica_dark")
    try:
        mica = get_atmosphere("mica_dark")
        assert tokens.ACCENT == mica.accent
        assert tokens.BG_CANVAS == mica.surface_stage
        assert tokens.BG_CHROME == mica.surface
        assert tokens.active_palette().accent == mica.accent
    finally:
        publish(LIGHT)
        publish_atmosphere("light")
    assert tokens.ACCENT == LIGHT.accent
