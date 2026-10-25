"""Small-object recall for the three hybrid-discovery strategies.

Same preparation and search calls as tools/bench_hybrid.py:
  A  exhaustive region index, then search
  B  no region index; on-demand promotion, then search
  C  whole-picture (region-lite) index, search, then detail promotion and one rescore

The production grid and the production batch of 8 are not changed. Batch 0/1/4
is a separate exploratory pass on the development split only.

The report has timings, counts, query ids and labels. No filesystem paths, no pixels.

  python tools/bench_small_object.py --work DIR --out report.json --reps 3
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from bench_hybrid import _clean, _csv, _med, coverage, media_ids, peak_memory_mb  # noqa: E402
from small_object_corpus import SEED, checksum, generate  # noqa: E402

STRATEGIES = ("A", "B", "C")
LABELS = {
    "A": "Exhaustive (15-piece index up front)",
    "B": "On demand (nothing prepared)",
    "C": "Hybrid (whole picture, detail batch 8 during search)",
}


def recall_precision(ranked: list[str], relevant: list[str], k: int) -> dict:
    """Set recall and precision. Slots past the end of a short list are misses."""
    rel = list(dict.fromkeys(relevant))
    top = list(ranked)[:k]
    hits = [photo for photo in top if photo in set(rel)]
    return {
        "hits": len(hits),
        "recall": (len(hits) / len(rel)) if rel else None,
        "precision": (len(hits) / k) if k else None,
        "any": bool(hits),
    }


def _machine() -> dict:
    cpu = ""
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        cpu = platform.processor()
    mem_mb = None
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                mem_mb = round(int(line.split()[1]) / 1024, 1)
                break
    except OSError:
        mem_mb = None
    return {
        "os": platform.platform(),
        "machine": platform.machine(),
        "processor": cpu,
        "logical_cpus_visible": os.cpu_count(),
        "mem_total_mb": mem_mb,
        "python": sys.version.split()[0],
        "native_x64": platform.machine().lower() in {"x86_64", "amd64"},
        "emulated": False,
        "note": "Visible CPUs are the sandbox limit. Not a Windows or ARM64 measurement.",
    }


def _versions() -> dict:
    import cv2
    import onnxruntime as ort

    from semblon.region_encoder import probe_region_pack, region_pack_dir

    ready, note = probe_region_pack()
    pin_path = region_pack_dir() / "semblon-region-pack-pin.json"
    pin = json.loads(pin_path.read_text(encoding="utf-8")) if pin_path.is_file() else {}
    return {
        "region_pack_ready": bool(ready),
        "region_pack_note": note,
        "region_model": pin.get("model"),
        "region_sha256": pin.get("sha256"),
        "region_license": pin.get("license"),
        "opencv": cv2.__version__,
        "onnxruntime": ort.__version__,
        "onnx_providers": list(ort.get_available_providers()),
        "search_quality": "balanced",
        "balanced_max_results": 8,
        "detail_promote_max": 8,
        "detail_budget_s": 12.0,
        "grid": "1 frame + 8 windows + up to 6 proposals",
    }


def _manifest(work: Path) -> dict:
    return json.loads((work / "manifest.json").read_text(encoding="utf-8"))


def _id_maps(work: Path) -> tuple[dict[str, str], dict[str, str]]:
    names = media_ids(work / "base.sqlite")
    photo_to_media = {}
    media_to_photo = {}
    for photo in _manifest(work)["photos"]:
        media = names.get(photo["file"])
        if not media:
            raise RuntimeError(f"no media id for {photo['photo_id']}")
        photo_to_media[photo["photo_id"]] = media
        media_to_photo[media] = photo["photo_id"]
    return photo_to_media, media_to_photo


def _ranked(result: dict, media_to_photo: dict[str, str]) -> list[dict]:
    rows = []
    for item in result.get("items") or []:
        media = str(item.get("media_id") or "")
        rows.append(
            {
                "photo_id": media_to_photo.get(media, ""),
                "score": None if item.get("score") is None else round(float(item["score"]), 4),
            }
        )
    return rows


def _distractor_ahead(ranked: list[str], relevant: list[str], distractors: list[str]) -> bool:
    rel = set(relevant)
    dist = set(distractors)
    first_rel = next((index for index, photo in enumerate(ranked) if photo in rel), None)
    first_dist = next((index for index, photo in enumerate(ranked) if photo in dist), None)
    if first_dist is None:
        return False
    if first_rel is None:
        return True
    return first_dist < first_rel


def _query_row(query: dict, first: list[dict], final: list[dict], timing: dict) -> dict:
    relevant = query["relevant_photo_ids"]
    first_ids = [item["photo_id"] for item in first]
    final_ids = [item["photo_id"] for item in final]
    distractors = list(query["category_distractor_photo_ids"]) + list(query["visual_distractor_photo_ids"])
    metrics = {f"at_{k}": recall_precision(final_ids, relevant, k) for k in (1, 5, 10)}
    before = {f"at_{k}": recall_precision(first_ids, relevant, k) for k in (1, 5, 10)}
    useful = None
    if before["at_10"]["any"]:
        useful = timing["first_ms"]
    elif metrics["at_10"]["any"]:
        useful = timing["final_ms"]
    top_before = [photo for photo in first_ids if photo in relevant]
    top_after = [photo for photo in final_ids if photo in relevant]
    return {
        "query_id": query["query_id"],
        "photo_id": query["photo_id"],
        "instance_id": query["instance_id"],
        "category": query["category"],
        "size_band": query["size_band"],
        "variant": query["variant"],
        "split": query["split"],
        "difficulties": list(query["difficulties"]),
        "relevant": len(relevant),
        "before": before,
        "after": metrics,
        "first_useful_ms": useful,
        "first_ms": timing["first_ms"],
        "final_ms": timing["final_ms"],
        "first_five_ms": timing["first_ms"] if len(first_ids) >= 5 else (timing["final_ms"] if len(final_ids) >= 5 else None),
        "promoted": timing["promoted"],
        "rank_passes": timing["rank_passes"],
        "rank_ms": timing["rank_ms"],
        "phases_ms": timing["phases_ms"],
        "status": timing["status"],
        "returned": len(final_ids),
        "ranked": final_ids,
        "scores": [item["score"] for item in final],
        "new_in_top5": sorted(set(top_after[:5]) - set(top_before[:5])),
        "rank_changed": top_before != top_after,
        "distractor_ahead": _distractor_ahead(final_ids, relevant, distractors),
        "engine": timing.get("engine"),
        "shortlist": timing.get("shortlist"),
    }



def _search_one(strategy: str, store: Path, query: dict, photo_to_media, media_to_photo, batch: int | None) -> dict:
    """Same calls as bench_hybrid._search, with many relevant pictures and limit 10.

    Balanced still caps the list at 8. Recall@10 therefore counts anything past
    that cap as missed. Batch 0 skips promotion. Any other batch overrides the
    production cap for this process only.
    """
    from semblon import region_search as rs
    from semblon.similarity_profile import resolve_search_quality

    if batch is not None and batch > 0:
        rs.DETAIL_PROMOTE_MAX = int(batch)
    quality = resolve_search_quality("balanced")
    x, y, w, h = (int(v) for v in query["bbox"])
    photo = query["photo_id"]
    work = store.parent
    image = work / "lib" / f"{photo}.png"
    call = dict(
        image_path=image,
        x=x,
        y=y,
        w=w,
        h=h,
        limit=10,
        media_id=photo_to_media[photo],
        search_quality="balanced",
    )
    rank_ms: list[float] = []

    def run_search(shortlist_out=None):
        started = time.perf_counter()
        found = rs.find_similar_region(store, shortlist_out=shortlist_out, **call)
        rank_ms.append((time.perf_counter() - started) * 1000.0)
        return found

    started = time.perf_counter()
    promoted = 0
    phases: dict = {}
    skip_promote = batch == 0
    shortlist_n = None
    if strategy == "B" and not skip_promote:
        crop = rs.crop_bgr(image, x, y, w, h)
        summary = rs.promote_for_search(
            store,
            [],
            crop=crop,
            media_id=photo_to_media[photo],
            quality=quality,
        )
        promoted = int(summary.get("done") or 0)
        phases = dict(summary.get("phases_ms") or {})
        result = run_search()
        first_wall = time.perf_counter() - started
        first = _ranked(result, media_to_photo)
        final = first
    elif strategy == "C" and not skip_promote:
        shortlist: list[str] = []
        result = run_search(shortlist)
        shortlist_n = len(shortlist)
        first_wall = time.perf_counter() - started
        first = _ranked(result, media_to_photo)
        crop = rs.crop_bgr(image, x, y, w, h)
        sharper = rs._refine_with_detail(
            store,
            shortlist,
            crop=crop,
            media_id=photo_to_media[photo],
            quality=quality,
            cancelled=None,
            rerun=lambda: run_search(),
        )
        if sharper is not None:
            result = sharper
            promoted = int(sharper.get("detail_promoted") or 0)
            phases = dict(sharper.get("detail_phases_ms") or {})
        final = _ranked(result, media_to_photo)
    else:
        result = run_search()
        first_wall = time.perf_counter() - started
        first = _ranked(result, media_to_photo)
        final = first
    timing = {
        "first_ms": round(first_wall * 1000.0, 1),
        "final_ms": round((time.perf_counter() - started) * 1000.0, 1),
        "promoted": promoted,
        "rank_passes": len(rank_ms),
        "rank_ms": [round(value, 1) for value in rank_ms],
        "phases_ms": {key: round(float(value), 1) for key, value in phases.items()},
        "status": result.get("status"),
        "engine": result.get("engine"),
        "shortlist": shortlist_n,
    }
    return _query_row(query, first, final, timing)
def _mean_phases(rows: list[dict]) -> dict:
    totals: dict[str, float] = {}
    for row in rows:
        for key, value in (row.get("phases_ms") or {}).items():
            totals[key] = round(totals.get(key, 0.0) + float(value), 1)
    return totals


def _summarize(rows: list[dict]) -> dict:
    def metric(k: int, when: str) -> dict:
        recalls = [row[when][f"at_{k}"]["recall"] for row in rows]
        precisions = [row[when][f"at_{k}"]["precision"] for row in rows]
        anys = [1.0 if row[when][f"at_{k}"]["any"] else 0.0 for row in rows]
        return {
            "recall_mean": round(sum(recalls) / len(recalls), 3) if recalls else None,
            "precision_mean": round(sum(precisions) / len(precisions), 3) if precisions else None,
            "any_hit_rate": round(sum(anys) / len(anys), 3) if anys else None,
        }

    useful = [row["first_useful_ms"] for row in rows if row["first_useful_ms"] is not None]
    return {
        "queries": len(rows),
        "before_detail": {str(k): metric(k, "before") for k in (1, 5, 10)},
        "after_detail": {str(k): metric(k, "after") for k in (1, 5, 10)},
        "first_ms_median": _med([row["first_ms"] for row in rows]),
        "first_ms_min": min((row["first_ms"] for row in rows), default=None),
        "first_ms_max": max((row["first_ms"] for row in rows), default=None),
        "complete_ms_median": _med([row["final_ms"] for row in rows]),
        "complete_ms_min": min((row["final_ms"] for row in rows), default=None),
        "complete_ms_max": max((row["final_ms"] for row in rows), default=None),
        "first_useful_ms_median": _med(useful),
        "queries_with_a_useful_result": len(useful),
        "promoted_photos": sum(row["promoted"] for row in rows),
        "rank_passes": sum(row["rank_passes"] for row in rows),
        "rank_ms_sum": round(sum(sum(row["rank_ms"]) for row in rows), 1),
        "phases_ms_sum": _mean_phases(rows),
        "new_top5_queries": sum(1 for row in rows if row["new_in_top5"]),
        "rank_changed_queries": sum(1 for row in rows if row["rank_changed"]),
        "distractor_ahead": sum(1 for row in rows if row["distractor_ahead"]),
    }


def _by_label(rows: list[dict], key: str) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    if key == "difficulty":
        for row in rows:
            for label in row["difficulties"] or ["none"]:
                grouped[label].append(row)
    else:
        for row in rows:
            grouped[str(row[key])].append(row)
    return {name: _summarize(group) for name, group in sorted(grouped.items())}


def stage_generate(work: Path) -> dict:
    manifest = generate(work, seed=SEED)
    return {
        "photos": manifest["counts"]["photos"],
        "queries": manifest["counts"]["queries"],
        "checksum": checksum(manifest),
        "seed": SEED,
    }


def stage_base(work: Path) -> dict:
    from semblon.ingest import ingest

    store = work / "base.sqlite"
    _clean(store)
    started = time.perf_counter()
    cpu = time.process_time()
    ingest(work / "lib", store, observers=_csv())
    return {
        "prep_s": round(time.perf_counter() - started, 2),
        "prep_cpu_s": round(time.process_time() - cpu, 2),
        "peak_mb": peak_memory_mb(),
        "coverage": coverage(store),
        "photos_indexed": len(media_ids(store)),
    }


def stage_prep(work: Path, strategy: str, rep: int) -> dict:
    from semblon.ingest import ingest

    store = work / f"{strategy}-r{rep}.sqlite"
    _clean(store)
    shutil.copy2(work / "base.sqlite", store)
    started = time.perf_counter()
    cpu = time.process_time()
    if strategy == "A":
        ingest(work / "lib", store, observers=_csv("region"))
    elif strategy == "C":
        ingest(work / "lib", store, observers=_csv("region-lite"))
    return {
        "prep_s": round(time.perf_counter() - started, 2),
        "prep_cpu_s": round(time.process_time() - cpu, 2),
        "peak_mb": peak_memory_mb(),
        "coverage": coverage(store),
        "embeddings": _embedding_counts(store),
    }


def _embedding_counts(store: Path) -> dict:
    from semblon.store import connect

    if not store.is_file():
        return {}
    conn = connect(store)
    try:
        rows = conn.execute("SELECT modality, COUNT(*) FROM embeddings GROUP BY modality").fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    return {str(row[0]): int(row[1]) for row in rows}


def _run_queries(work: Path, strategy: str, rep: int, queries: list[dict], batch: int | None) -> list[dict]:
    store = work / f"{strategy}-r{rep}.sqlite"
    photo_to_media, media_to_photo = _id_maps(work)
    return [_search_one(strategy, store, query, photo_to_media, media_to_photo, batch) for query in queries]


def stage_search(work: Path, strategy: str, rep: int, batch: int | None, split: str | None) -> dict:
    from semblon import detail_priority

    manifest = _manifest(work)
    queries = list(manifest["queries"])
    if split in {"dev", "heldout"}:
        queries = [query for query in queries if query["split"] == split]
    detail_priority.reset_stats()
    cpu = time.process_time()
    cold = _run_queries(work, strategy, rep, queries, batch)
    warm = _run_queries(work, strategy, rep, queries, batch)
    return {
        "cold": _summarize(cold),
        "warm": _summarize(warm),
        "cold_rows": cold,
        "warm_rows": warm,
        "by_band": _by_label(cold, "size_band"),
        "by_variant": _by_label(cold, "variant"),
        "by_difficulty": _by_label(cold, "difficulty"),
        "by_split": _by_label(cold, "split"),
        "coverage": coverage(work / f"{strategy}-r{rep}.sqlite"),
        "detail_priority": detail_priority.stats(),
        "search_cpu_s": round(time.process_time() - cpu, 2),
        "peak_mb": peak_memory_mb(),
        "batch": batch,
    }


def stage_background(work: Path) -> dict:
    """Rebuild a lite index, finish every photo's detail, then search with promotion off."""
    from semblon.ingest import ingest

    store = work / "C-enriched.sqlite"
    _clean(store)
    shutil.copy2(work / "base.sqlite", store)
    ingest(work / "lib", store, observers=_csv("region-lite"))
    before = coverage(store)
    started = time.perf_counter()
    ingest(work / "lib", store, observers=_csv("region"))
    enrich_s = round(time.perf_counter() - started, 2)
    after = coverage(store)
    photo_to_media, media_to_photo = _id_maps(work)
    found = [
        _search_one("A", store, query, photo_to_media, media_to_photo, batch=0)
        for query in _manifest(work)["queries"]
    ]
    return {
        "enrichment_s": enrich_s,
        "coverage_before": before,
        "coverage_after": after,
        "search_after_enrichment": _summarize(found),
        "by_band": _by_label(found, "size_band"),
        "rows": found,
        "peak_mb": peak_memory_mb(),
    }


