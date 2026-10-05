"""ARCH-011 / APP-1 — JobEngine is the ingest door. No InsightFace."""

from __future__ import annotations

import inspect
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from semblon.home_ui import HOME_CONTROLS_ALWAYS_ON, HomeApp, home_control_states
from semblon.jobs import JobBusy, JobEngine
from semblon.process import ProcessCancelled
from semblon.review import name_cluster
from semblon.review_ui import ReviewApp, _ro_connect, load_board, make_review_root, resolve_run_id
from tests.test_review import _clustered


def test_second_submit_is_job_busy(tmp_path, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    def fake_process(folder, **kwargs):
        calls["n"] += 1
        started.set()
        if not release.wait(2):
            raise RuntimeError("test gate timed out")
        return {"run_id": "r-job", "out": None}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    engine = JobEngine(tmp_path / "s.sqlite")
    folder = tmp_path / "photos"
    folder.mkdir()
    engine.submit_ingest(folder)
    assert started.wait(1)
    assert engine.busy is True
    with pytest.raises(JobBusy, match="already running"):
        engine.submit_ingest(folder)
    assert calls["n"] == 1
    release.set()
    deadline = time.monotonic() + 2
    while engine.busy and time.monotonic() < deadline:
        time.sleep(0.01)
    assert engine.busy is False
    started.clear()
    engine.submit_ingest(folder)
    assert started.wait(1)
    assert calls["n"] == 2
    release.set()


def test_run_ingest_passes_cancel_and_observers(tmp_path, monkeypatch):
    saw = {}

    def fake_process(folder, **kwargs):
        saw["cancel"] = kwargs.get("cancel")
        saw["observers"] = kwargs.get("observers")
        saw["resume"] = kwargs.get("resume")
        return {"run_id": "r-ok"}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    engine = JobEngine(tmp_path / "s.sqlite")
    rec = engine.run_ingest(tmp_path / "photos", observers="face,color,object", resume=True)
    assert rec["run_id"] == "r-ok"
    assert saw["observers"] == "face,color,object"
    assert saw["resume"] is True
    assert saw["cancel"] is not None
    assert saw["cancel"]() is False


def test_cancel_stops_submitted_ingest(tmp_path, monkeypatch):
    entered = threading.Event()
    done = {}

    def fake_process(folder, **kwargs):
        entered.set()
        for _ in range(100):
            cancel = kwargs.get("cancel")
            if cancel is not None and cancel():
                raise ProcessCancelled("cancelled", run_id="r-c")
            time.sleep(0.02)
        return {"run_id": "too-late"}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    engine = JobEngine(tmp_path / "s.sqlite")

    def on_done(result):
        done["result"] = result

    engine.submit_ingest(tmp_path / "photos", on_done=on_done)
    assert entered.wait(1)
    engine.cancel()
    deadline = time.monotonic() + 3
    while "result" not in done and time.monotonic() < deadline:
        time.sleep(0.01)
    assert done["result"].status == "cancelled"
    assert done["result"].run_id == "r-c"
    assert engine.busy is False


def test_submit_ingest_reports_cancelled(tmp_path, monkeypatch):
    done = {}
    gate = threading.Event()

    def fake_process(folder, **kwargs):
        gate.wait(2)
        raise ProcessCancelled("cancelled", run_id="r-c")

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    engine = JobEngine(tmp_path / "s.sqlite")

    def on_done(result):
        done["result"] = result

    engine.submit_ingest(tmp_path / "photos", on_done=on_done)
    gate.set()
    deadline = time.monotonic() + 2
    while "result" not in done and time.monotonic() < deadline:
        time.sleep(0.01)
    assert done["result"].status == "cancelled"
    assert done["result"].run_id == "r-c"
    assert engine.busy is False


def test_home_control_states_are_job_control_not_app_lock():
    running = home_control_states(job_running=True, resume_ready=True)
    assert running["folder"] == "disabled"
    assert running["resume"] == "disabled"
    assert running["pause"] == "normal"
    assert running["cancel"] == "normal"
    for name in HOME_CONTROLS_ALWAYS_ON:
        assert running[name] == "normal", name

    paused = home_control_states(job_running=True, job_paused=True, resume_ready=False)
    assert paused["pause"] == "disabled"
    assert paused["resume"] == "normal"
    assert paused["cancel"] == "normal"
    assert paused["folder"] == "disabled"
    for name in HOME_CONTROLS_ALWAYS_ON:
        assert paused[name] == "normal", name

    idle = home_control_states(job_running=False, resume_ready=False)
    assert idle["folder"] == "normal"
    assert idle["resume"] == "disabled"
    assert idle["pause"] == "disabled"
    assert idle["cancel"] == "disabled"
    assert idle["review"] == "normal"

    ready = home_control_states(job_running=False, resume_ready=True)
    assert ready["resume"] == "normal"
    assert ready["pause"] == "disabled"


def test_pause_blocks_until_unpause(tmp_path, monkeypatch):
    entered = threading.Event()
    left_gate = threading.Event()
    engine = JobEngine(tmp_path / "s.sqlite")

    def fake_process(folder, **kwargs):
        entered.set()
        cancel = kwargs.get("cancel")
        assert cancel is not None
        deadline = time.monotonic() + 2
        while not engine.paused and time.monotonic() < deadline:
            time.sleep(0.01)
        assert engine.paused is True
        # Gate blocks here until unpause; then returns False (not cancelled).
        assert cancel() is False
        left_gate.set()
        return {"run_id": "r-pause"}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    done = {}

    def on_done(result):
        done["result"] = result

    engine.submit_ingest(tmp_path / "photos", on_done=on_done)
    assert entered.wait(1)
    engine.pause()
    assert engine.state == "paused"
    assert engine.busy is True
    with pytest.raises(JobBusy):
        engine.submit_ingest(tmp_path / "photos")
    time.sleep(0.15)
    assert not left_gate.is_set()
    assert "result" not in done
    engine.unpause()
    assert left_gate.wait(2)
    deadline = time.monotonic() + 2
    while "result" not in done and time.monotonic() < deadline:
        time.sleep(0.01)
    assert done["result"].status == "completed"
    assert done["result"].run_id == "r-pause"
    assert engine.busy is False
    assert engine.state == "idle"


def test_cancel_while_paused(tmp_path, monkeypatch):
    entered = threading.Event()
    saw_pause = threading.Event()
    engine = JobEngine(tmp_path / "s.sqlite")
    done = {}

    def fake_process(folder, **kwargs):
        entered.set()
        cancel = kwargs.get("cancel")
        deadline = time.monotonic() + 2
        while not engine.paused and time.monotonic() < deadline:
            time.sleep(0.01)
        if engine.paused:
            saw_pause.set()
        # Blocks while paused; returns True once cancel unblocks the gate.
        assert cancel() is True
        raise ProcessCancelled("cancelled", run_id="r-pc")

    monkeypatch.setattr("semblon.process.process_folder", fake_process)

    def on_done(result):
        done["result"] = result

    engine.submit_ingest(tmp_path / "photos", on_done=on_done)
    assert entered.wait(1)
    engine.pause()
    assert saw_pause.wait(2)
    engine.cancel()
    deadline = time.monotonic() + 3
    while "result" not in done and time.monotonic() < deadline:
        time.sleep(0.01)
    assert done["result"].status == "cancelled"
    assert done["result"].run_id == "r-pc"
    assert engine.busy is False
    assert engine.state == "idle"


def test_home_pause_and_unpause_wired():
    src = inspect.getsource(HomeApp)
    assert "_request_pause" in src
    assert "pause_job" in src
    assert "unpause_job" in src
    assert "engine.pause" not in src
    assert "engine.unpause" not in src
    assert "btn_pause" in src


def test_home_submits_through_job_engine():
    src = inspect.getsource(HomeApp)
    assert "submit_ingest" in src
    assert "JobBusy" in src
    init = inspect.getsource(HomeApp.__init__)
    assert "Application(" in init
    assert "self.engine = self.app.engine" in init
    assert "JobEngine(" not in init
    open_src = inspect.getsource(HomeApp._open_review_ui)
    assert "parent=self.root" in open_src
    assert "withdraw" not in open_src
    assert ".mainloop(" not in open_src
    busy_src = inspect.getsource(HomeApp._set_busy)
    assert "_refresh_job_controls" in busy_src
    refresh_src = inspect.getsource(HomeApp._refresh_job_controls)
    assert "home_control_states" in refresh_src
    assert "job_paused" in refresh_src


def test_review_root_is_toplevel_on_parent():
    class FakeTk:
        def __init__(self):
            self.kind = "tk"

    class FakeToplevel:
        def __init__(self, parent):
            self.kind = "toplevel"
            self.parent = parent

    class FakeMod:
        Tk = FakeTk
        Toplevel = FakeToplevel

    child, owns = make_review_root(parent="home-root", tk_mod=FakeMod)
    assert owns is False
    assert child.kind == "toplevel"
    assert child.parent == "home-root"
    standalone, owns = make_review_root(parent=None, tk_mod=FakeMod)
    assert owns is True
    assert standalone.kind == "tk"
    run_src = inspect.getsource(ReviewApp.run)
    assert "if self._owns_loop" in run_src
    workers = Path(__file__).resolve().parents[1] / "semblon" / "jobs.py"
    text = workers.read_text(encoding="utf-8")
    assert "JobEngine" in text
    assert "submit_ingest" in text


def test_review_reads_set_busy_timeout(tmp_path):
    store = tmp_path / "s.sqlite"
    _clustered(store)
    conn = _ro_connect(store)
    timeout = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])
    conn.close()
    assert timeout == 5000
    board = load_board(store, "r1")
    assert board["run_id"] == "r1"
    assert resolve_run_id(store, "r1") == "r1"


def test_review_mutation_waits_on_existing_writer(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    writer = sqlite3.connect(str(store))
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("UPDATE runs SET software_version=software_version")
    finished = {}

    def mutate():
        try:
            name_cluster(store, "r1", assigned["f1"], "Alice")
            finished["ok"] = True
        except Exception as e:  # noqa: BLE001 — capture for the assertion
            finished["err"] = e

    t = threading.Thread(target=mutate)
    t.start()
    blocked = False
    for _ in range(20):
        time.sleep(0.05)
        if t.is_alive() and "ok" not in finished:
            blocked = True
            break
    assert blocked, finished
    writer.commit()
    writer.close()
    t.join(3)
    assert finished.get("ok") is True
    assert "err" not in finished
