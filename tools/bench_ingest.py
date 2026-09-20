"""Benchmark harness for ingest throughput and A/B semantic contract.

Usage (after install):
  python tools/bench_ingest.py --folder PATH --store PATH --out bench.json

If --folder is omitted, writes a harness-not-run record (honest unverified).
Never claims 10k unless that folder was actually processed.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def _parse_worker_sweep(spec: str | None, *, fallback: int) -> list[int]:
    if not spec:
        return [max(1, int(fallback))]
    vals: list[int] = []
    for raw in str(spec).split(","):
        raw = raw.strip()
        if not raw:
            continue
        vals.append(int(raw))
    vals = sorted({v for v in vals if v >= 1})
    if not vals:
        return [max(1, int(fallback))]
    return vals


def _pow2_sweep(max_workers: int) -> list[int]:
    max_workers = max(1, int(max_workers))
    out = [1]
    w = 2
    while w <= max_workers:
        out.append(w)
        w *= 2
    if out[-1] != max_workers:
        out.append(max_workers)
    return sorted(set(out))


def _store_for_worker(base: Path, worker: int, multi: bool) -> Path:
    if not multi:
        return base
    suffix = base.suffix or ".sqlite"
    stem = base.name[: -len(suffix)] if base.name.endswith(suffix) else base.name
    return base.with_name(f"{stem}-w{worker}{suffix}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bench_ingest")
    p.add_argument("--folder", type=Path, default=None)
    p.add_argument("--store", type=Path, default=None)
    p.add_argument("--out", type=Path, default=Path("bench.json"))
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--sweep", default=None, help="comma list worker sweep, e.g. 1,2,4")
    p.add_argument("--max-workers", type=int, default=0, help="auto sweep powers of two up to this cap")
    p.add_argument("--embedding-tol", type=float, default=1e-6)
    p.add_argument("--score-tol", type=float, default=1e-6)
    p.add_argument("--prefer-gpu", action="store_true")
    p.add_argument("--synthetic", type=int, default=0, help="write N tiny jpeg stubs (not a 10k claim)")
    p.add_argument("--execute", action="store_true", help="actually run ingest (needs FaceKit)")
    args = p.parse_args(argv)
    rec = {
        "harness": "bench_ingest",
        "workers": args.workers,
        "verified": False,
        "note": "10k is a design target; this file is only evidence if verified=true",
    }
    if args.synthetic:
        folder = args.folder or (args.out.parent / "synth")
        folder.mkdir(parents=True, exist_ok=True)
        for i in range(int(args.synthetic)):
            (folder / f"{i:05d}.jpg").write_bytes(b"\xff\xd8\xff" + bytes([i % 256]) * 64)
        rec["synthetic"] = int(args.synthetic)
        rec["folder"] = str(folder)
        args.folder = folder
        if not args.execute:
            rec["status"] = "synthetic files written; ingest NOT EXECUTED"
            args.out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            print(json.dumps(rec, indent=2))
            return 0
    if args.folder is None:
        rec["status"] = "not executed — human/environment verification required"
        args.out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        print(json.dumps(rec, indent=2))
        return 0
    from semblon.ingest import ingest
    from semblon.perf_contract import build_semantic_snapshot, compare_semantic_snapshots

    if args.max_workers > 0:
        workers = _pow2_sweep(args.max_workers)
    else:
        workers = _parse_worker_sweep(args.sweep, fallback=args.workers)
    base_store = args.store or (args.out.parent / "bench-store.sqlite")
    results: list[dict] = []
    snapshots: list[dict] = []
    baseline_snapshot = None
    baseline_ingest_s = None

    for idx, worker in enumerate(workers):
        store = _store_for_worker(base_store, worker, multi=len(workers) > 1)
        if store.exists():
            store.unlink()
        t0 = time.perf_counter()
        out = ingest(args.folder, store, workers=worker, prefer_gpu=args.prefer_gpu)
        wall = time.perf_counter() - t0
        snap = build_semantic_snapshot(store, out["run_id"], embedding_tol=args.embedding_tol)
        if idx == 0:
            baseline_snapshot = snap
            baseline_ingest_s = float(out.get("ingest_s") or 0.0)
            contract = {"ok": True, "diffs": [], "note": "baseline"}
        else:
            contract = compare_semantic_snapshots(
                baseline_snapshot,
                snap,
                score_tol=args.score_tol,
            )
        ingest_s = float(out.get("ingest_s") or 0.0)
        eff = None
        if baseline_ingest_s and ingest_s > 0:
            eff = round(float(baseline_ingest_s) / float(ingest_s), 4)
        results.append(
            {
                "worker": int(worker),
                "store": str(store),
                "run_id": out.get("run_id"),
                "wall_s": round(wall, 3),
                "files": out.get("files"),
                "faces": out.get("faces"),
                "ok": out.get("ok"),
                "failed": out.get("failed"),
                "ingest_s": out.get("ingest_s"),
                "images_per_second": out.get("images_per_second"),
                "faces_per_second": out.get("faces_per_second"),
                "seconds_per_image": out.get("seconds_per_image"),
                "seconds_per_face": out.get("seconds_per_face"),
                "scaling_efficiency_t1_over_tw": eff,
                "execution_provider": (snap.get("runtime_evidence") or {}).get("execution_provider"),
                "runtime_workers": (snap.get("runtime_evidence") or {}).get("workers"),
                "contract": contract,
            }
        )
        snapshots.append(snap)

    sem_ok = [r for r in results if bool((r.get("contract") or {}).get("ok"))]
    if sem_ok:
        best = max(
            sem_ok,
            key=lambda r: float(r.get("images_per_second") or 0.0),
        )
        ceiling = int(best["worker"])
    else:
        ceiling = None

    rec.update(
        {
            "verified": True,
            "folder": str(args.folder),
            "stores": [r["store"] for r in results],
            "provider": "facekit",
            "device": "cpu",
            "worker_sweep": workers,
            "results": results,
            "semantic_contract_ok": all(bool((r.get("contract") or {}).get("ok")) for r in results),
            "recommended_worker_ceiling": ceiling,
            "benchmark_policy": {
                "correctness": "contract parity must pass",
                "throughput_metrics": ["images_per_second", "faces_per_second", "seconds_per_image", "seconds_per_face"],
                "scaling_metric": "T1/Tw",
                "selection_rule": "choose best throughput among semantic-pass runs",
            },
        }
    )
    args.out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
