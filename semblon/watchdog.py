"""Stall vs slow vs failed. Does not kill jobs. Does not invent percent."""

from __future__ import annotations

import time

from semblon.progress import (
    KIND_CANCELLED,
    KIND_COMPLETED,
    KIND_FAILED,
    KIND_PARTIAL,
    KIND_PROGRESS,
    KIND_STARTED,
    KIND_STALLED,
    ProgressEvent,
    make_event,
)

DEFAULT_STALL_S = 120.0
_ALIVE = {
    KIND_STARTED,
    KIND_PROGRESS,
    KIND_PARTIAL,
    KIND_COMPLETED,
    KIND_FAILED,
    KIND_CANCELLED,
}


class Watchdog:
    """Track last meaningful progress. Stalled ≠ slow ≠ failed."""

    def __init__(self, stall_s: float = DEFAULT_STALL_S):
        if stall_s <= 0:
            raise ValueError("stall_s must be > 0")
        self.stall_s = float(stall_s)
        self.last_monotonic = time.monotonic()
        self.last_event: ProgressEvent | None = None
        self.started_monotonic = self.last_monotonic

    def note(self, event: ProgressEvent) -> None:
        if event.kind in _ALIVE:
            self.last_monotonic = time.monotonic()
            self.last_event = event

    def idle_s(self, now: float | None = None) -> float:
        t = time.monotonic() if now is None else now
        return max(0.0, t - self.last_monotonic)

    def check(self, now: float | None = None) -> ProgressEvent | None:
        idle = self.idle_s(now)
        if idle < self.stall_s:
            return None
        last = self.last_event
        return make_event(
            last.stage if last else "process",
            KIND_STALLED,
            run_id=last.run_id if last else None,
            elapsed_s=idle,
            message=f"no progress for {idle:.0f}s (stall_s={self.stall_s:g})",
            outcome="stalled",
        )

    def classify(self, now: float | None = None) -> str:
        last = self.last_event
        if last is None:
            idle = self.idle_s(now)
            if idle >= self.stall_s:
                return "stalled"
            return "queued"
        if last.kind == KIND_FAILED:
            return "failed"
        if last.kind == KIND_CANCELLED:
            return "cancelled"
        if last.kind == KIND_COMPLETED:
            return "completed"
        if last.kind == KIND_PARTIAL:
            return "partial"
        if self.idle_s(now) >= self.stall_s:
            return "stalled"
        return "slow" if self.idle_s(now) > min(30.0, self.stall_s / 2) else "running"
