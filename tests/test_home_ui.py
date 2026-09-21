"""Home activity semantics readers + Track-1 control policy."""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

import pytest

from semblon.home_ui import format_activity_lines, home_control_states, read_activity_snapshot
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
    lines = format_activity_lines(
        run_line="run=r1",
        integrity_line="integrity ok=1 unfinished=0",
        groups=rec["groups"],
        relationships=rec["relationships"],
        events=rec["events"],
        track_count=rec["track_count"],
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
