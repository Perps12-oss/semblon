"""R2 IPC probe — loopback JSON-lines over JobEngine.

Architecture boundary proof only (SEM-ARCH-V1.4 D.1):

    external client  <->  TCP 127.0.0.1  <->  Application  <->  JobEngine  <->  process_folder

Not the product IPC stack. Not named pipes. Not WinUI. Does not import Tk.
Does not write faces.person_id. Does not touch identity compare.

Wire protocol (one JSON object per line, UTF-8):

Request:  {"id": <any>, "op": "<name>", ...params}
Reply:    {"id": <same>, "ok": true|false, ...}
Push:     {"type": "progress", "event": {...}}   (no id; may arrive anytime)
Push:     {"type": "done", "result": {...}}      (terminal JobResult)

Ops: ping, status, submit_ingest, cancel, pause, unpause, result, shutdown.
`unpause` is in-flight resume. After cancel, use submit_ingest with resume=true.
"""

from __future__ import annotations

import json
import secrets
import socket
import threading
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from semblon.application import Application
from semblon.jobs import JobBusy, JobHandle, JobResult
from semblon.progress import ProgressEvent

DEFAULT_HOST = "127.0.0.1"
PROTOCOL = "semblon-ipc-probe/1"


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseException):
        return {"type": type(value).__name__, "message": str(value)}
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _handle_payload(handle: JobHandle | None) -> dict | None:
    if handle is None:
        return None
    return {
        "kind": handle.kind,
        "folder": str(handle.folder),
        "resume": handle.resume,
        "store": str(handle.store),
    }


def _result_payload(result: JobResult | None) -> dict | None:
    if result is None:
        return None
    return {
        "status": result.status,
        "run_id": result.run_id,
        "rec": _jsonable(result.rec),
        "error": _jsonable(result.error),
    }


class IpcProbeServer:
    """Loopback probe in front of Application. Not a second job owner."""

    def __init__(self, store: Path, *, host: str = DEFAULT_HOST, port: int = 0):
        self.store = Path(store)
        self.host = host
        self.port = int(port)
        self.app = Application(self.store)
        self.engine = self.app.engine
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._clients_lock = threading.Lock()
        self._clients: list[socket.socket] = []
        self._last_result: JobResult | None = None
        self._result_lock = threading.Lock()
        self._bound_port: int | None = None
        self.token = secrets.token_hex(16)

    @property
    def bound_port(self) -> int | None:
        return self._bound_port

    def start(self) -> int:
        if self._sock is not None:
            raise RuntimeError("ipc probe already started")
        if self.host not in ("127.0.0.1", "::1", "localhost"):
            raise ValueError("ipc probe binds loopback only")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host if self.host != "localhost" else "127.0.0.1", self.port))
        sock.listen(8)
        sock.settimeout(0.5)
        self._sock = sock
        self._bound_port = int(sock.getsockname()[1])
        self._stop.clear()
        self._thread = threading.Thread(target=self._accept_loop, name="semblon-ipc-probe", daemon=True)
        self._thread.start()
        return self._bound_port

    def stop(self) -> None:
        self._stop.set()
        try:
            self.app.cancel_job()
        except Exception:  # noqa: BLE001 — best-effort on shutdown
            pass
        deadline = time.monotonic() + 2.0
        while self.app.busy and time.monotonic() < deadline:
            time.sleep(0.02)
        with self._clients_lock:
            clients = list(self._clients)
            self._clients.clear()
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                client.close()
            except OSError:
                pass
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def wait_stopped(self, timeout: float) -> bool:
        """True when stop was requested (shutdown op or stop())."""
        return self._stop.wait(timeout)

    def __enter__(self) -> "IpcProbeServer":
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                client, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._clients_lock:
                self._clients.append(client)
            threading.Thread(
                target=self._serve_client,
                args=(client,),
                name="semblon-ipc-client",
                daemon=True,
            ).start()

    def _broadcast(self, payload: dict) -> None:
        line = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        with self._clients_lock:
            clients = list(self._clients)
        dead: list[socket.socket] = []
        for client in clients:
            try:
                client.sendall(line)
            except OSError:
                dead.append(client)
        if dead:
            with self._clients_lock:
                for client in dead:
                    if client in self._clients:
                        self._clients.remove(client)
                    try:
                        client.close()
                    except OSError:
                        pass

    def _on_event(self, event: ProgressEvent) -> None:
        self._broadcast({"type": "progress", "event": _jsonable(event)})

    def _on_done(self, result: JobResult) -> None:
        with self._result_lock:
            self._last_result = result
        self._broadcast({"type": "done", "result": _result_payload(result)})

    def _serve_client(self, client: socket.socket) -> None:
        buf = b""
        max_line = 1 << 20
        try:
            client.settimeout(1.0)
            while not self._stop.is_set():
                try:
                    chunk = client.recv(4096)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                if len(buf) > max_line:
                    try:
                        client.close()
                    except OSError:
                        pass
                    return
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    reply = self._dispatch_line(line)
                    try:
                        client.sendall((json.dumps(reply, separators=(",", ":")) + "\n").encode("utf-8"))
                    except OSError:
                        return
                    if reply.get("shutdown"):
                        self._stop.set()
                        return
        finally:
            with self._clients_lock:
                if client in self._clients:
                    self._clients.remove(client)
            try:
                client.close()
            except OSError:
                pass

    def _dispatch_line(self, line: str) -> dict:
        req_id: Any = None
        try:
            msg = json.loads(line)
            if not isinstance(msg, dict):
                return {"id": None, "ok": False, "error": {"type": "ProtocolError", "message": "request must be object"}}
            req_id = msg.get("id")
            if not secrets.compare_digest(str(msg.get("token") or ""), self.token):
                return {
                    "id": req_id,
                    "ok": False,
                    "error": {"type": "AuthError", "message": "ipc probe token required"},
                }
            op = msg.get("op")
            if not isinstance(op, str) or not op:
                return {"id": req_id, "ok": False, "error": {"type": "ProtocolError", "message": "op required"}}
            return self._handle_op(req_id, op, msg)
        except json.JSONDecodeError as e:
            return {"id": req_id, "ok": False, "error": {"type": "JSONDecodeError", "message": str(e)}}
        except Exception as e:  # noqa: BLE001 — surface to external client
            return {"id": req_id, "ok": False, "error": _jsonable(e)}

    def _handle_op(self, req_id: Any, op: str, msg: dict) -> dict:
        if op == "ping":
            return {"id": req_id, "ok": True, "protocol": PROTOCOL}
        if op == "status":
            return {
                "id": req_id,
                "ok": True,
                "state": self.app.state,
                "busy": self.app.busy,
                "paused": self.app.paused,
                "current": _handle_payload(self.app.job_current()),
                "store": str(self.store),
            }
        if op == "submit_ingest":
            folder = msg.get("folder")
            if not isinstance(folder, str) or not folder.strip():
                return {
                    "id": req_id,
                    "ok": False,
                    "error": {"type": "ProtocolError", "message": "folder required"},
                }
            resume = bool(msg.get("resume", False))
            try:
                handle = self.app.submit_ingest(
                    Path(folder),
                    resume=resume,
                    on_event=self._on_event,
                    on_done=self._on_done,
                )
            except JobBusy as e:
                return {"id": req_id, "ok": False, "error": _jsonable(e)}
            return {"id": req_id, "ok": True, "handle": _handle_payload(handle)}
        if op == "cancel":
            self.app.cancel_job()
            return {"id": req_id, "ok": True, "state": self.app.state}
        if op == "pause":
            self.app.pause_job()
            return {"id": req_id, "ok": True, "state": self.app.state, "paused": self.app.paused}
        if op == "unpause":
            self.app.unpause_job()
            return {"id": req_id, "ok": True, "state": self.app.state, "paused": self.app.paused}
        if op == "result":
            with self._result_lock:
                result = self._last_result
            return {"id": req_id, "ok": True, "result": _result_payload(result)}
        if op == "shutdown":
            return {"id": req_id, "ok": True, "shutdown": True}
        return {
            "id": req_id,
            "ok": False,
            "error": {"type": "ProtocolError", "message": f"unknown op: {op}"},
        }


