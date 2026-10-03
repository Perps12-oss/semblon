"""Discovery loop: Memory Canvas → region → Similar → results → continue."""

from __future__ import annotations

import inspect

from semblon.discovery_loop import (
    DiscoveryFrame,
    DiscoverySession,
    image_rect_from_corners,
    image_rect_from_selection,
    result_set_lines,
    with_discovery_prompt,
)
from semblon.product_features import _cmd_lens_find_similar, build_product_registry


def test_image_rect_from_corners_normalizes():
    assert image_rect_from_corners(10, 20, 4, 8) == {"x": 4, "y": 8, "w": 6, "h": 12}
    assert image_rect_from_corners(1, 1, 1.5, 1.5) is None


def test_image_rect_from_selection_region_and_face():
    assert image_rect_from_selection({"kind": "region", "rect": {"x": 1, "y": 2, "w": 30, "h": 40}}) == {
        "x": 1,
        "y": 2,
        "w": 30,
        "h": 40,
    }
    face_hit = {
        "kind": "face",
        "face": {"bbox_x1": 0, "bbox_y1": 0, "bbox_x2": 50, "bbox_y2": 60},
    }
    assert image_rect_from_selection(face_hit) == {"x": 0, "y": 0, "w": 50, "h": 60}


def test_result_set_lines_empty_unavailable_success():
    empty = result_set_lines({"status": "NO_RESULT", "reason": "No similar images found yet."})
    assert "No similar images found yet." in empty[0]
    assert any("try again" in ln.lower() or "another" in ln.lower() for ln in empty)

    unavail = result_set_lines({"status": "UNAVAILABLE", "reason": "needs embeddings"})
    assert "needs embeddings" in unavail[0]
    assert any("library stays open" in ln.lower() for ln in unavail)

    ok = result_set_lines(
        {
            "status": "SUCCESS",
            "kind": "similar",
            "items": [{"media_id": "a"}, {"media_id": "b"}],
        }
    )
    assert "2 similar results" in ok[0]
    assert any("not a person identity" in ln.lower() for ln in ok)


def test_discovery_session_stack_back():
    s = DiscoverySession()
    s.set_query("m1", {"x": 0, "y": 0, "w": 10, "h": 10})
    s.push(DiscoveryFrame(filter_key="all", focus_media_id="m1"))
    s.push(
        DiscoveryFrame(
            filter_key="all",
            similar_media_ids=["a", "b"],
            focus_media_id="a",
        )
    )
    assert s.has_history()
    top = s.pop()
    assert top is not None and top.focus_media_id == "a"
    assert s.pop() is not None
    assert s.pop() is None
    s.clear()
    assert s.query_rect is None


def test_with_discovery_prompt_distinguishes_rect():
    with_rect = with_discovery_prompt(["Looking here"], has_query_rect=True)
    assert any("similarity" in ln.lower() for ln in with_rect)
    without = with_discovery_prompt(["This photo"], has_query_rect=False)
    assert any("select a region" in ln.lower() for ln in without)


def test_find_similar_command_uses_workspace_path():
    src = inspect.getsource(_cmd_lens_find_similar)
    assert "_find_similar_in_workspace" in src
    # Body must call workspace path; docstring may mention the forbidden stack.
    body = src.split('"""', 2)[-1]
    assert "search.search_similar" not in body
    assert "remember_and_find" in src or "open_region_select" in src


def test_home_discovery_loop_methods_exist():
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp)
    assert "_find_similar_in_workspace" in src
    assert "_discovery_back" in src
    assert "_focus_library_media" in src
    assert "btn_find_similar" in src
    assert "DiscoverySession" in src
    apply = inspect.getsource(home_ui.HomeApp._apply_find_similar_result)
    assert "result_set_lines" in apply
    assert "DiscoveryFrame" in apply
    clear = inspect.getsource(home_ui.HomeApp._clear_similar_search)
    assert "_focus_library_media" in clear
    select = inspect.getsource(home_ui.HomeApp._on_canvas_select)
    assert "image_rect_from_selection" in select
    assert "with_discovery_prompt" in select


def test_canvas_region_selection_carries_query_rect():
    from pathlib import Path

    src = Path("semblon/canvas.py").read_text(encoding="utf-8")
    assert "image_rect_from_corners" in src
    assert '"rect": query_rect' in src


def test_registry_still_exposes_find_similar():
    reg = build_product_registry()
    labels = {c.id: c.label for c in reg.commands()}
    assert labels["lens.find_similar"] == "Find Similar"


def test_discovery_loop_does_not_assign_identity():
    import semblon.discovery_loop as mod

    src = inspect.getsource(mod)
    assert "person_id" not in src
    assert "faces.person_id" not in src


def test_find_similar_in_workspace_uses_query_rect_without_lens_page(monkeypatch, tmp_path):
    """End-to-end host path: selection rect → Similar → Memory Canvas filter."""
    import semblon.home_ui as home_ui

    calls: dict = {}

    class FakeHome:
        store = tmp_path / "s.sqlite"
        _insp_media_id = "media-a"
        _discovery = DiscoverySession()
        _canvas_ws = None
        _library_filter = "all"
        _similar_media_ids = None
        _library_return = None
        _last_lens_result = None
        _last_lens_rect = None

        def __init__(self):
            self._discovery.set_query(
                "media-a", {"x": 2, "y": 3, "w": 40, "h": 50}
            )
            self.inspector = []
            self.applied = []

        def _set_inspector(self, title, lines):
            self.inspector = [title, list(lines)]

        def _set_inspector_collapsed(self, _flag):
            return None

        def _apply_find_similar_result(self, summary):
            self.applied.append(summary)

        def _sync_discovery_actions(self):
            return None

    home = FakeHome()
    home._find_similar_in_workspace = home_ui.HomeApp._find_similar_in_workspace.__get__(
        home, FakeHome
    )

    monkeypatch.setattr(
        "semblon.selection.media_file",
        lambda _store, _mid: tmp_path / "a.jpg",
    )

    def fake_remember(store, **kwargs):
        calls["kwargs"] = kwargs
        return {
            "lines": ["Similar images"],
            "summary": {
                "status": "SUCCESS",
                "kind": "similar",
                "items": [{"media_id": "media-b"}],
            },
        }

    monkeypatch.setattr("semblon.lens_release.remember_selection", fake_remember)
    (tmp_path / "a.jpg").write_bytes(b"x")

    home._find_similar_in_workspace()

    assert calls["kwargs"]["media_id"] == "media-a"
    assert calls["kwargs"]["x"] == 2
    assert calls["kwargs"]["w"] == 40
    assert home.applied and home.applied[0]["items"][0]["media_id"] == "media-b"
    assert home._last_lens_result["kind"] == "similar"
