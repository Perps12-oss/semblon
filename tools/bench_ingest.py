"""Benchmark harness for ingest throughput. Does not retune identity.

Single --workers value only. For the workers=1,2,4 sweep (face-count equality,
images/sec, faces/sec, RSS), use tools/perf_workers_harness.py — see
docs/PERF-WORKERS-HARNESS.md.

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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bench_ingest")
    p.add_argument("--folder", type=Path, default=None)
    p.add_argument("--store", type=Path, default=None)
    p.add_argument("--out", type=Path, default=Path("bench.json"))
    p.add_argument("--workers", type=int, default=1)
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

    store = args.store or (args.out.parent / "bench-store.sqlite")
    t0 = time.perf_counter()
    out = ingest(args.folder, store, workers=args.workers)
    wall = time.perf_counter() - t0
    rec.update(
        {
            "verified": True,
            "wall_s": round(wall, 3),
            "folder": str(args.folder),
            "store": str(store),
            "run_id": out.get("run_id"),
            "files": out.get("files"),
            "faces": out.get("faces"),
            "ok": out.get("ok"),
            "ingest_s": out.get("ingest_s"),
            "images_per_second": out.get("images_per_second"),
            "provider": "facekit",
            "device": "cpu",
        }
    )
    args.out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
