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
    "KIND_VISUAL",
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
    "activity_memory",
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
    rid = resolve_run_id(store, run_id)
    return load_board(store, rid)


def chrome_board(store: Path, run_id: str | None = None, *, mode: str = "live") -> dict:
    from semblon.review_chrome import build_chrome_board

    rid = resolve_run_id(store, run_id)
    return build_chrome_board(store, rid, mode=mode)


def review_document(store: Path, run_id: str | None = None, *, mode: str = "live") -> str:
    from semblon.review_chrome import render_review_document_from_store

    rid = resolve_run_id(store, run_id)
    return render_review_document_from_store(store, rid, mode=mode)


def activity(store: Path, run_id: str | None = None) -> dict:
    rid = resolve_run_id(store, run_id)
    return read_activity_snapshot(store, rid)


def activity_memory(store: Path, run_id: str | None = None) -> dict:
    from semblon.activity_surface import load_activity_memory

    return load_activity_memory(store, run_id)


def _install_lens_home() -> None:
    """Home mouse-up persists the user box and finds similar photos."""
    from semblon.home_ui import HomeApp
    from semblon.lens_home import install

    install(HomeApp)


class Application:
    def __init__(self, store: Path | None = None):
        self.store = Path(store) if store is not None else default_store_path()
        self.engine = JobEngine(self.store)
        _install_lens_home()

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

    def analyse_visual(
        self,
        media_id: str,
        image,
        *,
        run_id: str,
        nouns: list[str] | None = None,
        score_fn=None,
        view_w: int | None = None,
        view_h: int | None = None,
        color: str = "rgb",
    ) -> dict:
        """Synchronous visual understanding. Does not enrol a person."""
        import numpy as np

        from semblon.visual.engine import analyse
        from semblon.visual.persist import load_scene_inputs, persist_analysis

        frame = np.asarray(image)
        rgb = np.ascontiguousarray(frame[:, :, :3][:, :, ::-1]) if color == "bgr" else frame
        height, width = int(rgb.shape[0]), int(rgb.shape[1])
        scene = load_scene_inputs(self.store, media_id=media_id, run_id=run_id, height=height, width=width)
        analysis = analyse(
            rgb,
            nouns=nouns,
            score_fn=score_fn,
            view_w=view_w,
            view_h=view_h,
            user_regions=scene["user_regions"],
            face_boxes=scene["face_boxes"],
            revision=f"visual-{run_id}",
        )
        rec = persist_analysis(self.store, analysis, media_id=media_id, run_id=run_id)
        rec["level"] = analysis.level
        rec["regions"] = len(analysis.regions)
        rec["named"] = sum(1 for region in analysis.regions if region.label)
        rec["persons_touched"] = False
        return rec

    def submit_visual(self, media_id: str, image, *, run_id: str, **kwargs):
        return self.engine.submit_visual(media_id=media_id, image=image, run_id=run_id, **kwargs)

    def visual_capabilities(self) -> dict:
        from semblon.visual.engine import capabilities

        return capabilities()

    def pause_job(self) -> None:
        self.engine.pause()

    def unpause_job(self) -> None:
        self.engine.unpause()

    def cancel_job(self) -> None:
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
        )
