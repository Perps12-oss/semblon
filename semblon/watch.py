"""Folder poll watcher. Cancellable. Incremental ingest. Not identity."""

from __future__ import annotations

import time
from pathlib import Path

from semblon.ingest import CancelledError, ingest
from semblon.progress import (
    KIND_CANCELLED,
    KIND_COMPLETED,
    KIND_PROGRESS,
    KIND_STARTED,
    ProgressCallback,
    emit,
    make_event,
)


class WatchError(ValueError):
    pass


def watch_folder(
    folder: Path,
    store: Path,
    *,
    interval_s: float = 5.0,
    once: bool = False,
    cancel=None,
    on_event: ProgressCallback = None,
    observers: str = "face",
) -> dict:
    folder = Path(folder)
    if not folder.is_dir():
        raise WatchError(f"folder not found: {folder}")
    emit(on_event, make_event("watch", KIND_STARTED, path=str(folder)))
    runs = []
    cycles = 0
    while True:
        if cancel is not None:
            try:
                if cancel():
                    emit(on_event, make_event("watch", KIND_CANCELLED, message="cancelled"))
                    raise CancelledError("watch cancelled")
            except CancelledError:
                raise
            except Exception:
                pass
        cycles += 1
        try:
            rec = ingest(folder, store, observers=observers, on_event=on_event, cancel=cancel)
            runs.append(rec.get("run_id"))
            emit(
                on_event,
                make_event(
                    "watch",
                    KIND_PROGRESS,
                    current=cycles,
                    path=str(folder),
                    run_id=rec.get("run_id"),
                    outcome="ingest",
                    counts={"new_media": rec.get("new_media") or 0, "skipped_seen": rec.get("skipped_seen") or 0},
                ),
            )
        except CancelledError:
            raise
        if once:
            break
        time.sleep(max(0.2, float(interval_s)))
    emit(on_event, make_event("watch", KIND_COMPLETED, current=cycles, total=cycles))
    return {"cycles": cycles, "runs": runs, "folder": str(folder)}
