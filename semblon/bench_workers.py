"""Hash-worker microbench. Measures hash-phase parallelism only — not inference."""

from __future__ import annotations

import json
import time
from pathlib import Path

from semblon.ingest import _hash_path, _iter_hash_results, discover_media


class BenchError(ValueError):
    pass


def _rss_mb() -> float | None:
    try:
        import resource

        # Linux: ru_maxrss is KiB; macOS is bytes — report best-effort.
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if rss > 10_000_000:  # likely bytes
            return round(rss / (1024 * 1024), 1)
        return round(rss / 1024.0, 1)
    except Exception:
        return None


def bench_hash_workers(
    folder: Path,
    store_dir: Path,
    *,
    workers_list: list[int] | None = None,
) -> dict:
    """Time hash-only passes at workers=1/2/4. Does not run FaceKit.

    Semantic equivalence: same set of path digests across worker counts.
    """
    folder = Path(folder)
    store_dir = Path(store_dir)
    if not folder.is_dir():
        raise BenchError(f"folder not found: {folder}")
    store_dir.mkdir(parents=True, exist_ok=True)
    workers_list = list(workers_list or [1, 2, 4])
    for w in workers_list:
        if int(w) < 1:
            raise BenchError("workers must be >= 1")

    stills, videos = discover_media(folder)
    files = list(stills) + list(videos)
    if not files:
        raise BenchError("no media files discovered")

    results = []
    digests_by_workers: dict[int, list[str]] = {}
    for w in workers_list:
        t0 = time.perf_counter()
        digests: list[str] = []
        n_ok = 0
        n_fail = 0
        for rec in _iter_hash_results(files, workers=int(w), want_cancel=lambda: False):
            if rec.get("outcome") == "hashed":
                n_ok += 1
                digests.append(str(rec.get("sha256") or ""))
            else:
                n_fail += 1
        elapsed = time.perf_counter() - t0
        digests_by_workers[int(w)] = sorted(digests)
        results.append(
            {
                "workers": int(w),
                "files": len(files),
                "hashed_ok": n_ok,
                "hashed_failed": n_fail,
                "elapsed_s": round(elapsed, 4),
                "hash_files_per_s": round(n_ok / elapsed, 3) if elapsed > 0 else None,
                "rss_mb": _rss_mb(),
                "note": "hash phase only; decode/embed remain single-session",
            }
        )

    baseline = digests_by_workers.get(1)
    equiv = True
    if baseline is not None:
        for w, digs in digests_by_workers.items():
            if digs != baseline:
                equiv = False
                break
    return {
        "folder": str(folder),
        "files": len(files),
        "phase": "hash_only",
        "inference_parallel": False,
        "semantic_digest_equivalence": equiv,
        "runs": results,
        "recommendation": _recommend(results),
    }


def _recommend(results: list[dict]) -> str:
    if not results:
        return "no data"
    by_w = {r["workers"]: r for r in results}
    base = by_w.get(1)
    if base is None or not base.get("elapsed_s"):
        return "keep workers=1 (no baseline)"
    best = min(results, key=lambda r: float(r["elapsed_s"] or 1e9))
    if best["workers"] == 1:
        return "keep default workers=1; higher worker counts were not faster on this folder"
    speedup = float(base["elapsed_s"]) / float(best["elapsed_s"])
    if speedup < 1.1:
        return "keep default workers=1; measured gain under 10%"
    return (
        f"workers={best['workers']} was fastest ({speedup:.2f}x vs 1) for hash-only; "
        "still not inference parallelism — do not claim ingest acceleration"
    )


def write_bench_report(rec: dict, out: Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


# Re-export for tests that want a one-shot hash.
hash_one = _hash_path
