"""Application façade — RO reads + named JobEngine commands (APP-1 C.2)."""

from __future__ import annotations

import threading
import time

import pytest

from semblon.application import Application, JobBusy, activity, board
from semblon.observers import snapshot_memory_graph
from semblon.process import ProcessCancelled
from semblon.review import name_cluster, name_face
from tests.test_review import _clustered


def test_board_and_activity_are_read_only_facade(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_face(store, "r1", "f5", "Bob")
    snapshot_memory_graph(store, run_id="r1")

    board_rec = board(store, "r1")
    assert board_rec["run_id"] == "r1"
    assert "items" in board_rec
    assert "persons" in board_rec

    act = activity(store, "r1")
    assert act["track_count"] >= 0
    assert "groups" in act
    assert "relationships" in act
    assert "events" in act
    # Activity snapshot is observation-graph RO — not a person enrolment record.
    assert set(act) >= {"groups", "relationships", "events", "track_count"}

    from semblon.application import activity_memory

    mem = activity_memory(store, "r1")
    assert mem["empty"] is False
    soft = "\n".join(
        __import__("semblon.activity_surface", fromlist=["format_activity_memory_lines"])
        .format_activity_memory_lines(mem)
    )
    assert "person_id" not in soft
    assert "observation_groups" not in soft
    assert "Alice" in soft and "Bob" in soft


def test_application_pause_unpause_same_job(tmp_path, monkeypatch):
    entered = threading.Event()
    left_gate = threading.Event()
    app = Application(tmp_path / "s.sqlite")
    seen_handles = []

    def fake_process(folder, **kwargs):
        entered.set()
        cancel = kwargs.get("cancel")
        seen_handles.append(app.job_current())
        deadline = time.monotonic() + 2
        while not app.paused and time.monotonic() < deadline:
            time.sleep(0.01)
        assert app.state == "paused"
        assert cancel() is False
        left_gate.set()
        return {"run_id": "r-app-pause"}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    done = {}

    def on_done(result):
        done["result"] = result

    handle = app.submit_ingest(tmp_path / "photos", on_done=on_done)
    assert entered.wait(1)
    assert app.busy is True
    assert app.state == "running"
    app.pause_job()
    assert app.state == "paused"
    with pytest.raises(JobBusy):
        app.submit_ingest(tmp_path / "photos")
    time.sleep(0.1)
    assert not left_gate.is_set()
    app.unpause_job()
    assert left_gate.wait(2)
    deadline = time.monotonic() + 2
    while "result" not in done and time.monotonic() < deadline:
        time.sleep(0.01)
    assert done["result"].status == "completed"
    assert done["result"].run_id == "r-app-pause"
    assert seen_handles[0] is handle
    assert app.state == "idle"
    assert app.job_current() is None


def test_application_cancel_while_paused(tmp_path, monkeypatch):
    entered = threading.Event()
    app = Application(tmp_path / "s.sqlite")
    done = {}

    def fake_process(folder, **kwargs):
        entered.set()
        cancel = kwargs.get("cancel")
        deadline = time.monotonic() + 2
        while not app.paused and time.monotonic() < deadline:
            time.sleep(0.01)
        assert cancel() is True
        raise ProcessCancelled("cancelled", run_id="r-app-pc")

    monkeypatch.setattr("semblon.process.process_folder", fake_process)

    def on_done(result):
        done["result"] = result

    app.submit_ingest(tmp_path / "photos", on_done=on_done)
    assert entered.wait(1)
    app.pause_job()
    assert app.state == "paused"
    app.cancel_job()
    deadline = time.monotonic() + 3
    while "result" not in done and time.monotonic() < deadline:
        time.sleep(0.01)
    assert done["result"].status == "cancelled"
    assert app.state == "idle"


def test_application_running_to_cancelling(tmp_path, monkeypatch):
    entered = threading.Event()
    app = Application(tmp_path / "s.sqlite")
    done = {}

    def fake_process(folder, **kwargs):
        entered.set()
        cancel = kwargs.get("cancel")
        for _ in range(100):
            if cancel is not None and cancel():
                raise ProcessCancelled("cancelled", run_id="r-app-c")
            time.sleep(0.02)
        return {"run_id": "too-late"}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)

    def on_done(result):
        done["result"] = result

    app.submit_ingest(tmp_path / "photos", on_done=on_done)
    assert entered.wait(1)
    app.cancel_job()
    assert app.state == "cancelling"
    deadline = time.monotonic() + 3
    while "result" not in done and time.monotonic() < deadline:
        time.sleep(0.01)
    assert done["result"].status == "cancelled"


def test_control_states_distinguish_unpause_vs_resume_after_cancel(tmp_path):
    app = Application(tmp_path / "s.sqlite")
    idle = app.control_states(resume_ready=False)
    assert idle["pause"] == "disabled"
    assert idle["resume"] == "disabled"
    assert idle["folder"] == "normal"

    ready = app.control_states(resume_ready=True)
    assert ready["resume"] == "normal"
    assert ready["pause"] == "disabled"
