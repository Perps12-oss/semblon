"""Benchmark harness for ingest throughput. Does not retune identity.

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
    args = p.parse_args(argv)
    rec = {
        "harness": "bench_ingest",
        "workers": args.workers,
        "verified": False,
        "note": "10k is a design target; this file is only evidence if verified=true",
    }
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
