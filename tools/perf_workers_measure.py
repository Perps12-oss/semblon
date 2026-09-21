"""CLI: measure hash-phase ingest workers=1/2/4 and write JSON.

Does not change product defaults. Evidence only — never claims workers>1
should become the product default.

Usage:
  python tools/perf_workers_measure.py --folder PATH --out report.json
  python tools/perf_workers_measure.py --out report.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="perf_workers_measure",
        description=(
            "Hash-phase only workers=1/2/4 measure harness. "
            "Product default remains workers=1; this tool never recommends flipping it."
        ),
    )
    p.add_argument(
        "--folder",
        type=Path,
        default=None,
        help="media folder to hash-measure (omit → verified=false record)",
    )
    p.add_argument(
        "--out",
        type=Path,
        required=True,
        help="JSON report path",
    )
    p.add_argument(
        "--workers",
        type=str,
        default="1,2,4",
        help="comma-separated worker counts (default: 1,2,4)",
    )
    args = p.parse_args(argv)

    workers_list = [int(x.strip()) for x in str(args.workers).split(",") if x.strip()]
    if not workers_list:
        workers_list = [1, 2, 4]

    from semblon.perf_workers_harness import measure_hash_workers

    report = measure_hash_workers(args.folder, workers_list=workers_list)
    # Hard invariants — never claim product default should change.
    report["default_product_workers"] = 1
    report["recommend_change_default"] = False
    report["recommendation"] = "keep product default workers=1"
    if "hash-phase" not in str(report.get("note", "")).lower() and "hash" not in str(
        report.get("phase", "")
    ).lower():
        report["note"] = (
            "hash-phase only; product default remains workers=1; "
            "do not change defaults from this harness alone."
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
