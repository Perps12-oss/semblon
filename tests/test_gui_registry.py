"""Internal GUI feature registry — Phase 1–7 substrate tests."""

from __future__ import annotations

import inspect

import pytest

from semblon.gui_registry import (
    DuplicateFeatureId,
    Feature,
    FeatureRegistry,
    GuiCommand,
    NavContribution,
    UnknownFeature,
    default_registry,
    reset_default_registry_for_tests,
)
from semblon.home_ui import HOME_NAV, refresh_home_nav
from semblon.product_features import build_product_registry, register_demo_feature


def test_register_and_lookup():
    reg = FeatureRegistry()
    feat = Feature(id="a", label="A", route_id="a")
    reg.register(feat)
    assert reg.get("a") is feat
    assert "a" in reg
    assert [f.id for f in reg.features()] == ["a"]


def test_duplicate_feature_id_rejected():
    reg = FeatureRegistry()
    reg.register(Feature(id="x", label="X"))
    with pytest.raises(DuplicateFeatureId):
        reg.register(Feature(id="x", label="X2"))


def test_unknown_feature_raises():
    reg = FeatureRegistry()
    with pytest.raises(UnknownFeature):
        reg.get("missing")


def test_unavailable_features_filtered():
    reg = FeatureRegistry()
    reg.register(Feature(id="on", label="On", available=lambda _h: True))
    reg.register(Feature(id="off", label="Off", available=lambda _h: False))
    ids = [f.id for f in reg.features(available_only=True)]
    assert ids == ["on"]


def test_route_resolution_and_nav():
    calls: list[str] = []

    def page(host):
        calls.append("ran")

    reg = FeatureRegistry()
    reg.register(
        Feature(
            id="photos",
            label="Photos",
            nav=NavContribution(section="LIBRARY", route_id="home", label="Photos", order=0),
            route_id="home",
            page=page,
        )
    )
    assert reg.feature_for_route("home") is not None
    fn = reg.resolve_route("home")
    assert fn is not None
    fn(None)
    assert calls == ["ran"]
    sections = reg.nav_sections()
    assert sections[0][0] == "LIBRARY"
    assert sections[0][1][0].route_id == "home"


def test_command_discovery_by_surface():
    ran: list[str] = []

    def run(host, ctx=None):
        ran.append("ok")

    reg = FeatureRegistry()
    reg.register(
        Feature(
            id="people",
            label="People",
            commands=(
                GuiCommand(
                    id="person.history",
                    label="Show history",
                    run=run,
                    surfaces=frozenset({"inspector", "palette"}),
                    available=lambda h, c: True,
                ),
                GuiCommand(
                    id="hidden.overflow_only",
                    label="Hidden",
                    run=run,
                    surfaces=frozenset({"overflow"}),
                ),
            ),
        )
    )
    insp = reg.commands(surface="inspector")
    assert [c.id for c in insp] == ["person.history"]
    assert reg.get_command("person.history") is not None
    insp[0].execute(None, None)
    assert ran == ["ok"]


def test_product_registry_matches_home_nav_shape():
    reg = build_product_registry()
    nav = reg.home_nav_tuple()
    flat = {rid: label for _sec, items in nav for rid, label in items}
    assert flat["home"] == "Photos"
    assert flat["videos"] == "Videos"
    assert flat["people"] == "People"
    assert flat["unknown"] == "People to name"
    assert flat["activity"] == "Recent activity"
    assert flat["lens"] == "Lens"
    # HOME_NAV module export stays in sync.
    refresh_home_nav()
    assert HOME_NAV == nav
    # Activity is a real page factory.
    assert reg.resolve_route("activity") is not None
    assert reg.get("activity").page is not None


def test_product_commands_expose_hidden_capabilities():
    reg = build_product_registry()
    ids = {c.id for c in reg.commands()}
    for needed in {
        "person.history",
        "person.identify_face",
        "lens.select_region",
        "lens.find_similar",
        "lens.ask",
        "lens.search_text",
        "library.browse_photos",
        "library.backup",
        "library.watch_folder",
        "library.export_person_folders",
        "shell.open_review",
    }:
        assert needed in ids


def test_demo_feature_registers_without_editing_homeapp():
    """Architectural acceptance: new feature needs no HomeApp / HOME_NAV / menu edits."""
    home_src = inspect.getsource(__import__("semblon.home_ui", fromlist=["HomeApp"]).HomeApp)
    assert "registry_demo" not in home_src

    reg = build_product_registry()
    before_nav = reg.home_nav_tuple()
    feat = register_demo_feature(reg)
    assert feat.id == "registry_demo"
    assert reg.resolve_route("registry_demo") is not None
    assert any(n.route_id == "registry_demo" for n in reg.nav_contributions())
    assert reg.get_command("registry_demo.ping") is not None
    # Discoverable on palette / overflow without shell edits.
    labels = {c.label for c in reg.commands(surface="palette")}
    assert "Demo ping" in labels
    # Original product nav still present.
    flat_before = {rid for _s, items in before_nav for rid, _ in items}
    flat_after = {n.route_id for n in reg.nav_contributions()}
    assert flat_before <= flat_after


def test_reset_default_registry_isolates_tests():
    a = build_product_registry()
    register_demo_feature(a)
    reset_default_registry_for_tests(a)
    assert "registry_demo" in default_registry()
    reset_default_registry_for_tests(build_product_registry())
    assert "registry_demo" not in default_registry()


def test_navigate_uses_registry_resolve(monkeypatch):
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp._navigate)
    assert "resolve_route" in src
    assert "self._registry" in src


def test_overflow_and_palette_consume_registry():
    import semblon.home_ui as home_ui

    overflow = inspect.getsource(home_ui.HomeApp._rebuild_overflow_menu)
    palette = inspect.getsource(home_ui.HomeApp._open_command_palette)
    assert 'surface="overflow"' in overflow
    assert "nav_contributions" in palette
    assert 'surface="palette"' in palette
