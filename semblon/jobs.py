"""Application job boundary.

UI  →  JobEngine  →  process_folder / review.py / visual_analyze

One ingest job at a time. A second ingest submit is JobBusy — not an application lock.
Visual analysis is a separate cooperative slot on the same engine (not a second
job system). Review mutations stay on review.py and wait on the existing writer.
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
KIND_VISUAL_ANALYZE = "visual_analyze"

STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_PAUSED = "paused"
STATE_CANCELLING = "cancelling"

OnEvent = Callable[[ProgressEvent], None]
OnDone = Callable[["JobResult"], None]
OnVisualDone = Callable[["VisualJobResult"], None]


def _load_job_bgr(store: Path, media_id: str | None):
    """Decode the stored file. Callers do not pass pixel arrays across this boundary."""
    from semblon.selection import load_media_bgr

    loaded = load_media_bgr(store, media_id)
    if loaded is None:
        raise FileNotFoundError(f"could not read media {media_id}")
    return loaded


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


@dataclass(frozen=True)
class VisualJobHandle:
    kind: str
    media_id: str
    store: Path


@dataclass(frozen=True)
class VisualJobResult:
    status: str
    media_id: str
    result: dict | None = None
    error: BaseException | None = None


def _process_rss_kb() -> int | None:
    """Peak RSS in KiB on platforms that provide ``resource``. Windows does not."""
    try:
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except Exception:
        return None


class JobEngine:
    """Single door for ingest + visual analysis. UIs submit; they do not own workers."""

    def __init__(self, store: Path):
        self.store = Path(store)
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._pause = threading.Event()  # set => paused; clear => running
        self._thread: threading.Thread | None = None
        self._current: JobHandle | None = None
        self._cancelling = False
        self._visual_lock = threading.Lock()
        self._visual_thread: threading.Thread | None = None
        self._visual_current: VisualJobHandle | None = None
        self._visual_cancel = threading.Event()

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
    def visual_busy(self) -> bool:
        with self._visual_lock:
            return self._visual_current is not None

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

    def shutdown(self, timeout: float = 30.0) -> None:
        """Cancel in-flight writers and join them. Call before the process exits."""
        if getattr(self, "_shut_down", False):
            return
        self._shut_down = True
        self.cancel()
        self.cancel_visual()
        threads: list[threading.Thread] = []
        with self._lock:
            if self._thread is not None:
                threads.append(self._thread)
        with self._visual_lock:
            if self._visual_thread is not None:
                threads.append(self._visual_thread)
        deadline = time.monotonic() + max(0.0, float(timeout))
        for thread in threads:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if thread.is_alive():
                thread.join(remaining)

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
        reprocess: bool = False,
    ) -> JobHandle:
        """Start process_folder on a worker thread. Raises JobBusy if running."""
        handle = self._claim(folder, resume=resume)
        thread = threading.Thread(
            target=self._run_submitted,
            args=(handle, on_event, on_done, observers, prefer_gpu, open_review, bool(reprocess)),
            daemon=False,
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
        run_id: str,
        on_event: OnEvent | None = None,
        on_done: OnDone | None = None,
        nouns: list[str] | None = None,
        score_fn=None,
        config=None,
        view_w: int | None = None,
        view_h: int | None = None,
    ) -> JobHandle:
        """Background visual-region analysis. Same door as ingest. Not pointer-time.

        The stored file is decoded inside the worker. No ndarray crosses this call.
        """
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
            target=self._run_visual_regions,
            args=(handle, run_id, on_event, on_done, nouns, score_fn, config, view_w, view_h),
            daemon=False,
            name="semblon-job-visual-regions",
        )
        with self._lock:
            self._thread = thread
        thread.start()
        return handle

    def _run_visual_regions(
        self,
        handle: JobHandle,
        run_id: str,
        on_event,
        on_done,
        nouns,
        score_fn,
        config,
        view_w,
        view_h,
    ) -> None:
        import numpy as np

        from semblon.progress import ProgressEvent
        from semblon.visual.discovery import sam2_capability
        from semblon.visual.engine import analyse
        from semblon.visual.persist import load_scene_inputs, persist_analysis

        result = JobResult(status="failed", run_id=run_id)
        try:
            image = _load_job_bgr(self.store, handle.media_id)
            if on_event:
                on_event(ProgressEvent(stage="visual", kind="started", message="understanding"))
            if self._gate():
                result = JobResult(status="cancelled", run_id=run_id)
            else:
                frame = np.asarray(image)
                rgb = np.ascontiguousarray(frame[:, :, :3][:, :, ::-1])
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
                    rss = _process_rss_kb()
                    if rss is not None:
                        rec["rss_kb"] = rss
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

    def submit_visual_analyze(
        self,
        *,
        media_id: str,
        existing_faces: list | None = None,
        observation_id: str | None = None,
        force: bool = False,
        on_progress: Callable | None = None,
        on_done: OnVisualDone | None = None,
    ) -> VisualJobHandle:
        """Open-vocabulary visual analysis on a worker thread (non-identity).

        Concurrent with ingest is allowed — visual does not take the ingest lock.
        A second visual submit for any media is JobBusy until the first finishes.
        The stored file is decoded inside the worker.
        """
        handle = VisualJobHandle(
            kind=KIND_VISUAL_ANALYZE, media_id=str(media_id), store=self.store
        )
        with self._visual_lock:
            if self._visual_current is not None:
                raise JobBusy("visual analysis already running")
            self._visual_cancel.clear()
            self._visual_current = handle
            thread = threading.Thread(
                target=self._run_visual,
                args=(
                    handle,
                    existing_faces,
                    observation_id,
                    force,
                    on_progress,
                    on_done,
                ),
                daemon=False,
                name="semblon-job-visual",
            )
            self._visual_thread = thread
        thread.start()
        return handle

    def cancel_visual(self) -> None:
        self._visual_cancel.set()

    def _run_visual(
        self,
        handle: VisualJobHandle,
        existing_faces: list | None,
        observation_id: str | None,
        force: bool,
        on_progress: Callable | None,
        on_done: OnVisualDone | None,
    ) -> None:
        result = VisualJobResult(status="failed", media_id=handle.media_id)
        try:
            if self._visual_cancel.is_set():
                result = VisualJobResult(status="cancelled", media_id=handle.media_id)
            else:
                from semblon.visual_analyze import analyze_and_cache

                image = _load_job_bgr(self.store, handle.media_id)

                def _prog(stage: str, extra: dict):
                    if self._visual_cancel.is_set():
                        raise InterruptedError("visual cancelled")
                    if on_progress is not None:
                        on_progress(stage, extra)

                rec = analyze_and_cache(
                    handle.store,
                    media_id=handle.media_id,
                    image=image,
                    observation_id=observation_id,
                    existing_faces=existing_faces,
                    force=force,
                    on_progress=_prog,
                )
                result = VisualJobResult(
                    status="completed", media_id=handle.media_id, result=rec
                )
        except InterruptedError as e:
            result = VisualJobResult(
                status="cancelled", media_id=handle.media_id, error=e
            )
        except Exception as e:  # noqa: BLE001 — surface to the submitting UI
            result = VisualJobResult(
                status="failed", media_id=handle.media_id, error=e
            )
        finally:
            with self._visual_lock:
                if self._visual_current is handle:
                    self._visual_current = None
                    self._visual_thread = None
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
        reprocess: bool = False,
    ) -> dict:
        """Run process_folder on this thread. Raises JobBusy if running."""
        handle = self._claim(folder, resume=resume)
        try:
            return self._invoke_process(
                handle, on_event, observers, prefer_gpu, open_review, bool(reprocess)
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
        reprocess: bool = False,
    ) -> dict:
        from semblon.process import process_folder

        kwargs: dict = {
            "store": self.store,
            "open_review": open_review,
            "progress": lambda *_: None,
            "on_event": on_event,
            "cancel": self._gate,
            "resume": handle.resume,
            "reprocess": bool(reprocess),
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
        reprocess: bool = False,
    ) -> None:
        from semblon.process import ProcessCancelled

        result = JobResult(status="failed")
        try:
            rec = self._invoke_process(
                handle, on_event, observers, prefer_gpu, open_review, reprocess
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
