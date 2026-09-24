"""Language-neutral application façade.

A future native UI talks to these names, not to Home widgets or FaceKit.
Mutations stay in review.py via review_ui.apply_*. Reads are RO SQLite.
Job ownership lives in semblon.jobs. Home and Review are clients only —
they must not own the ingest worker (CLI `process`/`ingest` remain
headless doors; Tk surfaces and the native shell submit through JobEngine
via this façade or an equivalent JobEngine handle).
"""

from __future__ import annotations

from pathlib import Path

from semblon.canvas import load_canvas
from semblon.home_ui import home_control_states, read_activity_snapshot
from semblon.inbox import inbox
from semblon.jobs import (
    KIND_INGEST,
    STATE_CANCELLING,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RUNNING,
    JobBusy,
    JobEngine,
    JobHandle,
    JobResult,
    OnDone,
    OnEvent,
)
from semblon.process import default_store_path, latest_run_id
from semblon.review_ui import (
    apply_ignore,
    apply_merge,
    apply_name,
    apply_note,
    apply_rule_out,
    apply_split,
    load_board,
    resolve_run_id,
)
from semblon.search import search_people, search_person

__all__ = [
    "KIND_INGEST",
    "STATE_CANCELLING",
    "STATE_IDLE",
    "STATE_PAUSED",
    "STATE_RUNNING",
    "Application",
    "JobBusy",
    "JobEngine",
    "JobHandle",
    "JobResult",
    "activity",
    "apply_ignore",
    "apply_merge",
    "apply_name",
    "apply_note",
    "apply_rule_out",
    "apply_split",
    "board",
    "chrome_board",
    "default_store_path",
    "home_control_states",
    "inbox",
    "latest_run_id",
    "load_board",
    "load_canvas",
    "resolve_run_id",
    "review_document",
    "search_people",
    "search_person",
]


def board(store: Path, run_id: str | None = None) -> dict:
    """Read-only review board. Does not enrol anyone."""
    rid = resolve_run_id(store, run_id)
    return load_board(store, rid)


def chrome_board(store: Path, run_id: str | None = None, *, mode: str = "live") -> dict:
    """Shared Cluster Review DTO (export snapshot + Home / review-ui live)."""
    from semblon.review_chrome import build_chrome_board

    rid = resolve_run_id(store, run_id)
    return build_chrome_board(store, rid, mode=mode)


def review_document(store: Path, run_id: str | None = None, *, mode: str = "live") -> str:
    """Render the shared Cluster Review HTML document."""
    from semblon.review_chrome import render_review_document_from_store

    rid = resolve_run_id(store, run_id)
    return render_review_document_from_store(store, rid, mode=mode)


def activity(store: Path, run_id: str | None = None) -> dict:
    """Read-only groups / relationships / events snapshot. Track ≠ person."""
    rid = resolve_run_id(store, run_id)
    return read_activity_snapshot(store, rid)


class Application:
    """One store + one JobEngine. Named commands match docs/APPLICATION_API.md.

    Progress KIND_QUEUED is a ProgressEvent, not JobEngine.state. Engine state is
    idle | running | paused | cancelling. Terminal outcomes are JobResult.status.
    """

    def __init__(self, store: Path | None = None):
        self.store = Path(store) if store is not None else default_store_path()
        self.engine = JobEngine(self.store)

    def job_current(self) -> JobHandle | None:
        return self.engine.current()

    @property
    def busy(self) -> bool:
        return self.engine.busy

    @property
    def paused(self) -> bool:
        return self.engine.paused

    @property
    def state(self) -> str:
        return self.engine.state

    def submit_ingest(
        self,
        folder: Path,
        *,
        resume: bool = False,
        on_event: OnEvent | None = None,
        on_done: OnDone | None = None,
        observers: str | None = None,
        prefer_gpu: bool | None = None,
        open_review: bool = False,
    ) -> JobHandle:
        return self.engine.submit_ingest(
            folder,
            resume=resume,
            on_event=on_event,
            on_done=on_done,
            observers=observers,
            prefer_gpu=prefer_gpu,
            open_review=open_review,
        )

    def pause_job(self) -> None:
        """Cooperative pause at the next file/stage gate. Same job stays claimed."""
        self.engine.pause()

    def unpause_job(self) -> None:
        """Continue the same in-flight job. Not resume-after-cancel."""
        self.engine.unpause()

    def cancel_job(self) -> None:
        """Cooperative cancel (also unblocks a paused wait)."""
        self.engine.cancel()

    def control_states(self, *, resume_ready: bool = False) -> dict[str, str]:
        return home_control_states(
            job_running=self.busy,
            resume_ready=resume_ready,
            job_paused=self.paused,
        )

    def board(self, run_id: str | None = None) -> dict:
        return board(self.store, run_id)

    def chrome_board(self, run_id: str | None = None, *, mode: str = "live") -> dict:
        return chrome_board(self.store, run_id, mode=mode)

    def review_document(self, run_id: str | None = None, *, mode: str = "live") -> str:
        return review_document(self.store, run_id, mode=mode)

    def activity(self, run_id: str | None = None) -> dict:
        return activity(self.store, run_id)

    def people(self) -> dict:
        return search_people(self.store)

    def inbox(self, run_id: str | None = None) -> dict:
        rid = resolve_run_id(self.store, run_id)
        return inbox(self.store, rid)

    def canvas(self, run_id: str | None = None) -> dict:
        rid = resolve_run_id(self.store, run_id)
        return load_canvas(self.store, rid)
