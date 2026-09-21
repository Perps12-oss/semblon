"""Background import and live capture. The UI thread must not run ingest/FaceKit."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from semblon.desktop.copy import friendly_exception, process_event_snapshot
from semblon.home_ui import HOME_OBSERVERS
from semblon.ingest import CancelledError
from semblon.jobs import JobBusy, JobEngine
from semblon.live import LiveError, live_capture
from semblon.process import ProcessCancelled, ProcessError
from semblon.progress import ProgressEvent
from semblon.watchdog import Watchdog


class ImportWorker(QObject):
    progressed = Signal(dict)
    succeeded = Signal(dict)
    cancelled = Signal(dict)
    failed = Signal(str, str)

    def __init__(self, folder: Path, store: Path, *, observers: str = HOME_OBSERVERS):
        super().__init__()
        self.folder = Path(folder)
        self.store = Path(store)
        self.observers = observers
        self._engine = JobEngine(self.store)
        self._wd = Watchdog(stall_s=120.0)

    def request_cancel(self) -> None:
        self._engine.cancel()

    def request_pause(self) -> None:
        self._engine.pause()

    def request_unpause(self) -> None:
        self._engine.unpause()

    def run(self) -> None:
        def on_event(ev: ProgressEvent) -> None:
            self._wd.note(ev)
            self.progressed.emit(process_event_snapshot(ev))
            stalled = self._wd.check()
            if stalled is not None:
                self.progressed.emit(process_event_snapshot(stalled))

        try:
            rec = self._engine.run_ingest(
                self.folder,
                on_event=on_event,
                observers=self.observers,
            )
            self.succeeded.emit(rec)
        except JobBusy as e:
            self.failed.emit("Job busy — ingest already running.", str(e))
        except ProcessCancelled as e:
            self.cancelled.emit(
                {
                    "run_id": e.run_id,
                    "headline": "Import cancelled",
                    "detail": "Partial results have been retained.",
                }
            )
        except ProcessError as e:
            user, detail = friendly_exception(e)
            self.failed.emit(user, detail)
        except Exception as e:  # noqa: BLE001 — surface unexpected failures in the shell
            user, detail = friendly_exception(e)
            self.failed.emit(user, detail)


class LiveWorker(QObject):
    """Runs live_capture off the UI thread. Overlay snapshots via ``framed``."""

    progressed = Signal(dict)
    framed = Signal(dict)
    succeeded = Signal(dict)
    cancelled = Signal(dict)
    failed = Signal(str, str)

    def __init__(
        self,
        store: Path,
        *,
        source: str = "0",
        seconds: float = 0.0,
        sample_hz: float = 2.0,
    ):
        super().__init__()
        self.store = Path(store)
        self.source = source
        self.seconds = float(seconds)
        self.sample_hz = float(sample_hz)
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        def on_event(ev: ProgressEvent) -> None:
            self.progressed.emit(process_event_snapshot(ev))

        def on_frame(snap: dict) -> None:
            payload = {
                "t_ms": snap.get("t_ms"),
                "frame_index": snap.get("frame_index"),
                "overlays": list(snap.get("overlays") or []),
                "counts": dict(snap.get("counts") or {}),
                "run_id": snap.get("run_id"),
            }
            preview = snap.get("preview_bgr")
            if preview is not None:
                payload["preview_bgr"] = preview
            self.framed.emit(payload)

        try:
            rec = live_capture(
                self.store,
                source=self.source,
                seconds=self.seconds,
                sample_hz=self.sample_hz,
                reembed_s=2.0,
                cancel=lambda: self._cancel,
                on_event=on_event,
                on_frame=on_frame,
                include_frame_preview=True,
            )
            self.succeeded.emit(rec)
        except CancelledError as e:
            self.cancelled.emit(
                {
                    "run_id": getattr(e, "run_id", None),
                    "headline": "Live stopped",
                    "detail": "Partial live observations retained.",
                }
            )
        except LiveError as e:
            self.failed.emit("Live could not start.", str(e))
        except Exception as e:  # noqa: BLE001
            user, detail = friendly_exception(e)
            self.failed.emit(user, detail)
