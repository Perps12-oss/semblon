"""Atmosphere & Motion System — state tokens and prefs."""

from __future__ import annotations

import json

import pytest

from semblon.atmosphere import (
    ATMOSPHERES,
    DARK_ATMOSPHERE_IDS,
    DEFAULT_DARK_ATMOSPHERE,
    InteractionState,
    THEME_MODES,
    get_atmosphere,
    lerp_field_map,
    lerp_hex,
    normalize_atmosphere_id,
    palette_for,
    resolve,
)
from semblon.atmosphere_render import (
    Capability,
    allows_continuous_motion,
    detect_capability,
    publish_atmosphere,
    reset_capability_for_tests,
    transition_to,
)
from semblon.ui_prefs import (
    appearance_path,
    load_theme_mode,
    resolve_atmosphere_id,
    resolve_palette,
    save_theme_mode,
)
from semblon.ui_tokens import LIGHT, publish


def test_all_atmospheres_define_every_state():
    for aid in ATMOSPHERES:
        for state in InteractionState:
            tokens = resolve(aid, state)
            assert tokens.atmosphere_id == aid
            assert tokens.state is state
            assert tokens.surface.startswith("#")
            assert tokens.accent.startswith("#")
            assert tokens.region.outline.startswith("#")
            assert tokens.spotlight_radius_px > 0
            assert 0.0 <= tokens.illumination <= 1.0 or state is InteractionState.RESTING


def test_four_dark_atmospheres_are_visually_distinct():
    accents = {aid: get_atmosphere(aid).accent for aid in DARK_ATMOSPHERE_IDS}
    surfaces = {aid: get_atmosphere(aid).surface for aid in DARK_ATMOSPHERE_IDS}
    assert len(accents) == len(DARK_ATMOSPHERE_IDS)
    assert len(set(surfaces.values())) == len(DARK_ATMOSPHERE_IDS)
    assert get_atmosphere("tokyo_synth").dual_tone is True
    assert get_atmosphere("tokyo_synth").accent_b != get_atmosphere("tokyo_synth").accent


def test_dark_alias_and_system_resolve_to_mica():
    assert normalize_atmosphere_id("dark") == DEFAULT_DARK_ATMOSPHERE
    assert resolve_atmosphere_id("dark") == "mica_dark"
    assert resolve_atmosphere_id("system", system_dark=True) == "mica_dark"
    assert resolve_atmosphere_id("system", system_dark=False) == "light"
    assert resolve_atmosphere_id("system", system_dark=None) == "mica_dark"
    assert resolve_atmosphere_id("nope") == "light"
    assert resolve_atmosphere_id("cyber_obsidian") == "cyber_obsidian"


def test_theme_modes_include_atmospheres():
    for aid in DARK_ATMOSPHERE_IDS:
        assert aid in THEME_MODES
    assert "dark" in THEME_MODES
    assert "system" in THEME_MODES


def test_prefs_roundtrip_atmosphere(tmp_path):
    store = tmp_path / "lib" / "store.sqlite"
    assert save_theme_mode("neon_ember", store) == "neon_ember"
    assert load_theme_mode(store) == "neon_ember"
    assert json.loads(appearance_path(store).read_text(encoding="utf-8")) == {
        "theme": "neon_ember"
    }
    pal = resolve_palette("neon_ember")
    assert pal.accent == get_atmosphere("neon_ember").accent
    assert save_theme_mode("dark", store) == "dark"
    assert resolve_atmosphere_id(load_theme_mode(store)) == "mica_dark"


def test_hover_clears_selected_persists_semantics():
    hover = resolve("mica_dark", InteractionState.HOVER)
    selected = resolve("mica_dark", InteractionState.SELECTED)
    resting = resolve("mica_dark", InteractionState.RESTING)
    assert hover.illumination > resting.illumination
    assert selected.elevation > hover.elevation
    assert selected.border == selected.accent
    assert hover.glow != ""
    assert resting.glow == ""
    disabled = resolve("mica_dark", InteractionState.DISABLED)
    assert disabled.illumination == 0.0
    assert disabled.elevation == 0


