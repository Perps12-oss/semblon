"""Home activity semantics readers + Track-1 control policy + UX Rescue chrome."""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pytest

from semblon.home_ui import (
    HOME_IDLE_STATUS,
    HOME_NAV,
    INSPECTOR_HOME_EMPTY,
    format_activity_lines,
    home_control_states,
    read_activity_snapshot,
)
from semblon.observers import snapshot_memory_graph
from semblon.review import name_cluster, name_face
from tests.test_review import _clustered


def test_activity_lines_include_group_semantics(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_face(store, "r1", "f5", "Bob")
    snapshot_memory_graph(store, run_id="r1")

    rec = read_activity_snapshot(store, "r1")
    soft = format_activity_lines(
        run_line="run=r1",
        integrity_line="integrity ok=1 unfinished=0",
        groups=rec["groups"],
        relationships=rec["relationships"],
        events=rec["events"],
        track_count=rec["track_count"],
        photos=5,
        faces=3,
        group_count=2,
        advanced=False,
    )
    soft_text = "\n".join(soft)
    assert "photos processed" in soft_text
    assert "observation_groups" not in soft_text
    assert "track ≠ person" not in soft_text

    lines = format_activity_lines(
        run_line="run=r1",
        integrity_line="integrity ok=1 unfinished=0",
        groups=rec["groups"],
        relationships=rec["relationships"],
        events=rec["events"],
        track_count=rec["track_count"],
        advanced=True,
    )
    text = "\n".join(lines)
    assert "observation_groups" in text
    assert "members=" in text
    assert "not a person" in text
    assert "relationships:" in text
    assert "events:" in text
    assert "track ≠ person" in text


def test_activity_reader_broken_db_is_not_swallowed(tmp_path):
    bad = tmp_path / "broken.sqlite"
    bad.write_text("this is not sqlite")
    with pytest.raises(sqlite3.DatabaseError):
        read_activity_snapshot(Path(bad), "r1")


def test_home_control_policy_does_not_lock_read_surfaces():
    busy = home_control_states(job_running=True, resume_ready=False)
    for name in ("review", "people", "search", "unknown", "activity", "settings", "canvas", "html"):
        assert busy[name] == "normal"
    assert busy["folder"] == "disabled"
    assert busy["cancel"] == "normal"
    assert busy["pause"] == "normal"
    assert busy["resume"] == "disabled"

    paused = home_control_states(job_running=True, job_paused=True, resume_ready=False)
    assert paused["pause"] == "disabled"
    assert paused["resume"] == "normal"
    assert paused["cancel"] == "normal"


def test_home_nav_labels_ux_rescue():
    """§4 — display labels change; route ids stay unknown / activity."""
    flat = {nav_id: label for _sec, items in HOME_NAV for nav_id, label in items}
    assert flat["unknown"] == "To review"
    assert flat["activity"] == "Recent activity"
    assert flat["home"] == "Photos"
    assert "photos" not in flat
    assert flat["people"] == "People"


def test_home_idle_status_has_no_store_path():
    """§10 — idle copy is coaching, not Store: path."""
    assert HOME_IDLE_STATUS == "Ready — choose a folder of photos to begin."
    assert "Store:" not in HOME_IDLE_STATUS


def test_home_inspector_default_is_soft():
    """§5 — home inspector empty is soft coaching, not architecture dump."""
    text = "\n".join(INSPECTOR_HOME_EMPTY)
    assert "Your results will appear here" in text
    assert "AppShell" not in text
    assert "person_id" not in text
    assert "JobEngine" not in text
    assert "buffalo_l" not in text


def test_home_is_a_job_client():
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp)
    assert "JobEngine" in src
    assert "home_control_states" in src
    assert "btn_review.configure(state=state)" not in src
    assert "LIBRARY" in src
    assert "CanvasWorkspace" in src
    assert "INSPECTOR" in src
    assert "faces.person_id" in src or "person_id" in src
    # Activity reads go through Application façade (APP-1), not a Home-owned SQL path.
    assert "from semblon.application import activity" in src
    assert "inspector_verbs" in src or "Merge observations" in src
    # UX Rescue landing + settings + result card.
    assert "_show_home_landing" in src
    assert "Add a photo folder" in src
    assert "Find the people in your photos" in src
    assert "open_advanced_diagnostics" in src
    assert "Your photos are ready" in src
    assert "Review people" in src


