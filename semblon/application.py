"""UI-independent application façade.

PySide6 (`semblon shell`) is the forward shell. Legacy Tk Home is a client.
This module does not import a UI toolkit or a UI package.

The façade owns the JobEngine and the archive session. UIs submit and
observe. Visual commands take a media id and, where needed, a pixel rect.
The engine loads the file. Live image arrays are not the command interface.
"""

from __future__ import annotations

from pathlib import Path

from semblon.activity_surface import load_activity_memory, read_activity_snapshot
from semblon.archive_session import ArchiveSession, MediaRef
from semblon.canvas_data import load_canvas
from semblon.inbox import inbox
from semblon.job_controls import home_control_states
from semblon.jobs import (
    KIND_INGEST,
    KIND_VISUAL,
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
from semblon.review_board import (
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
    "KIND_VISUAL",
    "STATE_CANCELLING",
    "STATE_IDLE",
    "STATE_PAUSED",
    "STATE_RUNNING",
    "Application",
    "ArchiveSession",
    "JobBusy",
    "JobEngine",
    "JobHandle",
    "JobResult",
    "MediaRef",
    "activity",
    "activity_memory",
    "apply_ignore",
    "apply_merge",
    "apply_name",
    "apply_note",
    "apply_rule_out",
    "apply_split",
    "board",
    "default_store_path",
    "home_control_states",
    "inbox",
    "latest_run_id",
    "load_board",
    "load_canvas",
    "resolve_run_id",
    "search_people",
    "search_person",
]


def board(store: Path, run_id: str | None = None) -> dict:
    rid = resolve_run_id(store, run_id)
    return load_board(store, rid)


def activity(store: Path, run_id: str | None = None) -> dict:
    rid = resolve_run_id(store, run_id)
    return read_activity_snapshot(store, rid)


def activity_memory(store: Path, run_id: str | None = None) -> dict:
    return load_activity_memory(store, run_id)


class Application:
    """One process boundary. Shells do not open the store themselves."""

    def __init__(self, store: Path | None = None):
        self.store = Path(store) if store is not None else default_store_path()
        self.engine = JobEngine(self.store)
        self.archive = ArchiveSession(self.store, jobs=self)

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
        reprocess: bool = False,
    ) -> JobHandle:
        return self.engine.submit_ingest(
            folder,
            resume=resume,
            on_event=on_event,
            on_done=on_done,
            observers=observers,
            prefer_gpu=prefer_gpu,
            open_review=open_review,
            reprocess=reprocess,
        )

    def submit_visual(self, media_id: str, *, run_id: str, **kwargs):
        """Background visual understanding. The engine decodes the stored file."""
        return self.engine.submit_visual(media_id=media_id, run_id=run_id, **kwargs)

    def submit_visual_analyze(
        self,
        media_id: str,
        *,
        existing_faces: list | None = None,
        observation_id: str | None = None,
        force: bool = False,
        on_progress=None,
        on_done=None,
    ):
        """Background open-vocabulary analysis. The engine decodes the stored file."""
        return self.engine.submit_visual_analyze(
            media_id=media_id,
            existing_faces=existing_faces,
            observation_id=observation_id,
            force=force,
            on_progress=on_progress,
            on_done=on_done,
        )

    def query_media(
        self,
        media_id: str,
        rect: dict | None = None,
        *,
        capabilities: tuple[str, ...] | None = None,
    ) -> dict:
        """Whole-frame or region query on a media item. Loads pixels inside the query layer."""
        from semblon.visual_query import VisualQuery

        return self.query_visual(
            VisualQuery(
                source="media",
                media_id=str(media_id or ""),
                rect=dict(rect or {}),
                capabilities=capabilities,
            )
        )

    def query_screen(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        capabilities: tuple[str, ...] | None = None,
        limit: int = 10,
        selection_kind: str | None = None,
        cancelled=None,
    ) -> dict:
        """Screen-selection query through the same visual-query door, plus local retrieval."""
        from semblon.visual_query import VisualQuery

        return self.query_visual(
            VisualQuery(
                source="screen",
                screen_rect={"x": int(x), "y": int(y), "w": int(w), "h": int(h)},
                capabilities=capabilities,
                limit=max(1, int(limit)),
                selection_kind=selection_kind,
            ),
            cancelled=cancelled,
        )

    def query_visual(self, query, *, cancelled=None) -> dict:
        """Canonical visual-query dispatcher for media and screen sources."""
        from semblon.visual_query import run_visual_query

        return run_visual_query(self.store, query, cancelled=cancelled).as_dict()

    def pause_job(self) -> None:
        self.engine.pause()

    def unpause_job(self) -> None:
        self.engine.unpause()

    def cancel_job(self) -> None:
        self.engine.cancel()

    def shutdown(self, timeout: float = 30.0) -> None:
        self.engine.shutdown(timeout=timeout)

    def erase_person(self, person_id: str) -> dict:
        from semblon.erasure import delete_person

        return delete_person(self.store, person_id)

    def wipe_library(self) -> dict:
        from semblon.erasure import wipe_library

        return wipe_library(self.store)

    def control_states(self, *, resume_ready: bool = False) -> dict[str, str]:
        return home_control_states(
            job_running=self.busy,
            resume_ready=resume_ready,
            job_paused=self.paused,
        )

    def board(self, run_id: str | None = None) -> dict:
        return board(self.store, run_id)

    def activity(self, run_id: str | None = None) -> dict:
        return activity(self.store, run_id)

    def activity_memory(self, run_id: str | None = None) -> dict:
        return activity_memory(self.store, run_id)

    def people(self) -> dict:
        return search_people(self.store)

    def inbox(self, run_id: str | None = None) -> dict:
        rid = resolve_run_id(self.store, run_id)
        return inbox(self.store, rid)

    def canvas(self, run_id: str | None = None) -> dict:
        rid = resolve_run_id(self.store, run_id)
        return load_canvas(self.store, rid)

    def media(self, media_id: str) -> MediaRef | None:
        """Canonical media lookup. Shells do not query the media table themselves."""
        return self.archive.media(media_id)

    def media_path(self, media_id: str) -> str | None:
        item = self.media(media_id)
        if item is None or not item.path:
            return None
        return item.path

    def archive_count(self) -> int:
        return self.archive.count()

    def archive_window(self, offset: int, limit: int) -> list[MediaRef]:
        return self.archive.window(offset, limit)

    def remember_region(
        self,
        media_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        run_id: str | None = None,
        report=None,
    ) -> dict:
        from semblon.user_region import persist_user_region

        return persist_user_region(
            self.store,
            media_id=media_id,
            x=x,
            y=y,
            w=w,
            h=h,
            run_id=run_id,
            report=report,
        )

    def regions(self, run_id: str | None = None) -> list[dict]:
        from semblon.user_region import list_user_regions

        return list_user_regions(self.store, run_id=run_id)

    def name_region(self, item_id: str, name: str) -> dict:
        from semblon.user_region import name_user_region

        return name_user_region(self.store, item_id, name)

    def name_selection(
        self,
        media_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        image_path: Path | None = None,
    ) -> dict:
        from semblon.region_search import name_selection

        return name_selection(
            self.store,
            media_id=media_id,
            image_path=image_path,
            x=x,
            y=y,
            w=w,
            h=h,
        )

    def remember_and_find_region(
        self,
        media_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        image_path: Path | None = None,
        run_id: str | None = None,
        limit: int = 10,
        selection_kind: str | None = None,
        search_quality: str = "balanced",
        cancelled=None,
        on_first=None,
        query_spec=None,
    ) -> dict:
        from semblon.region_search import remember_and_find

        return remember_and_find(
            self.store,
            media_id=media_id,
            image_path=image_path,
            x=x,
            y=y,
            w=w,
            h=h,
            run_id=run_id,
            limit=limit,
            selection_kind=selection_kind,
            search_quality=search_quality,
            cancelled=cancelled,
            on_first=on_first,
            query_spec=query_spec,
        )

    def preview_region_parts(
        self,
        media_id: str,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        image_path: Path | None = None,
    ) -> dict:
        """Parts inside the highlight. Whole area plus up to three labels."""
        from semblon.query_spec import empty_parts
        from semblon.region_parts import propose_parts
        from semblon.region_search import crop_bgr

        crop = None
        path = Path(image_path) if image_path is not None else None
        if path is None or not path.is_file():
            item = self.media(media_id)
            path = Path(item.path) if item is not None and item.path else None
        if path is not None and path.is_file():
            try:
                crop = crop_bgr(path, x, y, w, h)
            except Exception:
                crop = None
        parts = propose_parts(self.store, media_id=media_id, x=x, y=y, w=w, h=h, crop=crop)
        return {"parts": parts or empty_parts(), "count": max(0, len(parts) - 1)}

