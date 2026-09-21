"""R3 §6 measurement runners — measure, don't prefer; refuse fake PASS.

Companion to ``tools/r3_bakeoff`` (aggregation). This package owns per-criterion
runners only. Without real OS/toolkit measurements every runner stays
``verified=False`` / ``pass=False`` / ``status=\"unverified\"``.
"""

from __future__ import annotations

from .refuse import FakePassError, assert_no_fake_pass, mark_unverified
from .runners import (
    CRITERIA,
    CRITERION_IDS,
    run_accent_suppress,
    run_a11y_tree,
    run_all,
    run_frame_time_4k60,
    run_mica_opaque,
    run_virtualized_grid_10k,
    run_wcag_aa,
)

__all__ = [
    "CRITERIA",
    "CRITERION_IDS",
    "FakePassError",
    "assert_no_fake_pass",
    "mark_unverified",
    "run_a11y_tree",
    "run_accent_suppress",
    "run_all",
    "run_frame_time_4k60",
    "run_mica_opaque",
    "run_virtualized_grid_10k",
    "run_wcag_aa",
]
