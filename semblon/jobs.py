"""Application Job boundary. UI-agnostic. No Tk, Qt, FaceKit, or SQLite handles.

A client submits a job and observes snapshots. The existing process_folder
implementation stays underneath. One ingest job at a time — a second submit
is JobBusy, not a fake thread pool.

JSON-shaped snapshots are the R2 IPC payload. Do not put widgets on them.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from semblon.process import ProcessCancelled, process_folder
from semblon.progress import (
    KIND_CANCELLED,
    KIND_COMPLETED,
    KIND_FAILED,
    KIND_PARTIAL,
    KIND_PROGRESS,
    KIND_QUEUED,
    KIND_STALLED,
    KIND_STARTED,
    ProgressEvent,
)

# Language-neutral job states. PAUSED is reserved; not implemented.
STATE_QUEUED = "queued"
STATE_STARTING = "starting"
STATE_RUNNING = "running"
STATE_CANCELLING = "cancelling"
STATE_CANCELLED = "cancelled"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"

JOB_TYPE_INGEST = "ingest"

_ACTIVE = frozenset({STATE_QUEUED, STATE_STARTING, STATE_RUNNING, STATE_CANCELLING})
_KIND_STATE = {
    KIND_QUEUED: STATE_QUEUED,
    KIND_STARTED: STATE_STARTING,
    KIND_PROGRESS: STATE_RUNNING,
    KIND_PARTIAL: STATE_RUNNING,
    KIND_STALLED: STATE_RUNNING,
    KIND_CANCELLED: STATE_CANCELLED,
    KIND_COMPLETED: STATE_COMPLETED,
    KIND_FAILED: STATE_FAILED,
}


class JobBusy(RuntimeError):
    """A job is already running. Semblon does not queue a second ingest."""


class JobError(ValueError):
    pass


@dataclass
class JobSnapshot:
    """JSON-safe job view. Missing metrics stay None — never invent them."""

    job_id: str
    type: str
    state: str
    source: str | None = None
    store: str | None = None
    run_id: str | None = None
    resume: bool = False
    files_total: int | None = None
    files_processed: int | None = None
    faces: int | None = None
    skipped: int | None = None
    failed: int | None = None
    elapsed_s: float | None = None
    rate: float | None = None
    eta_s: float | None = None
    current_stage: str | None = None
    kind: str | None = None
    error: str | None = None
    stalled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    def active(self) -> bool:
        return self.state in _ACTIVE


READ_SURFACES = (
    "review",
    "html",
    "people",
    "unknown",
    "activity",
    "settings",
    "canvas",
    "search",
)


def home_control_states(*, job_active: bool, resume_ready: bool) -> dict[str, str]:
    """Which Home buttons are enabled. Read surfaces stay on during a job."""
    states = {name: "normal" for name in READ_SURFACES}
    states["folder"] = "disabled" if job_active else "normal"
    states["resume"] = "disabled" if job_active or not resume_ready else "normal"
    states["cancel"] = "normal" if job_active else "disabled"
    return states


def snapshot_from_event(job: JobSnapshot, ev: ProgressEvent) -> JobSnapshot:
    """Fold a ProgressEvent into a snapshot. Does not invent counts."""
    state = _KIND_STATE.get(ev.kind, job.state)
    if job.state == STATE_CANCELLING and state in {STATE_QUEUED, STATE_STARTING, STATE_RUNNING}:
        state = STATE_CANCELLING
    skipped = job.skipped
    rate = None
    if ev.elapsed_s and ev.elapsed_s > 0 and ev.files_processed:
        rate = round(float(ev.files_processed) / float(ev.elapsed_s), 4)
    return JobSnapshot(
        job_id=job.job_id,
        type=job.type,
        state=state,
        source=ev.path or job.source,
        store=job.store,
        run_id=ev.run_id or job.run_id,
        resume=job.resume,
        files_total=ev.files_total if ev.files_total is not None else job.files_total,
        files_processed=ev.files_processed if ev.files_processed is not None else job.files_processed,
        faces=ev.faces_found if ev.faces_found is not None else job.faces,
        skipped=skipped,
        failed=job.failed,
        elapsed_s=ev.elapsed_s if ev.elapsed_s is not None else job.elapsed_s,
        rate=rate,
        eta_s=ev.eta_s if ev.eta_s is not None else job.eta_s,
        current_stage=ev.stage or job.current_stage,
        kind=ev.kind,
        error=ev.error or job.error,
        stalled=ev.kind == KIND_STALLED,
    )


class JobEngine:
    """Owns at most one ingest worker. Clients subscribe to snapshots/events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self._snap = JobSnapshot(job_id="", type=JOB_TYPE_INGEST, state=STATE_COMPLETED)
        self._on_event: Callable[[ProgressEvent], None] | None = None

    def snapshot(self) -> JobSnapshot:
        with self._lock:
            return self._snap

    def active(self) -> bool:
        return self.snapshot().active()

    def request_cancel(self) -> None:
        with self._lock:
            if not self._snap.active():
                return
            self._snap = JobSnapshot(
                **{**self._snap.to_dict(), "state": STATE_CANCELLING, "kind": "cancelling"}
            )
        self._cancel.set()

    def submit_ingest(
        self,
        folder: Path,
        store: Path,
        *,
        resume: bool = False,
        observers: str = "face",
        on_event: Callable[[ProgressEvent], None] | None = None,
        on_done: Callable[[dict], None] | None = None,
        on_cancelled: Callable[[str | None], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
    ) -> JobSnapshot:
        folder = Path(folder)
        store = Path(store)
        with self._lock:
            if self._snap.active() or (self._thread is not None and self._thread.is_alive()):
                raise JobBusy("ingest already running")
            job_id = uuid.uuid4().hex[:12]
            self._cancel.clear()
            self._on_event = on_event
            self._snap = JobSnapshot(
                job_id=job_id,
                type=JOB_TYPE_INGEST,
                state=STATE_QUEUED,
                source=str(folder),
                store=str(store),
                resume=resume,
                current_stage="process",
                kind=KIND_QUEUED,
            )
            snap = self._snap
        self._thread = threading.Thread(
            target=self._run_ingest,
            args=(folder, store, resume, observers, on_done, on_cancelled, on_error),
            name=f"semblon-job-{snap.job_id}",
            daemon=True,
        )
        self._thread.start()
        return snap

    def _apply_event(self, ev: ProgressEvent) -> None:
        with self._lock:
            self._snap = snapshot_from_event(self._snap, ev)
        cb = self._on_event
        if cb is not None:
            try:
                cb(ev)
            except Exception:
                pass

    def _run_ingest(
        self,
        folder: Path,
        store: Path,
        resume: bool,
        observers: str,
        on_done,
        on_cancelled,
        on_error,
    ) -> None:
        t0 = time.perf_counter()
        try:
            rec = process_folder(
                folder,
                store=store,
                open_review=False,
                progress=lambda *_: None,
                on_event=self._apply_event,
                cancel=self._cancel.is_set,
                observers=observers,
                resume=resume,
            )
            with self._lock:
                self._snap = JobSnapshot(
                    **{
                        **self._snap.to_dict(),
                        "state": STATE_COMPLETED,
                        "kind": KIND_COMPLETED,
                        "run_id": rec.get("run_id") or self._snap.run_id,
                        "elapsed_s": round(time.perf_counter() - t0, 3),
                    }
                )
            if on_done is not None:
                on_done(rec)
        except ProcessCancelled as e:
            with self._lock:
                self._snap = JobSnapshot(
                    **{
                        **self._snap.to_dict(),
                        "state": STATE_CANCELLED,
                        "kind": KIND_CANCELLED,
                        "run_id": e.run_id or self._snap.run_id,
                        "elapsed_s": round(time.perf_counter() - t0, 3),
                    }
                )
            if on_cancelled is not None:
                on_cancelled(e.run_id)
        except Exception as e:
            with self._lock:
                self._snap = JobSnapshot(
                    **{
                        **self._snap.to_dict(),
                        "state": STATE_FAILED,
                        "kind": KIND_FAILED,
                        "error": f"{type(e).__name__}: {e}",
                        "elapsed_s": round(time.perf_counter() - t0, 3),
                    }
                )
            if on_error is not None:
                on_error(e)
