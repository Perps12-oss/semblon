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
    for name in ("review", "people", "search", "unknown", "activity", "settings", "live"):
        assert busy[name] == "normal"
    assert "html" not in busy
    assert "canvas" not in busy
    assert busy["folder"] == "disabled"
    assert busy["cancel"] == "normal"
    assert busy["pause"] == "normal"
    assert busy["resume"] == "disabled"

    paused = home_control_states(job_running=True, job_paused=True, resume_ready=False)
    assert paused["pause"] == "disabled"
    assert paused["resume"] == "normal"
    assert paused["cancel"] == "normal"


def test_home_nav_labels_ux_rescue():
    """Model D — compact destinations Library · People · Activity; Lens off MAIN."""
    flat = {nav_id: label for _sec, items in HOME_NAV for nav_id, label in items}
    assert flat["library"] == "Library"
    assert flat["people"] == "People"
    assert flat["activity"] == "Activity"
    assert "unknown" not in flat
    assert "lens" not in flat
    assert "home" not in flat or flat.get("home") != "Photos"


def test_narrow_window_keeps_a_rail():
    from semblon.home_ui import shell_is_condensed

    assert shell_is_condensed(900) is True
    assert shell_is_condensed(1100) is False


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
    assert "activity_memory" in src or "show_activity_page" in src
    assert "_build_activity_workspace" in src
    assert "_refresh_activity_workspace" in src
    assert "gui_registry" in src or "default_registry" in src or "_registry" in src
    assert "inspector_verbs" in src or "Merge observations" in src
    # UX Rescue landing + settings + result card.
    assert "_show_home_landing" in src
    assert "Add Folder" in src or "Select Photo Folder" in src
    assert "SHELL_HEADLINE" in src or "Welcome to Semblon" in src or "_show_onboarding" in src
    assert "_refresh_library_shell" in src or "_refresh_footer" in src
    assert "open_advanced_diagnostics" in src
    assert "Your photos are ready" in src
    assert "Start naming" in src or "Review people" in src or "Review People" in src


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


def test_home_settings_uses_hero_font_and_shared_inspector_width():
    """Fluent Settings title + reserved inspector column share review tokens."""
    import semblon.home_ui as home_ui
    from semblon import ui_tokens

    assert home_ui.HERO == ui_tokens.HERO
    assert home_ui.INSPECTOR_WIDTH == 320
    assert ui_tokens.INSPECTOR_WIDTH == 320
    fill = inspect.getsource(home_ui.HomeApp._fill_settings_body)
    assert "font=HERO" in fill
    assert "minsize=INSPECTOR_WIDTH" in inspect.getsource(
        home_ui.HomeApp._set_inspector_collapsed
    )


def test_home_settings_is_user_panel_not_dump():
    """§6 — Settings is an in-shell workspace route; diagnostics go to Diagnostics."""
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp._show_settings)
    fill = inspect.getsource(home_ui.HomeApp._fill_settings_body)
    build = inspect.getsource(home_ui.HomeApp._build_settings_workspace)
    assert "Advanced diagnostics" in fill or "SETTINGS_OPEN_DIAGNOSTICS" in fill
    assert "Library location" in fill or "SETTINGS_LIBRARY" in fill
    assert "Use GPU when available" in fill or "SETTINGS_GPU" in fill or "Processing on this computer" in fill or "SETTINGS_PROCESSING_CPU" in fill
    assert "SETTINGS_DIAGNOSTICS" in fill or "Diagnostics" in fill
    assert "SETTINGS_RESET_BUTTON" in fill or "Reset app" in fill
    assert "SETTINGS_RECOVERY" in fill
    assert "SETTINGS_GRID_DENSITY" in fill
    assert "SETTINGS_SEARCH_MODE" in fill
    assert "_reset_app_to_defaults" in fill
    # Reset is on-demand under Advanced → Recovery, not an everyday top section.
    reset_at = fill.index("SETTINGS_RESET_BUTTON")
    advanced_at = fill.index("SETTINGS_ADVANCED")
    assert advanced_at < reset_at
    assert "format_execution_status_lines" not in fill
    assert "weights_status" not in fill
    assert "buffalo_l" not in fill
    # Workspace route — not a popup.
    assert "Toplevel" not in src
    assert "_settings_win" not in src
    assert "_settings.pack" in src or "self._settings.pack" in src
    assert "_navigate(\"settings\")" in inspect.getsource(home_ui.HomeApp.__init__)
    assert 'text="Theme"' in fill
    assert "self._on_theme_row" in fill
    assert "Save theme" in fill
    assert "Canvas" in build
    assert "_hide_workspace_panes" in src

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
    init = inspect.getsource(home_ui.HomeApp.__init__)
    assert "Explore workspace" in init or "Start naming" in init or "btn_review" in init
    assert "Open Review" not in init
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
    """While ingest runs, processing pane replaces Stage even when files == 0."""
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp)
    assert "_build_processing_home" in src
    assert "_home_state" in src
    assert 'return "PROCESSING"' in inspect.getsource(home_ui.HomeApp._home_state)
    show = inspect.getsource(home_ui.HomeApp._show_home_landing)
    assert "_show_library_or_onboard" in show
    start = inspect.getsource(home_ui.HomeApp._start_process)
    assert "_show_processing_home" in start
    onboard = inspect.getsource(home_ui.HomeApp._show_library_or_onboard)
    assert "_show_processing_home" in onboard
    sync = inspect.getsource(home_ui.HomeApp._sync_chrome_for_route)
    # Busy path must pack Pause/Cancel even on Library / Memory Canvas.
    assert "btn_pause_toggle.pack" in sync
    assert "btn_cancel_prog.pack" in sync
    assert "if busy:" in sync
    assert "not processing_home" not in sync
    build = inspect.getsource(home_ui.HomeApp._build_processing_home)
    assert "Add a photo folder" not in build
    assert "Building your photo library" in build or "processing_home_headline" in build
    assert '"Cancel"' in build
    assert "Already discovered" in build
    assert "height=16" in build or "height=14" in inspect.getsource(home_ui.StillProgressBar.__init__)


