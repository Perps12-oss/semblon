"""Double-click home — client of the application Job boundary.

Not the canonical workstation architecture. Tk is a replaceable client.
Opaque tkinter. No Mica. Jobs live in semblon.jobs; this window observes them.
Progress text comes from Job snapshots / process events only — no invented percent.
"""

from __future__ import annotations

import json
import queue
import sqlite3
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError:  # pragma: no cover - depends on host Python build
    tk = None
    filedialog = messagebox = ttk = None

from semblon.desktop.copy import friendly_exception, status_text
from semblon.jobs import JobBusy, JobEngine, home_control_states
from semblon.process import default_store_path
from semblon.progress import (
    KIND_QUEUED,
    KIND_STALLED,
    STAGE_PROCESS,
    ProgressEvent,
    format_duration,
    format_progress_line,
    make_event,
    stills_percent,
)

# Tests and callers import the status line from home_ui.
__all__ = ["HOME_OBSERVERS", "HomeApp", "format_progress_line", "run_home_ui"]
from semblon.watchdog import Watchdog

# Home ingest fills cheap non-identity items for Canvas. Face remains identity.
HOME_OBSERVERS = "face,color,object"
