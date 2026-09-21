"""Application job boundary.

UI  →  JobEngine  →  process_folder / review.py

One ingest job at a time. A second submit is JobBusy — not an application lock.
Review mutations stay on review.py and wait on the existing writer.
Does not write faces.person_id. Does not touch identity compare.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from semblon.progress import ProgressEvent

KIND_INGEST = "ingest"

OnEvent = Callable[[ProgressEvent], None]
OnDone = Callable[["JobResult"], None]


class JobBusy(RuntimeError):
    """A job is already running. Second submit is refused."""


@dataclass(frozen=True)
class JobHandle:
    kind: str
    folder: Path
    resume: bool
    store: Path


@dataclass(frozen=True)
class JobResult:
    status: str
    rec: dict | None = None
    run_id: str | None = None
    error: BaseException | None = None


class JobEngine:
    """Single door for ingest. UIs submit; they do not own the worker."""

    def __init__(self, store: Path):
        self.store = Path(store)
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._current: JobHandle | None = None

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._current is not None

    def current(self) -> JobHandle | None:
        with self._lock:
            return self._current

    def cancel(self) -> None:
        self._cancel.set()

    def submit_ingest(
        self,
        folder: Path,
        *,
        resume: bool = False,
        on_event: OnEvent | None = None,
        on_done: OnDone | None = None,
        observers: str | None = None,
        open_review: bool = False,
    ) -> JobHandle:
        """Start process_folder on a worker thread. Raises JobBusy if running."""
        handle = self._claim(folder, resume=resume)
        thread = threading.Thread(
            target=self._run_submitted,
            args=(handle, on_event, on_done, observers, open_review),
            daemon=True,
            name="semblon-job-ingest",
        )
        with self._lock:
            self._thread = thread
        thread.start()
        return handle

    def run_ingest(
        self,
        folder: Path,
        *,
        resume: bool = False,
        on_event: OnEvent | None = None,
        observers: str | None = None,
        open_review: bool = False,
    ) -> dict:
        """Run process_folder on this thread. Raises JobBusy if running."""
        handle = self._claim(folder, resume=resume)
        try:
            return self._invoke_process(handle, on_event, observers, open_review)
        finally:
            self._release(handle)

    def _claim(self, folder: Path, *, resume: bool) -> JobHandle:
        handle = JobHandle(
            kind=KIND_INGEST,
            folder=Path(folder),
            resume=resume,
            store=self.store,
        )
        with self._lock:
            if self._current is not None:
                raise JobBusy("ingest already running")
            self._cancel.clear()
            self._current = handle
        return handle

    def _release(self, handle: JobHandle) -> None:
        with self._lock:
            if self._current is handle:
                self._current = None
                self._thread = None

    def _invoke_process(
        self,
        handle: JobHandle,
        on_event: OnEvent | None,
        observers: str | None,
        open_review: bool,
    ) -> dict:
        from semblon.process import process_folder

        kwargs: dict = {
            "store": self.store,
            "open_review": open_review,
            "progress": lambda *_: None,
            "on_event": on_event,
            "cancel": self._cancel.is_set,
            "resume": handle.resume,
        }
        if observers is not None:
            kwargs["observers"] = observers
        return process_folder(handle.folder, **kwargs)

    def _run_submitted(
        self,
        handle: JobHandle,
        on_event: OnEvent | None,
        on_done: OnDone | None,
        observers: str | None,
        open_review: bool,
    ) -> None:
        from semblon.process import ProcessCancelled

        result = JobResult(status="failed")
        try:
            rec = self._invoke_process(handle, on_event, observers, open_review)
            result = JobResult(status="completed", rec=rec, run_id=rec.get("run_id"))
        except ProcessCancelled as e:
            result = JobResult(status="cancelled", run_id=e.run_id, error=e)
        except Exception as e:  # noqa: BLE001 — surface to the submitting UI
            result = JobResult(status="failed", error=e)
        finally:
            self._release(handle)
            if on_done is not None:
                on_done(result)
