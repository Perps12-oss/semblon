"""R2 IPC probe — external client <-> loopback <-> JobEngine. No InsightFace."""

from __future__ import annotations

import threading
import time

import pytest

from semblon.ipc_probe import PROTOCOL, IpcProbeClient, IpcProbeServer
from semblon.process import ProcessCancelled
from semblon.progress import KIND_STARTED, STAGE_INGEST, ProgressEvent


def test_probe_refuses_non_loopback(tmp_path):
    server = IpcProbeServer(tmp_path / "s.sqlite", host="0.0.0.0", port=0)
    with pytest.raises(ValueError, match="loopback"):
        server.start()


def test_ping_status_and_unknown_op(tmp_path):
    with IpcProbeServer(tmp_path / "s.sqlite") as server:
        assert server.bound_port is not None
        with IpcProbeClient(port=server.bound_port, token=server.token) as client:
            ping = client.request("ping", req_id=1)
            assert ping["ok"] is True
            assert ping["protocol"] == PROTOCOL
            status = client.request("status", req_id=2)
            assert status["ok"] is True
            assert status["state"] == "idle"
            assert status["busy"] is False
            assert status["current"] is None
            bad = client.request("nope", req_id=3)
            assert bad["ok"] is False
            assert bad["error"]["type"] == "ProtocolError"


def test_submit_progress_cancel_result(tmp_path, monkeypatch):
    entered = threading.Event()
    events: list[ProgressEvent] = []

    def fake_process(folder, **kwargs):
        on_event = kwargs.get("on_event")
        if on_event is not None:
            ev = ProgressEvent(stage=STAGE_INGEST, kind=KIND_STARTED, run_id="r-ipc")
            events.append(ev)
            on_event(ev)
        entered.set()
        for _ in range(100):
            cancel = kwargs.get("cancel")
            if cancel is not None and cancel():
                raise ProcessCancelled("cancelled", run_id="r-ipc")
            time.sleep(0.02)
        return {"run_id": "too-late"}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    folder = tmp_path / "photos"
    folder.mkdir()

    with IpcProbeServer(tmp_path / "s.sqlite") as server:
        with IpcProbeClient(port=server.bound_port, token=server.token) as client:
            submit = client.request("submit_ingest", req_id=10, folder=str(folder))
            assert submit["ok"] is True
            assert submit["handle"]["folder"] == str(folder)
            assert entered.wait(2)

            status = client.request("status", req_id=11)
            assert status["busy"] is True
            assert status["state"] in ("running", "cancelling", "paused")

            busy = client.request("submit_ingest", req_id=12, folder=str(folder))
            assert busy["ok"] is False
            assert busy["error"]["type"] == "JobBusy"

            cancel = client.request("cancel", req_id=13)
            assert cancel["ok"] is True

            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                client.drain(timeout=0.1)
                if client.done:
                    break
                time.sleep(0.05)
            assert client.done
            assert client.done[-1]["result"]["status"] == "cancelled"
            assert client.done[-1]["result"]["run_id"] == "r-ipc"
            assert any(p.get("event", {}).get("kind") == KIND_STARTED for p in client.progress)

            result = client.request("result", req_id=14)
            assert result["ok"] is True
            assert result["result"]["status"] == "cancelled"

            idle = client.request("status", req_id=15)
            assert idle["busy"] is False
            assert idle["state"] == "idle"


def test_pause_unpause_via_ipc(tmp_path, monkeypatch):
    entered = threading.Event()
    left_gate = threading.Event()

    with IpcProbeServer(tmp_path / "s.sqlite") as server:
        engine = server.engine

        def fake_process(folder, **kwargs):
            entered.set()
            cancel = kwargs.get("cancel")
            assert cancel is not None
            deadline = time.monotonic() + 2
            while not engine.paused and time.monotonic() < deadline:
                time.sleep(0.01)
            assert engine.paused is True
            assert cancel() is False
            left_gate.set()
            return {"run_id": "r-pause"}

        monkeypatch.setattr("semblon.process.process_folder", fake_process)
        folder = tmp_path / "photos"
        folder.mkdir()

        with IpcProbeClient(port=server.bound_port, token=server.token) as client:
            assert client.request("submit_ingest", req_id=20, folder=str(folder))["ok"] is True
            assert entered.wait(2)
            assert client.request("pause", req_id=21)["ok"] is True
            st = client.request("status", req_id=22)
            assert st["state"] == "paused"
            assert st["paused"] is True
            time.sleep(0.15)
            assert not left_gate.is_set()
            assert client.request("unpause", req_id=23)["ok"] is True
            assert left_gate.wait(2)
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                client.drain(timeout=0.05)
                if client.done:
                    break
                time.sleep(0.02)
            assert client.done[-1]["result"]["status"] == "completed"
            assert client.done[-1]["result"]["run_id"] == "r-pause"


def test_failed_result_via_ipc(tmp_path, monkeypatch):
    def fake_process(folder, **kwargs):
        raise RuntimeError("boom-ipc")

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    folder = tmp_path / "photos"
    folder.mkdir()

    with IpcProbeServer(tmp_path / "s.sqlite") as server:
        with IpcProbeClient(port=server.bound_port, token=server.token) as client:
            assert client.request("submit_ingest", req_id=40, folder=str(folder))["ok"] is True
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                client.drain(timeout=0.05)
                if client.done:
                    break
                time.sleep(0.02)
            assert client.done[-1]["result"]["status"] == "failed"
            assert "boom-ipc" in (client.done[-1]["result"]["error"] or {}).get("message", "")
            got = client.request("result", req_id=41)
            assert got["result"]["status"] == "failed"


def test_submit_resume_flag_and_json_error(tmp_path, monkeypatch):
    saw = {}

    def fake_process(folder, **kwargs):
        saw["resume"] = kwargs.get("resume")
        return {"run_id": "r-resume"}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    folder = tmp_path / "photos"
    folder.mkdir()

    with IpcProbeServer(tmp_path / "s.sqlite") as server:
        with IpcProbeClient(port=server.bound_port, token=server.token) as client:
            ok = client.request("submit_ingest", req_id=30, folder=str(folder), resume=True)
            assert ok["ok"] is True
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                client.drain(timeout=0.05)
                if client.done:
                    break
                time.sleep(0.02)
            assert saw.get("resume") is True
            assert client.done[-1]["result"]["status"] == "completed"

            assert server._dispatch_line("not-json")["ok"] is False  # noqa: SLF001


def test_cli_registers_ipc_probe():
    import inspect

    import semblon.cli as cli

    src = inspect.getsource(cli.main)
    assert "ipc-probe" in src
    assert "IpcProbeServer" in src