def test_home_landing_has_no_engineering_leak():
    """§2 — cold-launch landing method must not render buffalo_l / FaceKit / AppShell."""
    import semblon.home_ui as home_ui

    landing = inspect.getsource(home_ui.HomeApp._show_home_landing)
    build = inspect.getsource(home_ui.HomeApp._build_home_landing)
    for blob in (landing, build):
        assert "buffalo_l" not in blob
        assert "FaceKit" not in blob
        assert "AppShell" not in blob
        assert "JobEngine" not in blob
        assert "person_id" not in blob
        assert "R3" not in blob


def test_home_settings_is_user_panel_not_dump():
    """§6 — Settings opens a user panel; diagnostics go to Advanced."""
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp._show_settings)
    assert "Advanced diagnostics" in src
    assert "Library location" in src
    assert "Use GPU when available" in src or "Processing on this computer" in src
    assert "format_execution_status_lines" not in src
    assert "weights_status" not in src
    assert "buffalo_l" not in src


def test_home_defers_canvas_load_until_inspector_ready():
    """Regression: Canvas on_select during __init__ must not touch missing _canvas_ws."""
    import semblon.home_ui as home_ui

    init_src = inspect.getsource(home_ui.HomeApp.__init__)
    # First CanvasWorkspace construction must not pass the live store (reload→on_select
    # runs before Inspector widgets / attribute assignment complete).
    assert "store=None" in init_src
    sel_src = inspect.getsource(home_ui.HomeApp._on_canvas_select)
    assert 'getattr(self, "_canvas_ws"' in sel_src
    assert 'hasattr(self, "_sel_list")' in sel_src
    # 3-arg callback accepts structured face/region hit from CanvasWorkspace.
    assert "selected_hit" in sel_src


def test_home_photos_chrome_demotes_review_and_canvas():
    """Photos browse: Review/Canvas out of primary job bar; purpose is the photo."""
    import semblon.home_ui as home_ui

    sync = inspect.getsource(home_ui.HomeApp._sync_chrome_for_route)
    assert 'photos", "videos"' in sync or "photos" in sync
    assert "Explore workspace" in inspect.getsource(home_ui.HomeApp.__init__) or (
        "Open Review" in inspect.getsource(home_ui.HomeApp.__init__)
    )
    nav = inspect.getsource(home_ui.HomeApp._navigate)
    # Must not dump faces=/items= library log into Photos inspector.
    assert "photos_videos_nothing_selected" not in nav.split('nav_id == "photos"')[1].split(
        'nav_id == "videos"'
    )[0]


def test_home_done_status_clears_clock_telemetry():
    import semblon.home_ui as home_ui

    drain = inspect.getsource(home_ui.HomeApp._drain_queue)
    assert 'self.clock.set("")' in drain
    assert "soft_progress_counts" in drain or "soft_progress_clock" in drain
    assert "product_status_text" in drain
    assert "current_item_line" not in drain
    assert 'bits.append(f"elapsed {elapsed}")' not in drain
    assert "Your photos are ready" in drain
    assert "format_progress_line(" not in drain


def test_home_processing_state_replaces_marketing_landing():
    """PROCESSING Home is its own workspace — not landing + telemetry header."""
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp)
    assert "_build_processing_home" in src
    assert "_home_state" in src
    assert 'return "PROCESSING"' in inspect.getsource(home_ui.HomeApp._home_state)
    show = inspect.getsource(home_ui.HomeApp._show_home_landing)
    assert 'state == "PROCESSING"' in show
    assert "_processing.pack" in show
    sync = inspect.getsource(home_ui.HomeApp._sync_chrome_for_route)
    assert "processing_home" in sync
    # Marketing CTA must not be the processing surface.
    build = inspect.getsource(home_ui.HomeApp._build_processing_home)
    assert "Add a photo folder" not in build
    assert "Building your photo library" in build or "processing_home_headline" in build
    assert '"Cancel"' in build
    assert "Already discovered" in build
    # Substantial bar — not hairline height=4 default.
    assert "height=16" in build or "height=14" in inspect.getsource(home_ui.StillProgressBar.__init__)