def test_region_resting_vs_hover_vs_selected():
    r = resolve("cyber_obsidian", InteractionState.RESTING).region
    h = resolve("cyber_obsidian", InteractionState.HOVER).region
    s = resolve("cyber_obsidian", InteractionState.SELECTED).region
    assert r.label_visible is False
    assert r.fill == ""
    assert h.label_visible is True
    assert h.fill != ""
    assert s.outline_width >= h.outline_width
    assert s.aura != ""


def test_lerp_hex_and_field_map():
    assert lerp_hex("#000000", "#FFFFFF", 0.0) == "#000000"
    assert lerp_hex("#000000", "#FFFFFF", 1.0) == "#FFFFFF"
    mid = lerp_hex("#000000", "#FFFFFF", 0.5)
    assert mid == "#808080"
    src = {"accent": "#000000", "surface": "#111111"}
    dst = {"accent": "#FFFFFF", "surface": "#222222"}
    out = lerp_field_map(src, dst, 0.5)
    assert out["accent"] == "#808080"


def test_reduced_motion_disables_continuous():
    reset_capability_for_tests()
    detect_capability(force=Capability.REDUCED)
    try:
        assert allows_continuous_motion() is False
    finally:
        reset_capability_for_tests()


def test_publish_atmosphere_and_transition_snap(tmp_path):
    reset_capability_for_tests()
    detect_capability(force=Capability.STATIC)
    try:
        publish(LIGHT)
        publish_atmosphere("mica_dark")
        from semblon import ui_tokens as tokens
        from semblon.atmosphere_render import active_atmosphere_id

        assert active_atmosphere_id() == "mica_dark"
        assert tokens.ACCENT == get_atmosphere("mica_dark").accent
        done = []
        transition_to(None, "tokyo_synth", on_done=lambda: done.append(1))
        assert done == [1]
        assert active_atmosphere_id() == "tokyo_synth"
    finally:
        publish(LIGHT)
        publish_atmosphere("light")
        reset_capability_for_tests()


def test_palette_for_matches_spec():
    for aid in ATMOSPHERES:
        pal = palette_for(aid)
        spec = get_atmosphere(aid)
        assert pal.accent == spec.accent
        assert pal.surface == spec.surface


def test_preview_theatre_uses_resolve():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"tkinter could not start: {exc}")
    root.withdraw()
    reset_capability_for_tests()
    detect_capability(force=Capability.STATIC)
    try:
        from semblon.atmosphere_render import PreviewTheatre

        tile = PreviewTheatre(root, "neon_ember", selected=False)
        assert tile.atmosphere_id == "neon_ember"
        tile.set_selected(True)
        tile.destroy()
    finally:
        reset_capability_for_tests()
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_stage_capability_card_hover_selected_not_conflated():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"tkinter could not start: {exc}")
    root.withdraw()
    reset_capability_for_tests()
    detect_capability(force=Capability.FULL)
    clicked = []
    try:
        from semblon.atmosphere_render import StageCapabilityCard
        from semblon.atmosphere import InteractionState

        card = StageCapabilityCard(
            root,
            title="Explore",
            body="See your photos.",
            command=lambda: clicked.append(1),
            primary=True,
            atmosphere_id="mica_dark",
        )
        assert card._state is InteractionState.RESTING
        card._on_enter()
        assert card._state is InteractionState.HOVER
        card._on_leave()
        assert card._state is InteractionState.RESTING
        card._on_click()
        assert card._state is InteractionState.SELECTED
        assert clicked == [1]
        # Leave after select keeps SELECTED until paint RESTING explicitly
        card._on_leave()
        assert card._state is InteractionState.SELECTED
    finally:
        reset_capability_for_tests()
        try:
            root.destroy()
        except tk.TclError:
            pass


def test_dissolve_stage_snaps_when_reduced():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"tkinter could not start: {exc}")
    root.withdraw()
    reset_capability_for_tests()
    detect_capability(force=Capability.REDUCED)
    done = []
    try:
        from semblon.atmosphere_render import dissolve_stage

        dissolve_stage(root, on_done=lambda: done.append(1), atmosphere_id="mica_dark")
        assert done == [1]
    finally:
        reset_capability_for_tests()
        try:
            root.destroy()
        except tk.TclError:
            pass
