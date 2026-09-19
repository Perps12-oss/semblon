"""UI-agnostic process progress events.

CLI and a future GUI consume the same callback. No Tk/CTk/HTML dependency.
Reporting is optional: on_event=None is a no-op and must not change work.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    run_id: str | None = None,
    message: str | None = None,
    error: str | None = None,
    outcome: str | None = None,
    counts: Mapping[str, int] | None = None,
) -> ProgressEvent:
    if percent is None:
        percent = ratio_percent(current, total)
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
        run_id=run_id,
        message=message,
        error=error,
        outcome=outcome,
        counts=counts,
    )


def emit(on_event: ProgressCallback, event: ProgressEvent) -> None:
    """Invoke the consumer. A broken UI must not abort the pipeline."""
    if on_event is None:
        return
    try:
        on_event(event)
    except Exception:
        pass
