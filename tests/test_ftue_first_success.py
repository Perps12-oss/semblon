"""FTUE / first-success closure — lifecycle, naming door, empties, Stage CTA."""

from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import semblon.home_ui as home_ui
from semblon import empty_states, fluid_shell, home_completion


def test_cold_ingest_zero_files_shows_processing():
    """files == 0 + ingesting == True must enter processing, not Stage."""
    show = inspect.getsource(home_ui.HomeApp._show_library_or_onboard)
    assert "_ingest_running" in show
    assert "_show_processing_home" in show
    start = inspect.getsource(home_ui.HomeApp._start_process)
    assert "_show_processing_home" in start
    # Must not route cold ingest through Stage via library_or_onboard alone.
    assert "_show_processing_home()" in start


def test_completion_wires_result_card_not_landing():
    drain = inspect.getsource(home_ui.HomeApp._drain_queue)
    assert "_show_result_card" in drain
    assert "save_unseen_completion" in drain
    assert "_fill_result_card" in inspect.getsource(home_ui.HomeApp)
    fill = inspect.getsource(home_ui.HomeApp._fill_result_card)
    assert "Start naming" in fill or "_ack_completion_go_to_name" in inspect.getsource(
        home_ui.HomeApp._build_result_card_shell
    )
    assert "Select Different Folder" in fill or "Select Different Folder" in inspect.getsource(
        home_ui.HomeApp._build_result_card_shell
    )


def test_completion_variants_in_fill_result_card():
    fill = inspect.getsource(home_ui.HomeApp._fill_result_card)
    assert 'kind == "empty"' in fill or "No supported photos" in fill
    assert "partial" in fill
    assert "interrupted" in fill
    assert "cancelled" in fill
    assert "didn't find any faces" in fill
    counts = home_ui.HomeApp._counts_from_done_payload(
        {
            "run_id": "r1",
            "ingest": {"files": 10, "faces": 0, "failed": 2, "new_media": 10},
            "cluster": {"clusters": 0},
        }
    )
    assert counts["photos"] == 10
    assert counts["failed"] == 2
    assert counts["faces"] == 0


def test_restart_persistence_schema_meta(tmp_path: Path):
    store = tmp_path / "store.sqlite"
    conn = sqlite3.connect(str(store))
    conn.execute(
        "CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.execute(
        """CREATE TABLE runs (
             run_id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT,
             software_version TEXT, pack_id TEXT, embedding_dim INTEGER,
             embedding_norm TEXT, config_json TEXT, runtime_json TEXT,
             arch TEXT, execution TEXT)"""
    )
    conn.commit()
    conn.close()

    payload = {"run_id": "r-done", "photos": 3, "faces": 2, "groups": 1, "failed": 0}
    home_completion.save_unseen_completion(store, kind="done", payload=payload)
    unseen = home_completion.load_unseen_completion(store)
    assert unseen is not None
    assert unseen["kind"] == "done"
    assert unseen["payload"]["photos"] == 3

    home_completion.acknowledge_completion(store, "r-done")
    assert home_completion.load_unseen_completion(store) is None

    # Restart during ingest: unfinished run + folder from config_json.
    conn = sqlite3.connect(str(store))
    conn.execute(
        """INSERT INTO runs(
             run_id, started_at, finished_at, software_version, pack_id,
             embedding_dim, embedding_norm, config_json, runtime_json,
             arch, execution)
           VALUES (?,?,NULL,'1','p',512,'l2',?,?, 'x64','native')""",
        (
            "r-open",
            "2026-01-01T00:00:00Z",
            json.dumps({"folder": str(tmp_path / "photos")}),
            "{}",
        ),
    )
    conn.commit()
    conn.close()
    info = home_completion.latest_unfinished_run_info(store)
    assert info is not None
    assert info["run_id"] == "r-open"
    assert info["folder"] is not None


def test_worker_callbacks_queue_only():
    start = inspect.getsource(home_ui.HomeApp._start_process)
    # on_event / on_done must only put on the queue.
    assert 'self._q.put(("event", ev))' in start
    assert 'self._q.put(("done"' in start
    assert "winfo_" not in start.split("def on_event")[1].split("def on_done")[0]
    assert "configure(" not in start.split("def on_done")[1].split("try:")[0]


def test_to_name_is_canonical_naming_door():
    assert fluid_shell.people_chrome_label(0) == "People"
    assert fluid_shell.people_chrome_label(4) == "To name (4)"
    banner = fluid_shell.people_review_banner(3)
    assert banner is not None
    assert "face groups" in banner
    assert "waiting to be named" in banner
    chrome = inspect.getsource(home_ui.HomeApp._build_library_chrome)
    assert "Start naming" in chrome
    src = inspect.getsource(home_ui.HomeApp)
    assert 'lambda: self._navigate("unknown")' in src or "_open_people_mode" in src
    # No user-visible Open Review label in Home chrome.
    init = inspect.getsource(home_ui.HomeApp.__init__)
    assert "Open Review" not in init
    assert "Open Review" not in (empty_states.people_empty().primary_action or "")
    assert empty_states.search_no_named_people().primary_action == "Start naming"
    assert empty_states.search_no_named_people().action_id == empty_states.ACTION_REVIEW_PEOPLE
    pe = empty_states.people_empty()
    assert pe.tertiary_action != "Open Review"
    assert "Open Review" not in (pe.primary_action or "")


def test_stage_single_add_folder_cta():
    stage = inspect.getsource(home_ui.HomeApp._show_stage)
    assert stage.count("STAGE_CTA") >= 1
    assert stage.count("_choose_folder") == 1
    sync = inspect.getsource(home_ui.HomeApp._sync_chrome_for_route)
    assert "on_stage" in sync
    assert "btn_folder.pack_forget" in sync


def test_interactive_empty_states_bind_actions():
    assert hasattr(home_ui.HomeApp, "_mount_workspace_empty")
    assert hasattr(home_ui.HomeApp, "_dispatch_empty_action")
    assert hasattr(home_ui.HomeApp, "_offer_empty_action")
    people = inspect.getsource(home_ui.HomeApp._show_people)
    assert "_mount_workspace_empty" in people
    unknown = inspect.getsource(home_ui.HomeApp._show_unknown)
    assert "_mount_workspace_empty" in unknown
    mount = inspect.getsource(empty_states.mount_empty_state)
    assert "command=on_primary" in mount


def test_restore_home_lifecycle_exists():
    assert hasattr(home_ui.HomeApp, "_restore_home_lifecycle")
    init = inspect.getsource(home_ui.HomeApp.__init__)
    assert "_restore_home_lifecycle" in init
    restore = inspect.getsource(home_ui.HomeApp._restore_home_lifecycle)
    assert "load_unseen_completion" in restore
    assert "latest_unfinished_run_info" in restore


def test_progressive_disclosure_hides_advanced_before_media():
    rebuild = inspect.getsource(home_ui.HomeApp._rebuild_overflow_menu)
    assert "shell.live" in rebuild or "Live…" in rebuild
    assert "has_media" in rebuild or "_library_has_media" in rebuild
    settings = inspect.getsource(home_ui.HomeApp._fill_settings_body)
    assert "_library_has_media" in settings
    assert "Packs" in settings
