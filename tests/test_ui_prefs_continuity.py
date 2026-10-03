"""Saved presentation preferences / continuity — single appearance.json surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from semblon import ui_prefs
from semblon.app_reset import reset_app_to_defaults
from semblon.ui_prefs import (
    appearance_path,
    load_grid_density,
    load_last_folder,
    load_last_store,
    load_library_filter,
    load_prefer_gpu,
    load_search_mode,
    load_theme_mode,
    load_window_geometry,
    resolve_home_store,
    save_grid_density,
    save_last_folder,
    save_last_store,
    save_library_filter,
    save_prefer_gpu,
    save_search_mode,
    save_theme_mode,
    save_window_geometry,
    update_prefs,
)


def test_theme_save_preserves_other_keys(tmp_path: Path) -> None:
    store = tmp_path / "store.sqlite"
    save_grid_density("compact", store)
    save_search_mode("text", store)
    save_theme_mode("dark", store)
    raw = json.loads(appearance_path(store).read_text(encoding="utf-8"))
    assert raw["theme"] == "dark"
    assert raw["grid_density"] == "compact"
    assert raw["search_mode"] == "text"


def test_presentation_prefs_roundtrip(tmp_path: Path) -> None:
    store = tmp_path / "lib" / "store.sqlite"
    assert save_search_mode("whole", store) == "whole"
    assert save_library_filter("videos", store) == "videos"
    assert save_prefer_gpu(True, store) is True
    assert save_grid_density("compact", store) == "compact"
    assert load_search_mode(store) == "whole"
    assert load_library_filter(store) == "videos"
    assert load_prefer_gpu(store) is True
    assert load_grid_density(store) == "compact"
    assert load_theme_mode(store) == "system"  # never set


def test_canonical_defaults_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = tmp_path / "store.sqlite"
    monkeypatch.setattr(ui_prefs, "default_store_path", lambda: store)
    assert load_theme_mode(store) == "system"
    assert load_grid_density(store) == "comfortable"
    assert load_search_mode(store) == "people"
    assert load_library_filter(store) == "all"
    assert load_prefer_gpu(store) is None
    assert load_window_geometry() is None


def test_corrupt_prefs_fall_back_safely(tmp_path: Path) -> None:
    store = tmp_path / "store.sqlite"
    appearance_path(store).write_text("{not-json", encoding="utf-8")
    assert load_theme_mode(store) == "system"
    assert load_grid_density(store) == "comfortable"
    assert load_search_mode(store) == "people"
    assert load_library_filter(store) == "all"
    assert load_prefer_gpu(store) is None
    # Rewrite after corrupt must succeed.
    assert save_theme_mode("light", store) == "light"
    assert load_theme_mode(store) == "light"


def test_invalid_enum_values_fall_back(tmp_path: Path) -> None:
    store = tmp_path / "store.sqlite"
    update_prefs(
        store,
        theme="neon",
        grid_density="huge",
        search_mode="telepathy",
        library_filter="slides",
        prefer_gpu="maybe",
    )
    assert load_theme_mode(store) == "system"
    assert load_grid_density(store) == "comfortable"
    assert load_search_mode(store) == "people"
    assert load_library_filter(store) == "all"
    assert load_prefer_gpu(store) is None


def test_reset_restores_canonical_presentation_prefs(tmp_path: Path) -> None:
    store = tmp_path / "lib" / "store.sqlite"
    store.parent.mkdir()
    store.write_bytes(b"")
    save_theme_mode("cyber_obsidian", store)
    save_grid_density("compact", store)
    save_search_mode("region", store)
    save_library_filter("photos", store)
    save_prefer_gpu(False, store)
    assert reset_app_to_defaults(store).ok
    assert not appearance_path(store).exists()
    assert load_theme_mode(store) == "system"
    assert load_grid_density(store) == "comfortable"
    assert load_search_mode(store) == "people"
    assert load_library_filter(store) == "all"
    assert load_prefer_gpu(store) is None


def test_reset_does_not_delete_media(tmp_path: Path) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    media = photos / "keep.jpg"
    media.write_bytes(b"MEDIA")
    store = tmp_path / "lib" / "store.sqlite"
    store.parent.mkdir()
    store.write_bytes(b"")
    save_theme_mode("dark", store)
    assert reset_app_to_defaults(store).ok
    assert media.read_bytes() == b"MEDIA"


def test_last_store_and_window_geometry_machine_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    default = tmp_path / "Semblon" / "store.sqlite"
    default.parent.mkdir(parents=True)
    other = tmp_path / "other" / "store.sqlite"
    other.parent.mkdir()
    other.write_bytes(b"")
    monkeypatch.setattr(ui_prefs, "default_store_path", lambda: default)
    monkeypatch.setattr("semblon.process.default_store_path", lambda: default)

    assert load_last_store() is None
    assert save_last_store(other) == other
    assert load_last_store() == other.resolve()
    assert resolve_home_store(None) == other.resolve()
    assert resolve_home_store(default) == default

    assert save_window_geometry("1400x900+40+20") == "1400x900+40+20"
    assert load_window_geometry() == "1400x900+40+20"
    assert save_window_geometry("bad") is None
    assert load_window_geometry() is None

    # Missing last_store file → fall back to default.
    other.unlink()
    assert load_last_store() is None
    assert resolve_home_store(None) == default


def test_last_folder_roundtrip_and_missing(tmp_path: Path) -> None:
    store = tmp_path / "store.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    assert load_last_folder(store) is None
    assert save_last_folder(folder, store) == folder
    assert load_last_folder(store) == folder.resolve()
    folder.rename(tmp_path / "moved")
    assert load_last_folder(store) is None


def test_reset_clears_last_folder(tmp_path: Path) -> None:
    store = tmp_path / "lib" / "store.sqlite"
    store.parent.mkdir()
    store.write_bytes(b"")
    folder = tmp_path / "photos"
    folder.mkdir()
    save_last_folder(folder, store)
    assert reset_app_to_defaults(store).ok
    assert load_last_folder(store) is None


def test_home_wires_pref_persistence() -> None:
    import inspect

    import semblon.home_ui as home_ui

    init = inspect.getsource(home_ui.HomeApp.__init__)
    assert "resolve_home_store" in init
    assert "load_search_mode" in init
    assert "load_library_filter" in init
    assert "load_prefer_gpu" in init
    assert "load_last_folder" in init
    assert "load_window_geometry" in init
    assert "save_search_mode" in inspect.getsource(home_ui.HomeApp._set_search_mode)
    assert "save_library_filter" in inspect.getsource(home_ui.HomeApp._set_library_filter)
    assert "save_prefer_gpu" in inspect.getsource(home_ui.HomeApp._fill_settings_body)
    assert "save_window_geometry" in inspect.getsource(home_ui.HomeApp._persist_window_geometry)
    assert "initialdir" in inspect.getsource(home_ui.HomeApp._choose_folder)
    assert "save_last_folder" in inspect.getsource(home_ui.HomeApp._start_process)
    home = inspect.getsource(home_ui.HomeApp._show_library_home)
    assert 'filter_key="photos"' not in home
    assert "_library_filter" in home
    reset = inspect.getsource(home_ui.HomeApp._reset_app_to_defaults)
    assert 'self._search_mode = "people"' in reset
    assert 'self._library_filter = "all"' in reset
    assert "self._last_folder = None" in reset
    assert "_refresh_search_placeholder" in inspect.getsource(
        home_ui.HomeApp._set_search_mode
    )
