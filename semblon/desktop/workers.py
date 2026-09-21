"""Background import. The UI thread must not run ingest/cluster."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from semblon.desktop.copy import friendly_exception, process_event_snapshot
from semblon.home_ui import HOME_OBSERVERS
from semblon.jobs import JobBusy, JobEngine
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
