"""Optional pytest plugin. Activate with SEMBLON_P0_SQL_TRACE=1."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def pytest_configure(config):  # noqa: ARG001
    if os.environ.get("SEMBLON_P0_SQL_TRACE", "").strip() not in {"1", "true", "yes"}:
        return
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    from p0.sql_runtime_trace import install, reset

    install()
    reset()


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    if os.environ.get("SEMBLON_P0_SQL_TRACE", "").strip() not in {"1", "true", "yes"}:
        return
    from p0.sql_runtime_trace import dump, summary

    out = Path(os.environ.get("SEMBLON_P0_SQL_TRACE_OUT") or (ROOT / "artifacts" / "p0" / "sql_runtime_trace.json"))
    dump(out)
    stats = summary()
    print(
        f"\nP0 SQL trace: events={stats.event_count} connections={stats.connections} out={out}",
        flush=True,
    )
