"""Appearance file beside the library. Not a schema column."""

from __future__ import annotations

import json

from semblon.ui_prefs import (
    appearance_path,
    load_theme_mode,
    resolve_palette,
    save_theme_mode,
)
from semblon.ui_tokens import DARK, LIGHT, publish


def test_missing_file_is_system_and_resolves_light_when_unknown(tmp_path):
    store = tmp_path / "store.sqlite"
    assert load_theme_mode(store) == "system"
    assert resolve_palette("system", system_dark=None) is LIGHT
    assert resolve_palette("system", system_dark=False) is LIGHT
    assert resolve_palette("system", system_dark=True) is DARK
    assert resolve_palette("dark") is DARK
    assert resolve_palette("nope") is LIGHT


def test_save_roundtrip_and_rejects_unknown(tmp_path):
    store = tmp_path / "lib" / "store.sqlite"
    assert save_theme_mode("dark", store) == "dark"
    path = appearance_path(store)
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == {"theme": "dark"}
    assert load_theme_mode(store) == "dark"
    assert save_theme_mode("neon", store) == "system"
    assert load_theme_mode(store) == "system"


def test_damaged_file_falls_back_to_system(tmp_path):
    store = tmp_path / "store.sqlite"
    appearance_path(store).write_text("{", encoding="utf-8")
    assert load_theme_mode(store) == "system"


def test_publish_rebinds_consumer_names():
    import semblon.ui_tokens as tokens

    publish(DARK)
    try:
        assert tokens.ACCENT == DARK.accent
        assert tokens.BG_CANVAS == DARK.surface
        assert tokens.active_palette() is DARK
    finally:
        publish(LIGHT)
    assert tokens.ACCENT == LIGHT.accent
