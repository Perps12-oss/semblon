"""Job boundary and Home control policy. No FaceKit. No live ingest."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from semblon.jobs import (
    STATE_CANCELLED,
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_QUEUED,
    STATE_RUNNING,
    JobBusy,
    JobEngine,
    JobSnapshot,
    home_control_states,
    snapshot_from_event,
)
from semblon.process import ProcessCancelled
from semblon.progress import KIND_PROGRESS, STAGE_INGEST, make_event


def test_home_keeps_read_surfaces_on_during_job():
    busy = home_control_states(job_active=True, resume_ready=False)
    idle = home_control_states(job_active=False, resume_ready=True)
    for name in ("review", "people", "search", "unknown", "activity", "settings", "canvas", "html"):
        assert busy[name] == "normal"
        assert idle[name] == "normal"
    assert busy["folder"] == "disabled"
    assert busy["resume"] == "disabled"
    assert busy["cancel"] == "normal"
    assert idle["folder"] == "normal"
    assert idle["resume"] == "normal"
    assert idle["cancel"] == "disabled"


def test_snapshot_is_json_safe_and_does_not_invent_counts():
    snap = JobSnapshot(job_id="j1", type="ingest", state=STATE_QUEUED, source="/photos")
    ev = make_event(STAGE_INGEST, KIND_PROGRESS, files_processed=3, files_total=10, faces_found=4)
    out = snapshot_from_event(snap, ev)
    d = out.to_dict()
    assert d["files_processed"] == 3
    assert d["files_total"] == 10
    assert d["faces"] == 4
    assert d["failed"] is None
    assert "root" not in d
    assert out.state == STATE_RUNNING


def test_engine_rejects_second_ingest(tmp_path, monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def fake_process(*_a, **kw):
        started.set()
        release.wait(timeout=2)
        return {"run_id": "r-fake", "out": str(tmp_path / "review.html")}

    monkeypatch.setattr("semblon.jobs.process_folder", fake_process)
    eng = JobEngine()
    folder = tmp_path / "pics"
    folder.mkdir()
    store = tmp_path / "s.sqlite"
    eng.submit_ingest(folder, store)
    assert started.wait(timeout=2)
    with pytest.raises(JobBusy):
        eng.submit_ingest(folder, store)
    release.set()
    if eng._thread is not None:
        eng._thread.join(timeout=2)
    assert eng.snapshot().state == STATE_COMPLETED


def test_engine_cancel_maps_to_cancelled(tmp_path, monkeypatch):
    def fake_process(*_a, **kw):
        cancel = kw.get("cancel")
        if cancel is not None:
            pass
        raise ProcessCancelled("process cancelled", run_id="r-c")

    monkeypatch.setattr("semblon.jobs.process_folder", fake_process)
    eng = JobEngine()
    folder = tmp_path / "pics"
    folder.mkdir()
    cancelled = []
    eng.submit_ingest(
        folder,
        tmp_path / "s.sqlite",
        on_cancelled=cancelled.append,
    )
    if eng._thread is not None:
        eng._thread.join(timeout=2)
    assert eng.snapshot().state == STATE_CANCELLED
    assert cancelled == ["r-c"]


def test_engine_failure_is_failed_not_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "semblon.jobs.process_folder",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    eng = JobEngine()
    folder = tmp_path / "pics"
    folder.mkdir()
    errors = []
    eng.submit_ingest(folder, tmp_path / "s.sqlite", on_error=errors.append)
    if eng._thread is not None:
        eng._thread.join(timeout=2)
    assert eng.snapshot().state == STATE_FAILED
    assert errors and "boom" in str(errors[0])


def test_application_facade_exports_board_ops():
    from semblon import application as app

    assert app.load_board is not None
    assert app.apply_name is not None
    assert app.JobEngine is JobEngine
    assert app.search_people is not None
    assert app.inbox is not None
    assert callable(app.board)