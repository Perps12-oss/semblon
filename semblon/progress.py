"""UI-agnostic process progress events.

CLI and a future GUI consume the same callback. No Tk/CTk/HTML dependency.
Reporting is optional: on_event=None is a no-op and must not change work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping

STAGE_PROCESS = "process"
STAGE_DISCOVER = "discover"
STAGE_INGEST = "ingest"
STAGE_CLUSTER = "cluster"
STAGE_EXPORT = "export"

KIND_QUEUED = "queued"
KIND_STARTED = "started"
KIND_PROGRESS = "progress"
KIND_PARTIAL = "partial"
KIND_COMPLETED = "completed"
KIND_FAILED = "failed"
KIND_CANCELLED = "cancelled"
KIND_STALLED = "stalled"

STAGES = (
    STAGE_PROCESS,
    STAGE_DISCOVER,
    STAGE_INGEST,
    STAGE_CLUSTER,
    STAGE_EXPORT,
)
KINDS = (
    KIND_QUEUED,
    KIND_STARTED,
    KIND_PROGRESS,
    KIND_PARTIAL,
    KIND_COMPLETED,
    KIND_FAILED,
    KIND_CANCELLED,
    KIND_STALLED,
)


@dataclass(frozen=True)
class ProgressEvent:
    """One observation from the process pipeline. Missing metrics stay None."""

    stage: str
    kind: str
    current: int | None = None
    total: int | None = None
    percent: float | None = None
    files_processed: int | None = None
    files_total: int | None = None
    faces_found: int | None = None
    path: str | None = None
    elapsed_s: float | None = None
    eta_s: float | None = None
    clock: str | None = None
    run_id: str | None = None
    message: str | None = None
    error: str | None = None
    outcome: str | None = None
    counts: Mapping[str, int] | None = None

    def as_tuple(self) -> tuple[str, str]:
        return (self.stage, self.kind)


ProgressCallback = Callable[[ProgressEvent], None] | None


def ratio_percent(current: int | None, total: int | None) -> float | None:
    """Percent only when a real denominator exists. Never invent one."""
    if current is None or total is None or total <= 0:
        return None
    value = 100.0 * float(current) / float(total)
    if value < 0:
        return 0.0
    if value > 100:
        return 100.0
    return round(value, 1)


def stills_percent(event: ProgressEvent) -> float | None:
    """0–100 from still/file counts. Never invent a denominator."""
    if event.percent is not None:
        return event.percent
    pct = ratio_percent(event.files_processed, event.files_total)
    if pct is not None:
        return pct
    return ratio_percent(event.current, event.total)


def format_duration(seconds: float | None) -> str | None:
    if seconds is None or seconds < 0:
        return None
    s = int(round(float(seconds)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def estimate_eta_s(
    elapsed_s: float | None,
    current: int | None,
    total: int | None,
) -> float | None:
    """Remaining seconds from real work already done. None when that would be a guess."""
    if elapsed_s is None or current is None or total is None:
        return None
    if current <= 0 or total <= current or elapsed_s <= 0:
        return None
    return round((total - current) * (elapsed_s / current), 1)


def format_progress_bar(percent: float, width: int = 24) -> str:
    """ASCII bar that fills as stills climb toward 100%."""
    pct = max(0.0, min(100.0, float(percent)))
    filled = int(round(width * pct / 100.0))
    filled = min(width, max(0, filled))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def clock_now(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%H:%M:%S")


def make_event(
    stage: str,
    kind: str,
    *,
    current: int | None = None,
    total: int | None = None,
    percent: float | None = None,
    files_processed: int | None = None,
    files_total: int | None = None,
    faces_found: int | None = None,
    path: str | None = None,
    elapsed_s: float | None = None,
    eta_s: float | None = None,
    clock: str | None = None,
    run_id: str | None = None,
    message: str | None = None,
    error: str | None = None,
    outcome: str | None = None,
    counts: Mapping[str, int] | None = None,
    now: datetime | None = None,
) -> ProgressEvent:
    if percent is None:
        percent = ratio_percent(current, total)
    if percent is None:
        percent = ratio_percent(files_processed, files_total)
    work_current = current if current is not None else files_processed
    work_total = total if total is not None else files_total
    if eta_s is None:
        eta_s = estimate_eta_s(elapsed_s, work_current, work_total)
    if clock is None:
        clock = clock_now(now)
    return ProgressEvent(
        stage=stage,
        kind=kind,
        current=current,
        total=total,
        percent=percent,
        files_processed=files_processed,
        files_total=files_total,
        faces_found=faces_found,
        path=path,
        elapsed_s=elapsed_s,
        eta_s=eta_s,
        clock=clock,
        run_id=run_id,
        message=message,
        error=error,
        outcome=outcome,
        counts=counts,
    )


def format_progress_line(event: ProgressEvent) -> str:
    """Human status line. Never invents a percent when the event has none."""
    parts = [f"{event.stage}:{event.kind}"]
    pct = stills_percent(event)
    if pct is not None:
        parts.append(format_progress_bar(pct))
    if event.message:
        parts.append(event.message)
    if event.files_processed is not None and event.files_total is not None:
        parts.append(f"files {event.files_processed}/{event.files_total}")
    elif event.current is not None and event.total is not None:
        parts.append(f"{event.current}/{event.total}")
    if pct is not None:
        parts.append(f"{pct:g}%")
    if event.clock:
        parts.append(event.clock)
    elapsed = format_duration(event.elapsed_s)
    if elapsed:
        parts.append(f"elapsed {elapsed}")
    eta = format_duration(event.eta_s)
    if eta:
        parts.append(f"eta {eta}")
    if event.run_id:
        parts.append(f"run={event.run_id}")
    if event.error:
        parts.append(event.error)
    return "  ".join(parts)


def emit(on_event: ProgressCallback, event: ProgressEvent) -> None:
    """Invoke the consumer. A broken UI must not abort the pipeline."""
    if on_event is None:
        return
    try:
        on_event(event)
    except Exception:
        pass
