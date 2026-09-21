"""PERF workers measure harness — hash-phase only.

Measures bounded hash workers=1/2/4 via ingest helpers. Does not run decode,
FaceKit embed, or SQLite write. Product default remains workers=1; this harness
never recommends flipping that default.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

# Prefer ingest helpers; fall back only if import fails (e.g. partial checkout).
try:
    from semblon.ingest import _iter_hash_results, discover_media

    _INGEST_HELPERS_OK = True
except ImportError:  # pragma: no cover - helpers exist on main
    _iter_hash_results = None  # type: ignore[assignment]
    discover_media = None  # type: ignore[assignment]
    _INGEST_HELPERS_OK = False

DEFAULT_PRODUCT_WORKERS = 1
DEFAULT_WORKERS_LIST = (1, 2, 4)
HASH_PHASE_NOTE = (
    "hash-phase only; decode, FaceKit embed, and SQLite write are not measured. "
    "Product default remains workers=1; do not change defaults from this harness alone."
)


def _base_report(
    *,
    folder: Path | None,
    workers_list: list[int],
    verified: bool,
    status: str,
) -> dict[str, Any]:
    return {
        "harness": "perf_workers_measure",
        "phase": "hash",
        "note": HASH_PHASE_NOTE,
        "default_product_workers": DEFAULT_PRODUCT_WORKERS,
        "recommend_change_default": False,
        "recommendation": "keep product default workers=1",
        "verified": verified,
        "folder": str(folder) if folder is not None else None,
        "workers_list": list(workers_list),
        "ingest_helpers_ok": _INGEST_HELPERS_OK,
        "status": status,
        "file_count": 0,
        "runs": [],
    }


def _speedup(baseline_s: float, wall_s: float) -> float | None:
    if baseline_s <= 0 or wall_s <= 0:
        return None
    return round(baseline_s / wall_s, 4)


def _measure_one(
    files: list[Path],
    *,
    workers: int,
    want_cancel: Callable[[], bool],
) -> dict[str, Any]:
    hashed = 0
    failed = 0
    t0 = time.perf_counter()
    for rec in _iter_hash_results(files, workers=workers, want_cancel=want_cancel):
        if rec.get("outcome") == "failed":
            failed += 1
        else:
            hashed += 1
    wall_s = time.perf_counter() - t0
    n = hashed + failed
    return {
        "workers": int(workers),
        "wall_s": round(wall_s, 6),
        "hashed": hashed,
        "failed": failed,
        "files_per_s": round(n / wall_s, 4) if wall_s > 0 and n else 0.0,
    }


def measure_hash_workers(
    folder: Path | str | None,
    workers_list: list[int] | tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Time hash-phase only for each worker count; report speedup vs workers=1.

    When ``folder`` is missing or not a directory, returns ``verified=False``
    and empty runs for the requested worker counts. Never recommends changing
    the product default (always ``DEFAULT_PRODUCT_WORKERS``).
    """
    wlist = list(workers_list) if workers_list is not None else list(DEFAULT_WORKERS_LIST)
    if not wlist:
        wlist = list(DEFAULT_WORKERS_LIST)
    for w in wlist:
        if int(w) < 1:
            raise ValueError("workers must be >= 1")

    if folder is None:
        report = _base_report(
            folder=None,
            workers_list=wlist,
            verified=False,
            status="folder missing — not executed",
        )
        report["runs"] = [{"workers": int(w), "wall_s": None, "speedup_vs_w1": None} for w in wlist]
        return report

    path = Path(folder)
    if not path.is_dir():
        report = _base_report(
            folder=path,
            workers_list=wlist,
            verified=False,
            status="folder missing — not executed",
        )
        report["runs"] = [{"workers": int(w), "wall_s": None, "speedup_vs_w1": None} for w in wlist]
        return report

    if not _INGEST_HELPERS_OK:
        report = _base_report(
            folder=path,
            workers_list=wlist,
            verified=False,
            status="ingest helpers not importable — hash measure skipped",
        )
        report["runs"] = [{"workers": int(w), "wall_s": None, "speedup_vs_w1": None} for w in wlist]
        return report

    stills, _videos = discover_media(path)
    files = list(stills)
    report = _base_report(
        folder=path.resolve(),
        workers_list=wlist,
        verified=True,
        status="hash-phase measured",
    )
    report["file_count"] = len(files)

    want_cancel: Callable[[], bool] = lambda: False
    runs: list[dict[str, Any]] = []
    for w in wlist:
        runs.append(_measure_one(files, workers=int(w), want_cancel=want_cancel))

    w1 = next((r for r in runs if r["workers"] == 1), None)
    baseline_s = float(w1["wall_s"]) if w1 is not None else None
    for r in runs:
        if r["workers"] == 1:
            r["speedup_vs_w1"] = 1.0 if r["wall_s"] and float(r["wall_s"]) > 0 else None
        elif baseline_s is not None:
            r["speedup_vs_w1"] = _speedup(baseline_s, float(r["wall_s"] or 0.0))
        else:
            r["speedup_vs_w1"] = None

    report["runs"] = runs
    report["note"] = HASH_PHASE_NOTE
    report["recommend_change_default"] = False
    report["recommendation"] = "keep product default workers=1"
    report["default_product_workers"] = DEFAULT_PRODUCT_WORKERS
    return report
