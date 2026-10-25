"""Local performance evidence. One JSON line per measured run, next to the store.

It records how long things took and on what machine. It never records photo
names, paths, or pixels. Set ``SEMBLON_PERF=0`` to switch it off. A write
failure is swallowed: measuring must never break indexing or search.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

FILE_NAME = "perf-evidence.jsonl"
MAX_BYTES = 2_000_000
_FORBIDDEN = {"path", "paths", "name", "names", "folder", "file", "files", "query", "text"}


def enabled() -> bool:
    return os.environ.get("SEMBLON_PERF", "1").strip().lower() not in {"0", "off", "false", "no"}


def evidence_path(store: Path | str) -> Path:
    return Path(store).with_name(FILE_NAME)


def machine() -> dict:
    return {
        "os": platform.system().lower(),
        "machine": platform.machine().lower(),
        "python_arch": platform.architecture()[0],
        "python": sys.version.split()[0],
    }


def _clean(value):
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 3) if isinstance(value, float) else value
    if isinstance(value, str):
        return value if len(value) <= 80 else value[:80]
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items() if str(k).lower() not in _FORBIDDEN}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in list(value)[:32]]
    return str(value)[:80]


def record(store: Path | str, event: str, **fields) -> bool:
    """Append one record. Returns whether it was written."""
    if not enabled():
        return False
    try:
        from semblon import __version__

        line = {
            "t": time.time(),
            "event": str(event),
            "version": __version__,
            **machine(),
            **{k: _clean(v) for k, v in fields.items() if k.lower() not in _FORBIDDEN},
        }
        target = evidence_path(store)
        if target.exists() and target.stat().st_size > MAX_BYTES:
            keep = target.read_text(encoding="utf-8").splitlines()[-2000:]
            target.write_text("\n".join(keep) + "\n", encoding="utf-8")
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, separators=(",", ":")) + "\n")
        return True
    except Exception:  # noqa: BLE001 — measuring must not break the app
        return False


def read(store: Path | str, event: str | None = None) -> list[dict]:
    target = evidence_path(store)
    if not target.is_file():
        return []
    rows: list[dict] = []
    for raw in target.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if event is None or row.get("event") == event:
            rows.append(row)
    return rows


def report(store: Path | str) -> dict:
    """Summary an engineer can paste into an issue. No personal content."""
    ingests = read(store, "ingest")
    searches = read(store, "search")
    latencies = sorted(float(r["latency_ms"]) for r in searches if "latency_ms" in r)

    def pct(p: float) -> float | None:
        if not latencies:
            return None
        return latencies[min(len(latencies) - 1, int(p * len(latencies)))]

    return {
        "machine": machine(),
        "ingest_runs": len(ingests),
        "last_ingest": ingests[-1] if ingests else None,
        "searches": len(searches),
        "search_ms_p50": pct(0.5),
        "search_ms_p95": pct(0.95),
        "first_search_ms": float(searches[0]["latency_ms"]) if searches and "latency_ms" in searches[0] else None,
    }
