"""Fluid Visual Workspace — nav, launch, library filters, Details drawer."""

from __future__ import annotations

import inspect

from semblon.fluid_shell import (
    LIBRARY_FILTERS,
    ONBOARD_CTA,
    ONBOARD_HEADLINE,
    footer_library_line,
    footer_status_word,
    library_source_types,
    people_review_banner,
)
from semblon.gui_registry import default_registry, reset_default_registry_for_tests
from semblon.home_ui import HOME_NAV, refresh_home_nav
from semblon.product_features import build_product_registry
from semblon.product_surface import SETTINGS_SHORTCUTS


def test_primary_nav_is_library_people_activity():
    reset_default_registry_for_tests(build_product_registry())
    refresh_home_nav()
    flat = {rid: label for _sec, items in HOME_NAV for rid, label in items}
    assert flat == {
        "library": "Library",
        "people": "People",
        "activity": "Activity",
    }
    assert "lens" not in flat
    assert "unknown" not in flat
    assert "videos" not in flat
    assert "photos" not in flat
    assert ("Library", "Ctrl+1") in SETTINGS_SHORTCUTS
    assert ("People", "Ctrl+2") in SETTINGS_SHORTCUTS
    assert ("Activity", "Ctrl+3") in SETTINGS_SHORTCUTS


def test_compatibility_routes_still_resolve():
    reg = build_product_registry()
    for rid in ("library", "home", "photos", "videos", "lens", "unknown", "people", "activity"):
        assert reg.resolve_route(rid) is not None
    assert reg.get("lens").nav is None
    assert reg.get("unknown").nav is None


def test_library_filter_source_types():
    assert library_source_types("all") is None
    assert library_source_types("photos") == ("folder", "")
    assert library_source_types("videos") == ("video",)
    assert [k for k, _ in LIBRARY_FILTERS] == ["all", "photos", "videos"]


def test_footer_and_banner_copy():
    assert footer_library_line(None) == "No library yet"
    assert "photo" in footer_library_line({"photos": 2, "videos": 1})
    assert footer_status_word(busy=False) == "Ready"
    assert "Scanning" in footer_status_word(busy=True)
    assert people_review_banner(0) is None
    assert people_review_banner(3) is not None


def test_onboarding_and_library_methods_exist():
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp)
    assert "_show_library_or_onboard" in src
    assert "_show_onboarding" in src
    assert "_show_library" in src
    assert "_apply_find_similar_result" in src
    assert "_clear_similar_search" in src
    assert "Add Folder" in src
    onboard = inspect.getsource(home_ui.HomeApp._show_onboarding)
    assert "ONBOARD_HEADLINE" in onboard
    assert "ONBOARD_CTA" in onboard
    build = inspect.getsource(home_ui.HomeApp.__init__)
    assert '_navigate("library")' in build
    assert "btn_folder" in build
    assert "btn_settings" in build


def test_details_drawer_hides_without_selection():
    import semblon.home_ui as home_ui

    sel = inspect.getsource(home_ui.HomeApp._on_canvas_select)
    assert '_set_inspector_collapsed(True)' in sel
    assert 'title = "Details"' in sel or 'title = "Details"' in sel
    collapsed = inspect.getsource(home_ui.HomeApp._set_inspector_collapsed)
    assert "minsize=320" in collapsed


def test_find_similar_command_label():
    reg = build_product_registry()
    labels = {c.id: c.label for c in reg.commands()}
    assert labels["lens.find_similar"] == "Find Similar"
