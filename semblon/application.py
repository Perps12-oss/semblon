"""Language-neutral application façade.

A future native UI talks to these names, not to Home widgets or FaceKit.
Mutations stay in review.py via review_ui.apply_*. Reads are RO SQLite.
Job ownership lives in semblon.jobs. Home is a client.
"""

from __future__ import annotations

from pathlib import Path

from semblon.canvas import load_canvas
from semblon.home_ui import home_control_states
from semblon.inbox import inbox
from semblon.jobs import KIND_INGEST, JobBusy, JobEngine, JobHandle, JobResult
from semblon.process import default_store_path, latest_run_id
from semblon.review_ui import (
    apply_ignore,
    apply_merge,
    apply_name,
    apply_note,
    apply_split,
    load_board,
    resolve_run_id,
)
from semblon.search import search_people, search_person

__all__ = [
    "KIND_INGEST",
    "JobBusy",
    "JobEngine",
    "JobHandle",
    "JobResult",
    "apply_ignore",
    "apply_merge",
    "apply_name",
    "apply_note",
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
    """Read-only review board. Does not enrol anyone."""
    rid = resolve_run_id(store, run_id)
    return load_board(store, rid)
