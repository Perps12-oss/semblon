"""Discovery → Compare → Decide (session-scoped, no identity / no delete)."""

from __future__ import annotations

import inspect

from semblon.culling_compare import (
    COMPARE_MAX,
    COMPARE_MIN,
    CompareSession,
    DECISION_KEEP,
    DECISION_REJECT,
    compare_unavailable_lines,
    decision_lines,
)
from semblon.product_features import build_product_registry


def test_compare_session_enter_limits():
    s = CompareSession()
    s.set_result_ids(["a", "b", "c", "d", "e"])
    assert s.can_enter()[0] is False
    s.toggle_selected("a")
    assert s.can_enter()[0] is False
    s.toggle_selected("b")
    ok, _ = s.can_enter()
    assert ok
    assert s.enter()[0] is True
    assert s.active
    assert s.compare_ids == ["a", "b"]


def test_compare_max_selection():
    s = CompareSession()
    s.set_result_ids([f"m{i}" for i in range(6)])
    for i in range(COMPARE_MAX + 1):
        s.toggle_selected(f"m{i}")
    assert len(s.selected_ids) == COMPARE_MAX


def test_reject_hides_from_visible_does_not_delete_flag():
    s = CompareSession()
    s.set_result_ids(["a", "b", "c"])
    s.toggle_selected("a")
    s.toggle_selected("b")
    assert s.enter()[0]
    rec = s.decide("a", DECISION_REJECT)
    assert rec["ok"]
    assert rec["deleted_file"] is False
    assert rec["person_id_written"] is False
    assert "a" not in s.visible_result_ids()
    assert "a" in s.result_ids
    assert s.decisions["a"] == DECISION_REJECT


def test_keep_is_session_only():
    s = CompareSession()
    s.set_result_ids(["a", "b", "c"])
    s.selected_ids = ["a", "b"]
    s.enter()
    rec = s.decide("b", DECISION_KEEP)
    assert rec["ok"]
    assert rec["decision"] == DECISION_KEEP
    assert "b" in s.visible_result_ids()
    assert s.decisions["b"] == DECISION_KEEP


def test_exit_compare_and_back_semantics():
    s = CompareSession()
    s.set_result_ids(["a", "b"])
    s.selected_ids = ["a", "b"]
    s.enter()
    s.exit()
    assert s.active is False
    assert s.compare_ids == []


def test_focus_arrows():
    s = CompareSession()
    s.set_result_ids(["a", "b", "c"])
    s.selected_ids = ["a", "b", "c"]
    s.enter()
    assert s.focused_id() == "a"
    assert s.move_focus(1) == "b"
    assert s.move_focus(1) == "c"
    assert s.move_focus(1) == "c"


def test_unavailable_copy():
    lines = compare_unavailable_lines(selected_count=0, result_count=3)
    assert any("Ctrl+click" in ln for ln in lines)
    one = compare_unavailable_lines(selected_count=0, result_count=1)
    assert any("one" in ln.lower() for ln in one)


def test_decision_lines_firewall_copy():
    lines = decision_lines(DECISION_REJECT, remaining=2)
    assert any("not deleted" in ln.lower() for ln in lines)
    assert any("not a person identity" in ln.lower() for ln in lines)


def test_registry_compare_commands():
    reg = build_product_registry()
    ids = {c.id for c in reg.commands()}
    assert "compare.enter" in ids
    assert "compare.exit" in ids
    assert "media.keep" in ids
    assert "media.reject" in ids
    # No MAIN nav for compare feature.
    feat = reg.get("discovery_compare")
    assert feat.nav is None


def test_home_compare_methods_exist():
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp)
    for name in (
        "_enter_compare",
        "_exit_compare",
        "_compare_decide",
        "_toggle_compare_candidate",
        "_render_compare_pane",
        "_on_discovery_escape",
        "CompareSession",
    ):
        assert name in src
    back = inspect.getsource(home_ui.HomeApp._discovery_back)
    assert "_exit_compare" in back
    clear = inspect.getsource(home_ui.HomeApp._clear_similar_search)
    assert "_compare.clear" in clear or "self._compare.clear" in clear


def test_canvas_ctrl_click_compare_toggle():
    from pathlib import Path

    src = Path("semblon/canvas.py").read_text(encoding="utf-8")
    assert "_on_thumb_compare_toggle" in src
    assert "set_compare_marks" in src


def test_culling_module_no_person_id_writes():
    import semblon.culling_compare as mod

    src = inspect.getsource(mod)
    assert "faces.person_id" not in src
    assert "person_id =" not in src
    assert "DELETE FROM" not in src
    assert COMPARE_MIN == 2
    assert COMPARE_MAX == 4


def test_host_enter_compare_path(monkeypatch):
    import semblon.home_ui as home_ui

    class Fake:
        _similar_media_ids = ["a", "b", "c"]
        _library_filter = "all"
        _compare = CompareSession()
        shown = None
        inspector = None

        def __init__(self):
            self._compare.set_result_ids(self._similar_media_ids)
            self._compare.selected_ids = ["a", "b"]

        def _show_library(self, **kwargs):
            self.shown = kwargs

        def _set_inspector(self, title, lines):
            self.inspector = (title, list(lines))

        def _set_inspector_collapsed(self, _f):
            return None

        def _sync_discovery_actions(self):
            return None

    h = Fake()
    h._enter_compare = home_ui.HomeApp._enter_compare.__get__(h, Fake)
    h._enter_compare()
    assert h._compare.active
    assert h.shown is not None
    assert h.inspector and "Comparing" in h.inspector[1][0]
