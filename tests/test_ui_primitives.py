"""Visual primitives — MediaTile states, Inspector sections, Search chrome."""

from __future__ import annotations

import inspect

import pytest

from semblon.ui_primitives import (
    MediaTileState,
    build_search_presentation,
    media_ids_from_search_rec,
    media_tile_colors,
    media_tile_state,
    search_header_lines,
    sections_from_lines,
    truncate_label,
)
from semblon.ui_tokens import ACCENT, BG_STAGE, BORDER_DEFAULT, FOCUS_RING


def test_media_tile_states_use_tokens_not_legacy_hex():
    resting = media_tile_colors(MediaTileState.RESTING)
    hover = media_tile_colors(MediaTileState.HOVER)
    selected = media_tile_colors(MediaTileState.SELECTED)
    focus = media_tile_colors(MediaTileState.FOCUS)
    loading = media_tile_colors(MediaTileState.LOADING)
    assert resting.fill == BG_STAGE
    assert resting.outline == BORDER_DEFAULT
    assert hover.outline_width >= resting.outline_width
    assert selected.outline == ACCENT
    assert focus.outline == FOCUS_RING
    assert loading.fill != resting.fill
    # Legacy hardcoded grid colours must not reappear.
    legacy = {"#2a2d34", "#1c1f26", "#9b9a94"}
    for colors in (resting, hover, selected, loading):
        assert colors.fill.lower() not in legacy
        assert colors.outline.lower() not in legacy
        assert colors.label.lower() not in legacy


def test_media_tile_state_precedence():
    assert media_tile_state(selected=True, hover=True) is MediaTileState.SELECTED
    assert media_tile_state(hover=True) is MediaTileState.HOVER
    assert media_tile_state(loading=True) is MediaTileState.LOADING
    assert media_tile_state(disabled=True, selected=True) is MediaTileState.DISABLED


def test_truncate_label():
    assert truncate_label("short") == "short"
    assert truncate_label("abcdefghijklmnopqrstuvwxyz", max_chars=10).endswith("…")
    assert len(truncate_label("abcdefghijklmnopqrstuvwxyz", max_chars=10)) == 10


def test_sections_from_lines_promotes_short_titles():
    secs = sections_from_lines(["People", "Ada  (3 photos)", "", "Note", "hello"])
    assert secs[0].title == "People"
    assert secs[0].lines == ("Ada  (3 photos)",)
    assert secs[1].title == "Note"
    assert secs[1].lines == ("hello",)


def test_search_presentation_and_media_ids():
    rec = {
        "kind": "person",
        "query": "Ada",
        "count": 1,
        "items": [{"display_name": "Ada", "faces": 2}],
        "history": {"items": [{"media_id": "m1"}, {"media_id": "m2"}, {"media_id": "m1"}]},
    }
    mids = media_ids_from_search_rec(rec)
    assert mids == ["m1", "m2"]
    pres = build_search_presentation(rec, lines=["People", "Ada"], media_ids=mids)
    assert pres.mode == "People"
    assert pres.query == "Ada"
    header = search_header_lines(pres)
    assert header[0] == "Search"
    assert any(line.startswith("Query:") for line in header)
    assert any("1 result" in line for line in header)
    assert "Open a photo on the Memory Canvas to continue." in header


def test_canvas_thumb_paint_uses_media_tile_colors():
    pytest.importorskip("tkinter")
    import semblon.canvas as canvas

    # Paint lives in virtualized _paint_visible_thumbs; rebuild builds ViewModel layout.
    paint = inspect.getsource(canvas.CanvasWorkspace._paint_visible_thumbs)
    rebuild = inspect.getsource(canvas.CanvasWorkspace._rebuild_thumbs)
    assert "media_tile_colors" in paint
    assert "build_media_grid" in rebuild or "MediaGrid" in rebuild
    assert "#2a2d34" not in paint
    assert "#1c1f26" not in paint
    assert "#9b9a94" not in paint
    assert "media_tile" in paint


def test_home_inspector_uses_inspector_body_not_details_listbox():
    import semblon.home_ui as home_ui

    init = inspect.getsource(home_ui.HomeApp.__init__)
    assert "InspectorBody" in init
    assert "ActionGroup" in init
    # Details surface must not construct a Listbox for evidence lines.
    assert 'self._inspector = tk.Listbox' not in init
    set_insp = inspect.getsource(home_ui.HomeApp._set_inspector)
    assert "set_lines" in set_insp


def test_home_search_presents_shared_chrome():
    import semblon.home_ui as home_ui

    assert hasattr(home_ui.HomeApp, "_present_search")
    src = inspect.getsource(home_ui.HomeApp._search_person)
    assert "_present_search" in src


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("tkinter") is None,
    reason="tkinter unavailable",
)
def test_inspector_body_set_lines_builds_sections(root=None):
    pytest.importorskip("tkinter")
    import tkinter as tk

    from semblon.ui_primitives import InspectorBody
    from semblon.ui_theme import apply_theme, reset_theme_for_tests

    try:
        r = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"tkinter could not start: {exc}")
    r.withdraw()
    reset_theme_for_tests()
    apply_theme(r)
    try:
        body = InspectorBody(r, width=200)
        body.set_lines(["People", "Ada", "", "Details", "hello world"])
        assert len(body._sections) == 2
        body.clear()
        assert body._sections == []
    finally:
        try:
            r.destroy()
        except tk.TclError:
            pass
        reset_theme_for_tests()