class IpcProbeClient:
    """Minimal external client for the probe. No Tk."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = 0, token: str | None = None):
        self.host = host
        self.port = int(port)
        self.token = token or ""
        self._sock: socket.socket | None = None
        self._buf = b""
        self._lock = threading.Lock()
        self.progress: list[dict] = []
        self.done: list[dict] = []

    def connect(self, *, timeout: float = 2.0) -> None:
        sock = socket.create_connection((self.host, self.port), timeout=timeout)
        sock.settimeout(1.0)
        self._sock = sock
        self._buf = b""

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def __enter__(self) -> "IpcProbeClient":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def request(self, op: str, *, req_id: Any = 1, timeout: float = 5.0, **params: Any) -> dict:
        if self._sock is None:
            raise RuntimeError("not connected")
        payload = {"id": req_id, "op": op, "token": self.token, **params}
        line = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            self._sock.sendall(line)
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                msg = self._read_message(deadline=end)
                if msg is None:
                    continue
                if msg.get("type") == "progress":
                    self.progress.append(msg)
                    continue
                if msg.get("type") == "done":
                    self.done.append(msg)
                    continue
                if msg.get("id") == req_id:
                    return msg
            raise TimeoutError(f"no reply for op={op!r} id={req_id!r}")

    def drain(self, *, timeout: float = 0.2) -> None:
        """Pull any pending push messages without sending a request."""
        if self._sock is None:
            return
        end = time.monotonic() + timeout
        with self._lock:
            while time.monotonic() < end:
                msg = self._read_message(deadline=end)
                if msg is None:
                    break
                if msg.get("type") == "progress":
                    self.progress.append(msg)
                elif msg.get("type") == "done":
                    self.done.append(msg)

    def _read_message(self, *, deadline: float) -> dict | None:
        assert self._sock is not None
        while b"\n" not in self._buf:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            self._sock.settimeout(max(0.05, min(1.0, remaining)))
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout:
                return None
            except OSError:
                return None
            if not chunk:
                return None
            self._buf += chunk
        raw, self._buf = self._buf.split(b"\n", 1)
        line = raw.decode("utf-8", errors="replace").strip()
        if not line:
            return None
        return json.loads(line)