def test_home_landing_wraplength_avoids_clipping():
    import semblon.home_ui as home_ui

    build = inspect.getsource(home_ui.HomeApp._build_home_landing)
    assert "wraplength=560" in build
    assert "justify=tk.CENTER" not in build
    assert "width=48" not in build
    assert "width=18" not in build
    assert 'text="Semblon"' not in build
    assert "highlightthickness=1" in build
    assert "_landing_step_cards" in build
    assert "_landing_privacy" in build
    hint = inspect.getsource(home_ui.HomeApp._refresh_landing_hint)
    assert "previously added" not in hint
    assert "landing_cta_plan" in hint
    assert "landing_step_states" in hint
    assert "show_privacy" in hint


def test_landing_cta_plan_first_run_vs_returning():
    from semblon.home_ui import landing_cta_plan, landing_step_states

    empty = landing_cta_plan(files=0, unnamed=0)
    assert empty["primary"] == "add"
    assert empty["show_review"] is False
    assert empty["show_privacy"] is True
    assert empty["add_label"] == "Add a photo folder"

    returning = landing_cta_plan(files=12, unnamed=7)
    assert returning["primary"] == "review"
    assert returning["show_review"] is True
    assert returning["show_browse"] is True
    assert returning["show_privacy"] is False
    assert returning["review_label"] == "Review 7 suggestions"
    assert returning["add_label"] == "Add a photo folder"

    caught_up = landing_cta_plan(files=12, unnamed=0)
    assert caught_up["primary"] == "browse"
    assert caught_up["show_review"] is False
    assert caught_up["show_privacy"] is False
    assert caught_up["add_label"] == "Add another folder"

    first_steps = landing_step_states(files=0, unnamed=0)
    assert [s["phase"] for s in first_steps] == ["current", "idle", "idle"]
    assert first_steps[0]["marker"] == "1"

    mid = landing_step_states(files=5, unnamed=3)
    assert [s["phase"] for s in mid] == ["done", "done", "current"]
    assert mid[0]["marker"] == "✓"
    assert mid[2]["marker"] == "3"

    done = landing_step_states(files=5, unnamed=0)
    assert [s["phase"] for s in done] == ["done", "done", "done"]
    assert all(s["marker"] == "✓" for s in done)
    assert "caught up" in done[2]["desc"].lower()


def test_home_search_while_analysing_is_state_aware():
    import semblon.home_ui as home_ui

    search = inspect.getsource(home_ui.HomeApp._search_person)
    assert "search_library_analysing" in search
    assert "_search_placeholder" in search
    from semblon.empty_states import search_library_analysing

    st = search_library_analysing()
    assert "analysing" in st.headline.lower()
    assert "Error" not in st.headline


def test_home_product_status_path_has_no_filename_leak():
    import semblon.home_ui as home_ui
    import re

    drain = inspect.getsource(home_ui.HomeApp._drain_queue)
    start = inspect.getsource(home_ui.HomeApp._start_process)
    assert "product_status_text" in drain
    assert "product_status_text" in start
    # Must not call legacy ui_copy.status_text in the product path.
    assert re.search(r"(?<![a-z_])status_text\(", drain) is None
    assert re.search(r"(?<![a-z_])status_text\(", start) is None
    assert "current_item_line" not in drain


def test_home_inspector_uses_soft_verbs():
    import semblon.home_ui as home_ui

    init = inspect.getsource(home_ui.HomeApp.__init__)
    assert "Combine face groups" in init or "VERB_LABEL_MERGE" in init
    assert "Name this person" in init or "VERB_LABEL_NAME" in init
    assert "Nothing selected" in init or "SEL_HEADING_IDLE" in init
    assert 'text="Selection"' not in init
    fmt = inspect.getsource(home_ui._format_sel_item)
    assert "soft_sel_item_label" in fmt
    assert "unassigned" not in fmt


def test_home_navigate_home_uses_landing_not_canvas_dump():
    import semblon.home_ui as home_ui

    nav = inspect.getsource(home_ui.HomeApp._navigate)
    assert '_show_home_landing()' in nav
    assert 'nav_id == "home"' in nav
    # Engineering dump must not be the home default anymore.
    assert "compatibility frontend" not in nav
    assert "AppShell" not in nav


def test_counts_from_done_payload():
    from semblon.home_ui import HomeApp

    counts = HomeApp._counts_from_done_payload(
        {
            "ingest": {"files": 340, "faces": 42},
            "cluster": {"clusters": 12},
        }
    )
    assert counts == {"photos": 340, "faces": 42, "groups": 12}
