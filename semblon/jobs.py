"""Application job boundary.

UI  →  JobEngine  →  process_folder / review.py

One ingest job at a time. A second submit is JobBusy — not an application lock.
Review mutations stay on review.py and wait on the existing writer.
Does not write faces.person_id. Does not touch identity compare.

Pause is cooperative at the same boundaries as cancel (between files / stage
checks inside process_folder → ingest). Mid-file pause is not claimed.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from semblon.progress import ProgressEvent

KIND_INGEST = "ingest"
KIND_VISUAL = "visual"

STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_PAUSED = "paused"
STATE_CANCELLING = "cancelling"

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
    media_id: str | None = None


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
        self._pause = threading.Event()  # set => paused; clear => running
        self._thread: threading.Thread | None = None
        self._current: JobHandle | None = None
        self._cancelling = False

    @property
    def ingest_busy(self) -> bool:
        """True only for library ingest. Visual understanding must not flip Home to PROCESSING."""
        with self._lock:
            return self._current is not None and self._current.kind == KIND_INGEST

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._current is not None

    @property
    def paused(self) -> bool:
        with self._lock:
            return self._current is not None and self._pause.is_set() and not self._cancelling

    @property
    def state(self) -> str:
        with self._lock:
            if self._current is None:
                return STATE_IDLE
            if self._cancelling or self._cancel.is_set():
                return STATE_CANCELLING
            if self._pause.is_set():
                return STATE_PAUSED
            return STATE_RUNNING

    def current(self) -> JobHandle | None:
        with self._lock:
            return self._current

    def cancel(self) -> None:
        with self._lock:
            if self._current is None:
                return
            self._cancelling = True
        self._cancel.set()
        # Unblock a paused wait so cancel is observed at the next gate.
        self._pause.clear()

    def pause(self) -> None:
        """Request cooperative pause. Takes effect at the next file/stage gate."""
        with self._lock:
            if self._current is None or self._cancelling or self._cancel.is_set():
                return
            self._pause.set()

    def unpause(self) -> None:
        """Continue the same in-flight job after pause. Not resume-after-cancel."""
        with self._lock:
            if self._current is None:
                return
            self._pause.clear()

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
        """Start process_folder on a worker thread. Raises JobBusy if running."""
        handle = self._claim(folder, resume=resume)
        thread = threading.Thread(
            target=self._run_submitted,
            args=(handle, on_event, on_done, observers, prefer_gpu, open_review),
            daemon=True,
            name="semblon-job-ingest",
        )
        with self._lock:
            self._thread = thread
        thread.start()
        return handle

    def submit_visual(
        self,
        *,
        media_id: str,
        image,
        run_id: str,
        on_event: OnEvent | None = None,
        on_done: OnDone | None = None,
        nouns: list[str] | None = None,
        score_fn=None,
        config=None,
        color: str = "rgb",
        view_w: int | None = None,
        view_h: int | None = None,
    ) -> JobHandle:
        """Background visual analysis. Same single-job door as ingest. Not pointer-time."""
        handle = JobHandle(
            kind=KIND_VISUAL,
            folder=self.store,
            resume=False,
            store=self.store,
            media_id=media_id,
        )
        with self._lock:
            if self._current is not None:
                raise JobBusy("a job is already running")
            self._cancel.clear()
            self._pause.clear()
            self._cancelling = False
            self._current = handle
        thread = threading.Thread(
            target=self._run_visual,
            args=(handle, image, run_id, on_event, on_done, nouns, score_fn, config, color, view_w, view_h),
            daemon=True,
            name="semblon-job-visual",
        )
        with self._lock:
            self._thread = thread
        thread.start()
        return handle

    def _run_visual(
        self,
        handle: JobHandle,
        image,
        run_id: str,
        on_event,
        on_done,
        nouns,
        score_fn,
        config,
        color,
        view_w,
        view_h,
    ) -> None:
        import resource

        import numpy as np

        from semblon.progress import ProgressEvent
        from semblon.visual.discovery import sam2_capability
        from semblon.visual.engine import analyse
        from semblon.visual.persist import load_scene_inputs, persist_analysis

        result = JobResult(status="failed", run_id=run_id)
        try:
            if on_event:
                on_event(ProgressEvent(stage="visual", kind="started", message="understanding"))
            if self._gate():
                result = JobResult(status="cancelled", run_id=run_id)
            else:
                frame = np.asarray(image)
                rgb = (
                    np.ascontiguousarray(frame[:, :, :3][:, :, ::-1])
                    if color == "bgr"
                    else np.ascontiguousarray(frame[:, :, :3])
                )
                height, width = int(rgb.shape[0]), int(rgb.shape[1])
                scene = load_scene_inputs(
                    self.store, media_id=handle.media_id or "", run_id=run_id, height=height, width=width
                )
                cap = sam2_capability()
                two_pass = cap.get("state") == "READY"

                def _once(use_sam2):
                    return analyse(
                        rgb,
                        config=config,
                        nouns=nouns,
                        score_fn=score_fn,
                        view_w=view_w,
                        view_h=view_h,
                        user_regions=scene["user_regions"],
                        face_boxes=scene["face_boxes"],
                        revision=f"visual-{run_id}",
                        cancel=self._gate,
                        use_sam2=use_sam2,
                    )

                def _pack(analysis) -> dict:
                    rec = persist_analysis(
                        self.store,
                        analysis,
                        media_id=handle.media_id or "",
                        run_id=run_id,
                    )
                    rec["diagnostics"] = {
                        "stages": analysis.diagnostics.get("stages"),
                        "level": analysis.level,
                        "sam2": analysis.diagnostics.get("sam2"),
                        "naming": analysis.diagnostics.get("naming"),
                        "timings_ms": analysis.diagnostics.get("timings_ms"),
                    }
                    rec["rss_kb"] = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                    return rec

                first = _once(False if two_pass else None)
                if first.level == 0 and self._gate():
                    result = JobResult(status="cancelled", run_id=run_id)
                else:
                    rec = _pack(first)
                    result = JobResult(status="completed", rec=rec, run_id=run_id)
                    if two_pass and on_event:
                        on_event(ProgressEvent(stage="visual", kind="partial", message=f"L{first.level}"))
                    if two_pass and result.status == "completed" and not self._gate():
                        try:
                            second = _once(True)
                        except Exception as exc:  # noqa: BLE001 — coarse map stays
                            rec = dict(result.rec or {})
                            rec["sam2_error"] = f"{type(exc).__name__}: {exc}"
                            result = JobResult(status="completed", rec=rec, run_id=run_id)
                        else:
                            if second.level == 0 and self._gate():
                                result = JobResult(status="cancelled", rec=result.rec, run_id=run_id)
                            else:
                                result = JobResult(status="completed", rec=_pack(second), run_id=run_id)
                    if result.status == "completed" and on_event:
                        level = (result.rec or {}).get("level")
                        on_event(ProgressEvent(stage="visual", kind="completed", message=str(level)))
        except Exception as e:  # noqa: BLE001 — surface to the submitting UI
            result = JobResult(status="failed", error=e, run_id=run_id)
        finally:
            self._release(handle)
            if on_done is not None:
                on_done(result)

    def run_ingest(
        self,
        folder: Path,
        *,
        resume: bool = False,
        on_event: OnEvent | None = None,
        observers: str | None = None,
        prefer_gpu: bool | None = None,
        open_review: bool = False,
    ) -> dict:
        """Run process_folder on this thread. Raises JobBusy if running."""
        handle = self._claim(folder, resume=resume)
        try:
            return self._invoke_process(
                handle, on_event, observers, prefer_gpu, open_review
            )
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
            self._pause.clear()
            self._cancelling = False
            self._current = handle
        return handle

    def _release(self, handle: JobHandle) -> None:
        with self._lock:
            if self._current is handle:
                self._current = None
                self._thread = None
                self._cancelling = False
                self._pause.clear()
                self._cancel.clear()

    def _gate(self) -> bool:
        """True => stop (cancel). While paused, block here without processing.

        Granularity matches ingest/process cancel checks: between files and at
        stage boundaries — not mid-decode / mid-embed.
        """
        while self._pause.is_set() and not self._cancel.is_set():
            time.sleep(0.05)
        return self._cancel.is_set()

    def _invoke_process(
        self,
        handle: JobHandle,
        on_event: OnEvent | None,
        observers: str | None,
        prefer_gpu: bool | None,
        open_review: bool,
    ) -> dict:
        from semblon.process import process_folder

        kwargs: dict = {
            "store": self.store,
            "open_review": open_review,
            "progress": lambda *_: None,
            "on_event": on_event,
            "cancel": self._gate,
            "resume": handle.resume,
        }
        if observers is not None:
            kwargs["observers"] = observers
        if prefer_gpu is not None:
            kwargs["prefer_gpu"] = prefer_gpu
        return process_folder(handle.folder, **kwargs)

    def _run_submitted(
        self,
        handle: JobHandle,
        on_event: OnEvent | None,
        on_done: OnDone | None,
        observers: str | None,
        prefer_gpu: bool | None,
        open_review: bool,
    ) -> None:
        from semblon.process import ProcessCancelled

        result = JobResult(status="failed")
        try:
            rec = self._invoke_process(
                handle, on_event, observers, prefer_gpu, open_review
            )
            result = JobResult(status="completed", rec=rec, run_id=rec.get("run_id"))
        except ProcessCancelled as e:
            result = JobResult(status="cancelled", run_id=e.run_id, error=e)
        except Exception as e:  # noqa: BLE001 — surface to the submitting UI
            result = JobResult(status="failed", error=e)
        finally:
            self._release(handle)
            if on_done is not None:
                on_done(result)