def test_library_busy_exposes_pause_resume_cancel_controls():
    """Memory Canvas / Library ingest must show JobEngine Pause/Cancel chrome."""
    import semblon.home_ui as home_ui

    sync = inspect.getsource(home_ui.HomeApp._sync_chrome_for_route)
    assert "_ingest_running" in sync
    # When busy, progress Pause/Cancel are packed (not gated off by on_library).
    busy_block = sync.split("if busy:")[1].split("else:")[0]
    assert "btn_pause_toggle.pack" in busy_block
    assert "btn_cancel_prog.pack" in busy_block
    idle_block = sync.split("if busy:")[1].split("else:", 1)[1]
    assert "pack_forget" in idle_block
    assert home_ui.HomeApp._toggle_pause_resume is not None
    assert home_ui.HomeApp._request_cancel is not None
    assert home_ui.HomeApp._resume is not None


def test_home_landing_wraplength_avoids_clipping():
    import semblon.home_ui as home_ui

    stage = inspect.getsource(home_ui.HomeApp._show_stage)
    assert "wraplength=720" in stage or "wraplength=640" in stage
    assert "justify=tk.CENTER" not in stage
    assert "STAGE_HEADLINE" in stage
    assert "STAGE_PRIVACY" in stage
    hint = inspect.getsource(home_ui.HomeApp._refresh_landing_hint)
    assert "previously added" not in hint
    assert "landing_cta_plan" in hint


def test_populated_home_skips_first_run_marketing():
    """Populated launch goes to Memory Canvas, not a permanent capability dashboard."""
    import semblon.home_ui as home_ui

    show = inspect.getsource(home_ui.HomeApp._show_home_landing)
    assert "_show_library_or_onboard" in show
    stage = inspect.getsource(home_ui.HomeApp._show_stage)
    assert "STAGE_HEADLINE" in stage
    assert "Find the people in your photos" not in stage
    lib = inspect.getsource(home_ui.HomeApp._show_library)
    assert "_library_filter" in lib
    assert "_set_inspector_collapsed(True)" in lib
    chrome = inspect.getsource(home_ui.HomeApp._build_library_chrome)
    assert "LIBRARY_FILTERS" in chrome or "_lib_filter_buttons" in chrome


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
    assert returning["review_label"] == "Review 7 people to name"
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
    # Save identity is a primary button — not Enter-only on a grey Add to person.
    assert 'f"btn_{key}"' in init or "btn_name" in init
    assert "self._inspector_name_commit" in init
    refresh = inspect.getsource(home_ui.HomeApp._refresh_inspector_verbs)
    assert "_sync_name_save_button" in refresh
    sync = inspect.getsource(home_ui.HomeApp._sync_name_save_button)
    assert "btn_name" in sync
    assert "strip()" in sync
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
    assert counts["photos"] == 340
    assert counts["faces"] == 42
    assert counts["groups"] == 12
    assert counts.get("failed", 0) == 0


def test_home_ui_token_names_are_bound():
    """Regression: SP_20 / INK_SECONDARY style NameErrors on Windows launch."""
    import re
    from pathlib import Path

    import semblon.home_ui as home_ui

    src = Path("semblon/home_ui.py").read_text(encoding="utf-8")
    used = set(
        re.findall(
            r"\b((?:SP|BG|INK|TEXT|BORDER|ACCENT|SURFACE)_[A-Z0-9_]+|"
            r"SIDEBAR_WIDTH|WINDOW_DEFAULT|WINDOW_MIN|SUCCESS|DISPLAY|"
            r"H1|H2|H3|BODY|BODY_SMALL|BODY_STRONG|CAPTION|META|MONO)\b",
            src,
        )
    )
    import_block = re.search(r"from semblon\.ui_tokens import \((.*?)\)", src, re.S)
    assert import_block is not None
    imported = set(re.findall(r"[A-Z][A-Z0-9_]*", import_block.group(1)))
    # Mid-merge stub sits in the same try/except as the ui_tokens import.
    stub_region = src[import_block.end() : import_block.end() + 2500]
    stubbed = set(re.findall(r"^    ([A-Z][A-Z0-9_]*) =", stub_region, re.M))
    missing_import = sorted(used - imported)
    missing_stub = sorted(used - stubbed)
    assert missing_import == [], f"used but not imported from ui_tokens: {missing_import}"
    assert missing_stub == [], f"used but not in ImportError stub: {missing_stub}"
    # Module must actually bind tokens used by HomeApp chrome.
    assert getattr(home_ui, "INK_SECONDARY")
    assert getattr(home_ui, "SP_20")