def stage_cancel(work: Path) -> dict:
    from semblon import region_search as rs
    from semblon.similarity_profile import resolve_search_quality

    source = work / "C-r0.sqlite"
    store = work / "C-cancel.sqlite"
    _clean(store)
    shutil.copy2(source, store)
    manifest = _manifest(work)
    query = manifest["queries"][0]
    photo_to_media, _media_to_photo = _id_maps(work)
    image = work / "lib" / f"{query['photo_id']}.png"
    x, y, w, h = (int(v) for v in query["bbox"])
    flag = {"on": True}
    started = time.perf_counter()
    result = rs.find_similar_region(
        store,
        image_path=image,
        x=x,
        y=y,
        w=w,
        h=h,
        limit=10,
        media_id=photo_to_media[query["photo_id"]],
        search_quality="balanced",
        cancelled=lambda: flag["on"],
    )
    quick = round((time.perf_counter() - started) * 1000.0, 1)
    flag["on"] = False
    again = rs.find_similar_region(
        store,
        image_path=image,
        x=x,
        y=y,
        w=w,
        h=h,
        limit=10,
        media_id=photo_to_media[query["photo_id"]],
        search_quality="balanced",
    )
    quality = resolve_search_quality("balanced")
    crop = rs.crop_bgr(image, x, y, w, h)
    held = {"on": False}

    def blocked():
        rs._refine_with_detail(
            store,
            [next(iter(photo_to_media.values()))],
            crop=crop,
            media_id=photo_to_media[query["photo_id"]],
            quality=quality,
            cancelled=lambda: held["on"],
            rerun=lambda: None,
        )

    thread = threading.Thread(target=blocked)
    thread.start()
    time.sleep(0.05)
    held["on"] = True
    stamp = time.perf_counter()
    thread.join(30)
    return {
        "immediate_cancel_ms": quick,
        "immediate_status": result.get("status"),
        "followup_status": again.get("status"),
        "followup_returned": len(again.get("items") or []),
        "cancel_during_promote_return_ms": round((time.perf_counter() - stamp) * 1000.0, 1),
        "note": "session.run is not interrupted. A flag only stops the next photo.",
    }


