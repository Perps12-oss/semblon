"""Thin event channel around the existing job API.

Names are shell observations. They are not written into identity or clustering.
"""

from __future__ import annotations

from threading import Lock


JOB_STARTED = "job.started"
JOB_PROGRESS = "job.progress"
JOB_PAUSED = "job.paused"
JOB_COMPLETED = "job.completed"
JOB_CANCELLED = "job.cancelled"
JOB_FAILED = "job.failed"
LIBRARY_CHANGED = "library.changed"
IDENTITY_CHANGED = "identity.changed"

NAMES = (
    JOB_STARTED,
    JOB_PROGRESS,
    JOB_PAUSED,
    JOB_COMPLETED,
    JOB_CANCELLED,
    JOB_FAILED,
    LIBRARY_CHANGED,
    IDENTITY_CHANGED,
)


class ShellEvents:
    """In-process log. Thread-safe record. UI reads it on the Qt thread."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._items: list[dict] = []

    def record(self, name: str, payload: dict | None = None) -> None:
        if name not in NAMES:
            raise ValueError(f"unknown shell event {name}")
        item = {"name": name, "payload": dict(payload or {})}
        with self._lock:
            self._items.append(item)
            if len(self._items) > 200:
                self._items = self._items[-200:]

    def snapshot(self) -> list[dict]:
        with self._lock:
            return [dict(item) for item in self._items]

    def last(self, name: str | None = None) -> dict | None:
        with self._lock:
            rows = self._items
            if name is not None:
                rows = [item for item in rows if item["name"] == name]
            if not rows:
                return None
            item = rows[-1]
            return {"name": item["name"], "payload": dict(item["payload"])}
