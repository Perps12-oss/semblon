"""Measure hash-phase workers on the current ingest pool.

``workers>1`` parallelizes ``_hash_path`` only. This does not time inference
and must not be cited as an inference speedup. It does not change the
product default (workers=1).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from semblon.ingest import _iter_hash_results


def _rss_mb() -> float | None:
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1]) / 1024.0, 2)
    except OSError:
        return None
    return None


def _cpu_jiffies() -> tuple[int, int] | None:
    try:
        parts = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0].split()[1:]
        nums = [int(part) for part in parts]
    except (OSError, ValueError, IndexError):
        return None
    idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
    return sum(nums), idle


def _digests(rows: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        if row.get("outcome") != "hashed":
            raise RuntimeError(f"hash failed: {row.get('path')} {row.get('error')}")
        out[str(row["path"])] = str(row["digest"])
    return out


def measure_folder(folder: Path, workers: tuple[int, ...] = (1, 2, 4)) -> dict:
    """Hash every file in ``folder`` at each worker count. Compare digests."""
    folder = Path(folder)
    files = sorted(path for path in folder.iterdir() if path.is_file())
    if not files:
        raise FileNotFoundError(f"no files in {folder}")
    runs = []
    digest_sets: list[dict[str, str]] = []
    for count in workers:
        rss_before = _rss_mb()
        cpu_before = _cpu_jiffies()
        t0 = time.perf_counter()
        rows = list(_iter_hash_results(files, workers=int(count), want_cancel=lambda: False))
        wall = time.perf_counter() - t0
        rss_after = _rss_mb()
        cpu_after = _cpu_jiffies()
        digests = _digests(rows)
        digest_sets.append(digests)
        cpu_pct = None
        if cpu_before and cpu_after:
            total = cpu_after[0] - cpu_before[0]
            idle = cpu_after[1] - cpu_before[1]
            if total > 0:
                cpu_pct = round(100.0 * (total - idle) / total, 1)
        nbytes = sum(path.stat().st_size for path in files)
        runs.append(
            {
                "workers": int(count),
                "files": len(files),
                "bytes": nbytes,
                "wall_s": round(wall, 4),
                "files_per_s": round(len(files) / wall, 3) if wall > 0 else None,
                "mib_per_s": round((nbytes / (1024 * 1024)) / wall, 3) if wall > 0 else None,
                "rss_mb_before": rss_before,
                "rss_mb_after": rss_after,
                "cpu_pct_machine": cpu_pct,
                "inference": False,
            }
        )
    base = digest_sets[0]
    equivalent = all(item == base for item in digest_sets[1:])
    best = max(runs, key=lambda row: row["files_per_s"] or 0)
    w1 = runs[0]["files_per_s"] or 0
    speedup = round((best["files_per_s"] or 0) / w1, 3) if w1 else None
    return {
        "tool": "measure_hash_workers",
        "phase": "hash-only",
        "inference_parallel": False,
        "product_default_workers": 1,
        "default_changed": False,
        "cpu_count": os.cpu_count(),
        "semantic_equivalent": equivalent,
        "best_workers": best["workers"],
        "speedup_best_vs_w1": speedup,
        "runs": runs,
        "note": (
            "Wall time is the current _iter_hash_results pool only. "
            "It is not end-to-end ingest and not FaceKit/YuNet throughput."
        ),
    }