def _spawn(work: Path, stage: str, extra: list[str]) -> dict:
    cmd = [sys.executable, str(Path(__file__).resolve()), "--stage", stage, "--work", str(work), *extra]
    env = {**os.environ, "PYTHONPATH": str(ROOT), "SEMBLON_PERF": "0", "QT_QPA_PLATFORM": "offscreen"}
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise SystemExit(f"{stage} {' '.join(extra)} failed:\n{proc.stderr[-2500:]}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _spread(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median": None, "min": None, "max": None}
    return {"n": len(values), "median": _med(values), "min": min(values), "max": max(values)}


def _failures(rows: list[dict]) -> list[dict]:
    picked = []
    for row in rows:
        recall = row["after"]["at_5"]["recall"]
        before = row["before"]["at_5"]["recall"]
        if recall >= 1 and before >= recall and not row["distractor_ahead"] and row["after"]["at_5"]["any"]:
            continue
        picked.append(
            {
                "query_id": row["query_id"],
                "size_band": row["size_band"],
                "variant": row["variant"],
                "difficulties": row["difficulties"],
                "relevant": row["relevant"],
                "recall_at_5_before": before,
                "recall_at_5_after": recall,
                "any_at_5_after": row["after"]["at_5"]["any"],
                "recall_at_1_after": row["after"]["at_1"]["recall"],
                "new_in_top5": row["new_in_top5"],
                "distractor_ahead": row["distractor_ahead"],
                "ranked": row["ranked"],
                "status": row["status"],
                "engine": row["engine"],
            }
        )
    return picked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench_small_object")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--stage", choices=["generate", "base", "prep", "search", "background", "cancel"])
    parser.add_argument("--strategy", choices=STRATEGIES)
    parser.add_argument("--rep", type=int, default=0)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--split", choices=["dev", "heldout", "all"], default="all")
    args = parser.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    if args.stage:
        if args.stage == "generate":
            payload = stage_generate(args.work)
        elif args.stage == "base":
            payload = stage_base(args.work)
        elif args.stage == "prep":
            payload = stage_prep(args.work, args.strategy, args.rep)
        elif args.stage == "search":
            split = None if args.split == "all" else args.split
            payload = stage_search(args.work, args.strategy, args.rep, args.batch, split)
        elif args.stage == "background":
            payload = stage_background(args.work)
        else:
            payload = stage_cancel(args.work)
        print(json.dumps(payload))
        return 0

    versions = _versions()
    if not versions["region_pack_ready"]:
        raise SystemExit(f"region pack is not ready: {versions['region_pack_note']}")
    print("generating corpus", file=sys.stderr)
    generated = stage_generate(args.work)
    print("base ingest", file=sys.stderr)
    base = _spawn(args.work, "base", [])
    report = {
        "corpus": generated,
        "seed": SEED,
        "machine": _machine(),
        "versions": versions,
        "labels": LABELS,
        "base": base,
        "reps": args.reps,
        "strategies": {},
        "what_this_is_not": [
            "not the Kodak quarter-crop bench",
            "not Windows",
            "not native ARM64",
            "not an owner archive",
            "not a natural-object dataset",
        ],
    }
    for strategy in STRATEGIES:
        runs = []
        for rep in range(args.reps):
            print(f"prep {strategy} rep {rep}", file=sys.stderr)
            prep = _spawn(args.work, "prep", ["--strategy", strategy, "--rep", str(rep)])
            print(f"search {strategy} rep {rep}", file=sys.stderr)
            found = _spawn(args.work, "search", ["--strategy", strategy, "--rep", str(rep)])
            runs.append({"prep": prep, "search": found})
        report["strategies"][strategy] = {"label": LABELS[strategy], "runs": runs}
    print("background enrichment", file=sys.stderr)
    report["background"] = _spawn(args.work, "background", [])
    print("cancel probe", file=sys.stderr)
    report["cancel"] = _spawn(args.work, "cancel", [])
    report["batch_exploratory_dev_split"] = {}
    for batch in (0, 1, 4, 8):
        print(f"batch {batch} dev", file=sys.stderr)
        prep = _spawn(args.work, "prep", ["--strategy", "C", "--rep", str(100 + batch)])
        found = _spawn(
            args.work,
            "search",
            ["--strategy", "C", "--rep", str(100 + batch), "--batch", str(batch), "--split", "dev"],
        )
        report["batch_exploratory_dev_split"][str(batch)] = {
            "prep_coverage": prep.get("coverage"),
            "cold": found["cold"],
            "by_band": found["by_band"],
            "rows": found["cold_rows"],
        }
    report["failures_hybrid_rep0"] = _failures(report["strategies"]["C"]["runs"][0]["search"]["cold_rows"])
    report["failures_exhaustive_rep0"] = _failures(report["strategies"]["A"]["runs"][0]["search"]["cold_rows"])
    report["timing_spread"] = {}
    for strategy in STRATEGIES:
        runs = report["strategies"][strategy]["runs"]
        report["timing_spread"][strategy] = {
            "prep_s": _spread([run["prep"]["prep_s"] for run in runs]),
            "cold_complete_ms_median": _spread([run["search"]["cold"]["complete_ms_median"] for run in runs]),
            "warm_complete_ms_median": _spread([run["search"]["warm"]["complete_ms_median"] for run in runs]),
            "cold_recall_at_5": [run["search"]["cold"]["after_detail"]["5"]["recall_mean"] for run in runs],
            "cold_recall_at_5_before": [run["search"]["cold"]["before_detail"]["5"]["recall_mean"] for run in runs],
        }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"out": str(args.out) if args.out else None, "queries": generated["queries"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
