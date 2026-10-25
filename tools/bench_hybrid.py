"""End-to-end benchmark of three ways to prepare a library for "find this detail".

A  Exhaustive: every photo gets the whole-picture pass and all fine detail up front
   (the original 15-piece behaviour, the reference).
B  On demand: nothing is prepared; a search analyses the photos it needs first.
C  Hybrid: whole-picture pass for every photo, fine detail added for the
   promising photos during a search, the rest filled in by background work.

Evaluation set (no hand labels, identical for A/B/C): a folder of photos plus a
re-encoded copy (smaller, recompressed, slightly brighter) of N of them. Each
query is a small crop (about a quarter of the width and height) of an original.
The relevant answer is that photo's copy. The query photo itself is excluded.

Everything is measured by really running the indexing and the search code. Nothing is
extrapolated from per-photo timings. Timings are wall-clock on the machine that runs
this; the report records the machine so an emulated run is never read as native.

Usage:
  python tools/bench_hybrid.py --photos DIR --work DIR [--queries 10] [--out report.json]

The report holds timings and counts only: no file names, no paths, no pixels.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STRATEGIES = ("A", "B", "C")
LABELS = {
    "A": "Exhaustive (all detail up front)",
    "B": "On demand (nothing prepared)",
    "C": "Hybrid (whole picture, then detail where needed)",
}


def peak_memory_mb() -> float | None:
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
            psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
            return round(counters.PeakWorkingSetSize / 1048576, 1)
        import resource

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(peak / (1024 if sys.platform != "darwin" else 1048576), 1)
    except Exception:  # noqa: BLE001
        return None


def _csv(*extra: str) -> str:
    from semblon.observers import resolve_product_observers

    base = [x for x in resolve_product_observers().split(",") if x and not x.startswith("region")]
    return ",".join([*base, *extra])


def build_corpus(photos: Path, work: Path, queries: int, seed: int) -> dict:
    import cv2

    lib = work / "lib"
    if lib.exists():
        shutil.rmtree(lib)
    lib.mkdir(parents=True)
    sources = sorted(p for p in photos.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    rng = random.Random(seed)
    picked = rng.sample(sources, min(queries, len(sources)))
    spec = []
    for path in sources:
        shutil.copy2(path, lib / path.name)
    for index, path in enumerate(picked):
        img = cv2.imread(str(path))
        height, width = img.shape[:2]
        copy = cv2.resize(img, (int(width * 0.7), int(height * 0.7)), interpolation=cv2.INTER_AREA)
        copy = cv2.convertScaleAbs(copy, alpha=1.0, beta=8)
        cv2.imwrite(str(lib / f"copy_{index:02d}.jpg"), copy, [cv2.IMWRITE_JPEG_QUALITY, 70])
        qw, qh = int(width * rng.uniform(0.2, 0.3)), int(height * rng.uniform(0.2, 0.3))
        qx = rng.randint(0, width - qw)
        qy = rng.randint(0, height - qh)
        spec.append({"source": path.name, "copy": f"copy_{index:02d}.jpg", "box": [qx, qy, qw, qh]})
    return {"lib": str(lib), "queries": spec, "photos": len(sources) + len(picked)}


def media_ids(store: Path) -> dict[str, str]:
    from semblon.store import connect

    conn = connect(store)
    try:
        rows = conn.execute("SELECT path, media_id FROM work_items WHERE media_id IS NOT NULL").fetchall()
    finally:
        conn.close()
    return {Path(row[0]).name: str(row[1]) for row in rows}


def coverage(store: Path) -> dict:
    from semblon.scan_tiers import semantic_coverage
    from semblon.store import connect

    conn = connect(store)
    try:
        return semantic_coverage(conn) or {}
    finally:
        conn.close()


def _clean(store: Path) -> None:
    for ext in ("", "-wal", "-shm"):
        Path(str(store) + ext).unlink(missing_ok=True)


def stage_base(args) -> dict:
    from semblon.ingest import ingest

    work = Path(args.work)
    corpus = build_corpus(Path(args.photos), work, args.queries, args.seed)
    store = work / "base.sqlite"
    _clean(store)
    started = time.perf_counter()
    cpu = time.process_time()
    ingest(Path(corpus["lib"]), store, observers=_csv())
    corpus["base_prep_s"] = round(time.perf_counter() - started, 2)
    corpus["base_cpu_s"] = round(time.process_time() - cpu, 2)
    corpus["peak_mb"] = peak_memory_mb()
    ids = media_ids(store)
    for item in corpus["queries"]:
        item["source_id"] = ids[item["source"]]
        item["copy_id"] = ids[item["copy"]]
    (work / "corpus.json").write_text(json.dumps(corpus), encoding="utf-8")
    return {k: v for k, v in corpus.items() if k not in {"queries", "lib"}}


def stage_prep(args) -> dict:
    from semblon.ingest import ingest

    work = Path(args.work)
    corpus = json.loads((work / "corpus.json").read_text(encoding="utf-8"))
    store = work / f"{args.strategy}.sqlite"
    _clean(store)
    shutil.copy2(work / "base.sqlite", store)
    started = time.perf_counter()
    cpu = time.process_time()
    if args.strategy == "A":
        ingest(Path(corpus["lib"]), store, observers=_csv("region"))
    elif args.strategy == "C":
        ingest(Path(corpus["lib"]), store, observers=_csv("region-lite"))
    return {
        "prep_s": round(time.perf_counter() - started, 2),
        "prep_cpu_s": round(time.process_time() - cpu, 2),
        "peak_mb": peak_memory_mb(),
        "coverage": coverage(store),
    }


def _search(strategy: str, store: Path, lib: Path, query: dict, cancelled=None) -> dict:
    from semblon import region_search as rs
    from semblon.similarity_profile import resolve_search_quality

    quality = resolve_search_quality("balanced")
    x, y, w, h = query["box"]
    kwargs = dict(
        image_path=lib / query["source"],
        x=x,
        y=y,
        w=w,
        h=h,
        limit=5,
        media_id=query["source_id"],
        search_quality="balanced",
        cancelled=cancelled,
    )
    started = time.perf_counter()
    promoted = 0
    shortlist: list[str] = []
    if strategy == "A":
        result = rs.find_similar_region(store, **kwargs)
        first = time.perf_counter() - started
    elif strategy == "B":
        crop = rs.crop_bgr(lib / query["source"], x, y, w, h)
        summary = rs.promote_for_search(
            store, [], crop=crop, media_id=query["source_id"], quality=quality, cancelled=cancelled
        )
        promoted = int(summary.get("done") or 0)
        result = rs.find_similar_region(store, **kwargs)
        first = time.perf_counter() - started
    else:
        result = rs.find_similar_region(store, shortlist_out=shortlist, **kwargs)
        first = time.perf_counter() - started
        crop = rs.crop_bgr(lib / query["source"], x, y, w, h)
        sharper = rs._refine_with_detail(
            store,
            shortlist,
            crop=crop,
            media_id=query["source_id"],
            quality=quality,
            cancelled=cancelled,
            rerun=lambda: rs.find_similar_region(store, **kwargs),
        )
        if sharper is not None:
            result = sharper
            promoted = int(sharper.get("detail_promoted") or 0)
    final = time.perf_counter() - started
    ids = [str(item.get("media_id")) for item in (result.get("items") or [])][:5]
    hit = query["copy_id"] in ids
    coverage_info = result.get("coverage") or {}
    return {
        "first_ms": round(first * 1000, 1),
        "final_ms": round(final * 1000, 1),
        "hit": hit,
        "rank": ids.index(query["copy_id"]) + 1 if hit else None,
        "returned": len(ids),
        "promoted": promoted,
        "incomplete": coverage_info.get("complete") is False,
        "disclosed": coverage_info.get("complete") is False and "still" in str(result.get("reason") or ""),
    }


def _med(values: list[float]):
    values = sorted(values)
    return values[len(values) // 2] if values else None


def _summary(rows: list[dict]) -> dict:
    n = len(rows)
    hits = sum(1 for r in rows if r["hit"])
    returned = sum(r["returned"] for r in rows)
    return {
        "queries": n,
        "recall_at_5": round(hits / n, 3) if n else None,
        "precision_at_5": round(hits / returned, 3) if returned else 0.0,
        "first_result_ms_median": _med([r["first_ms"] for r in rows]),
        "first_result_ms_max": max((r["first_ms"] for r in rows), default=None),
        "complete_ms_median": _med([r["final_ms"] for r in rows]),
        "complete_ms_max": max((r["final_ms"] for r in rows), default=None),
        "promoted_photos": sum(r["promoted"] for r in rows),
        "searches_with_incomplete_coverage": sum(1 for r in rows if r["incomplete"]),
        "of_which_disclosed": sum(1 for r in rows if r["disclosed"]),
    }


def stage_search(args) -> dict:
    from semblon import detail_priority
    from semblon import region_search as rs

    work = Path(args.work)
    corpus = json.loads((work / "corpus.json").read_text(encoding="utf-8"))
    store = work / f"{args.strategy}.sqlite"
    lib = Path(corpus["lib"])
    queries = corpus["queries"]
    detail_priority.reset_stats()
    if args.strategy == "C":
        shutil.copy2(store, work / "C_bg.sqlite")
    cpu = time.process_time()
    loads_before = rs.patch_gallery_loads()
    cold = [_search(args.strategy, store, lib, q) for q in queries]
    cold_cov = coverage(store)
    warm = [_search(args.strategy, store, lib, q) for q in queries]
    searches = len(cold) + len(warm)
    loads = rs.patch_gallery_loads() - loads_before
    out = {
        "cold_pass": _summary(cold),
        "warm_pass": _summary(warm),
        "first_search_ms": cold[0]["final_ms"] if cold else None,
        "fifth_search_ms": cold[4]["final_ms"] if len(cold) > 4 else None,
        "per_query_cold_complete_ms": [r["final_ms"] for r in cold],
        "per_query_warm_complete_ms": [r["final_ms"] for r in warm],
        "archive_with_detail_after_queries_pct": round(
            100.0 * cold_cov.get("detailed", 0) / max(1, cold_cov.get("total", 1)), 1
        )
        if cold_cov
        else None,
        "coverage_after_cold_pass": cold_cov,
        "gallery_loads": loads,  # index reloads; a reload follows every batch of new detail
        "searches": searches,
        "detail_priority": detail_priority.stats(),
    }
    if args.strategy == "C":
        out.update(_background_stage(work / "C_bg.sqlite", lib, queries))
    out["search_cpu_s"] = round(time.process_time() - cpu, 2)
    out["peak_mb"] = peak_memory_mb()
    return out


def _background_stage(store: Path, lib: Path, queries: list[dict]) -> dict:
    """Background enrichment finishes the library while searches keep running."""
    from semblon import detail_priority
    from semblon.ingest import ingest

    before = coverage(store)
    detail_priority.reset_stats()
    state = {"done": False, "seconds": None}

    def enrich():
        started = time.perf_counter()
        ingest(lib, store, observers=_csv("region"))
        state["seconds"] = time.perf_counter() - started
        state["done"] = True

    idle = [_search("C", store, lib, q) for q in queries[:5]]
    worker = threading.Thread(target=enrich, daemon=True)
    worker.start()
    time.sleep(1.5)
    busy = []
    for query in queries:
        if state["done"]:
            break
        busy.append(_search("C", store, lib, query))
    cancel_ms = None
    if not state["done"] and queries:
        flag = {"on": False}
        thread = threading.Thread(
            target=lambda: _search("C", store, lib, queries[0], cancelled=lambda: flag["on"])
        )
        thread.start()
        time.sleep(0.3)
        flag["on"] = True
        stamp = time.perf_counter()
        thread.join(60)
        cancel_ms = round((time.perf_counter() - stamp) * 1000, 1)
    worker.join()
    after = coverage(store)
    total = max(1, before.get("total", 1))
    return {
        "background": {
            "enrichment_s": round(state["seconds"] or 0.0, 2),
            "detail_before_pct": round(100.0 * before.get("detailed", 0) / total, 1),
            "detail_after_pct": round(100.0 * after.get("detailed", 0) / max(1, after.get("total", 1)), 1),
            "photos_left_for_background": before.get("total", 0) - before.get("detailed", 0),
            "photos_already_done_by_searches": before.get("detailed", 0),
            "search_ms_idle_median": _med([r["final_ms"] for r in idle]),
            "search_ms_during_background_median": _med([r["final_ms"] for r in busy]),
            "searches_during_background": len(busy),
            "cancel_return_ms": cancel_ms,
            "duplicate_work_avoided": detail_priority.stats()["duplicates_avoided"],
        }
    }


def run_stage(stage: str, strategy: str, args) -> dict:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--stage",
        stage,
        "--strategy",
        strategy,
        "--work",
        str(args.work),
        "--queries",
        str(args.queries),
        "--seed",
        str(args.seed),
    ]
    if args.photos:
        cmd += ["--photos", str(args.photos)]
    env = {**os.environ, "PYTHONPATH": str(ROOT), "SEMBLON_PERF": "0"}
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise SystemExit(f"stage {stage}/{strategy} failed:\n{proc.stderr[-2000:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench_hybrid")
    parser.add_argument("--photos", type=Path)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--queries", type=int, default=10)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", type=Path, default=Path("bench-hybrid.json"))
    parser.add_argument("--stage", choices=["base", "prep", "search"])
    parser.add_argument("--strategy", choices=STRATEGIES)
    args = parser.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.stage:
        handler = {"base": stage_base, "prep": stage_prep, "search": stage_search}[args.stage]
        print(json.dumps(handler(args)))
        return 0
    if args.photos is None:
        parser.error("--photos is required")
    from semblon import perf_evidence

    report = {"machine": perf_evidence.machine(), "labels": LABELS, "strategies": {}}
    report["base"] = run_stage("base", "A", args)
    for strategy in STRATEGIES:
        prep = run_stage("prep", strategy, args)
        found = run_stage("search", strategy, args)
        report["strategies"][strategy] = {"label": LABELS[strategy], "prep": prep, "search": found}
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
