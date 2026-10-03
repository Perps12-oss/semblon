"""To name wiring — badge, route, and group list share unnamed_groups."""

from __future__ import annotations

import inspect

from semblon import fluid_shell, home_ui, product_features
from semblon.gui_registry import default_registry
from semblon.home_ui import format_unknown_lines
from semblon.inspector_verbs import evidence_lines_for_selection
from semblon.library_status import (
    library_summary,
    people_to_name_text,
    unnamed_group_items,
)
from semblon.product_surface import soft_unknown_coach_lines
from tests.test_review import _clustered


def test_badge_count_uses_canonical_unnamed_groups(tmp_path):
    store = tmp_path / "s.sqlite"
    _clustered(store)
    summary = library_summary(store)
    assert summary is not None
    waiting = int(summary["unnamed_groups"])
    assert waiting >= 1
    assert people_to_name_text(waiting) == soft_unknown_coach_lines(waiting=waiting)[0].rstrip(".")
    assert fluid_shell.people_chrome_label(waiting) == f"To name ({waiting})"
    items = unnamed_group_items(store)
    assert len(items) == waiting
    assert all(it.get("kind") == "cluster" and not it.get("named") for it in items)


def test_to_name_click_navigates_unknown_route():
    src = inspect.getsource(product_features._cmd_review_to_name)
    assert '_navigate("unknown")' in src
    open_src = inspect.getsource(home_ui.HomeApp._open_people_mode)
    assert '_navigate("unknown"' in open_src
    show = inspect.getsource(home_ui.HomeApp._show_unknown)
    assert 'title = "Groups to name"' in show
    reg = default_registry()
    feat = next(f for f in reg.features() if getattr(f, "id", None) == "unknown")
    assert feat.route_id == "unknown"
    assert feat.label == "Groups to name"


def test_show_unknown_renders_groups_not_inbox_evidence():
    src = inspect.getsource(home_ui.HomeApp._show_unknown)
    assert "unnamed_groups" in src or "library_summary" in src
    assert "unnamed_group_items" in src
    assert "_mount_to_name_workspace" in src
    assert "Groups to name" in src
    assert "evidence_lines_for_selection" not in src
    assert "inbox(" not in src
    assert "flatten_board_items_for_inspector" not in src
    mount = inspect.getsource(home_ui.HomeApp._mount_to_name_workspace)
    assert "_unnamed_cluster_face_paths" in mount


def test_set_inspector_does_not_wipe_to_name_selection():
    src = inspect.getsource(home_ui.HomeApp._set_inspector)
    assert 'self._sel_list.delete(0, tk.END)' in src
    # Wipe titles are the set immediately before the delete; To name titles
    # must not be members (People already was excluded).
    wipe_anchor = src.split("self._sel_list.delete(0, tk.END)")[0]
    wipe_set = wipe_anchor.rsplit("if title in {", 1)[-1]
    assert '"People to name"' not in wipe_set
    assert '"Groups to name"' not in wipe_set
    assert '"To review"' in wipe_set


def test_no_obsolete_people_to_name_evidence_copy():
    coach = soft_unknown_coach_lines(waiting=1571)
    joined = "\n".join(coach)
    assert "1571 groups to name" in joined
    assert "people to name" not in joined.lower()
    # Destination coach must not be the machine evidence shell.
    evid = "\n".join(
        evidence_lines_for_selection(
            run_id="20260929T020849Z-d71721",
            selected=[],
            board_lines=format_unknown_lines({}, "r1", waiting=1571),
        )
    )
    # Product To name path no longer feeds this shell; assert the obsolete
    # inbox-face phrasing is gone from the coach itself.
    soft = format_unknown_lines(
        {"counts": {"UNKNOWN": 1571, "REVIEW_REQUIRED": 0}},
        "20260929T020849Z-d71721",
        waiting=133,
    )
    assert soft[0] == "133 groups to name."
    assert "1571" not in "\n".join(soft)
    assert "people to name" not in "\n".join(soft).lower()
    assert "Evidence relationship (machine)" in evid  # still exists for other surfaces
