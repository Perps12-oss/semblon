"""Language-neutral application façade.

A future native UI talks to these names, not to Home widgets or FaceKit.
Mutations stay in review.py via review_ui.apply_*. Reads are RO SQLite.
"""

from __future__ import annotations

from pathlib import Path

from semblon.jobs import (
    JOB_TYPE_INGEST,
    JobBusy,
    JobEngine,
    JobSnapshot,
    home_control_states,
)
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

__all__ = [
    "JOB_TYPE_INGEST",
    "JobBusy",
    "JobEngine",
    "JobSnapshot",
    "apply_ignore",
    "apply_merge",
    "apply_name",
    "apply_note",
    "apply_split",
    "default_store_path",
    "home_control_states",
    "latest_run_id",
    "load_board",
    "resolve_run_id",
]


def board(store: Path, run_id: str | None = None) -> dict:
    """Read-only review board. Does not enrol anyone."""
    rid = resolve_run_id(store, run_id)
    return load_board(store, rid)
