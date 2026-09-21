"""Provider / EP measurement harness. Does not claim GPU speedup.

Records what ORT lists and what Semblon would choose. FaceKit remains the
identity engine. AzureExecutionProvider is never treated as GPU.

Usage:
  python tools/perf_provider_harness.py --out results.json
      → verified=false dry record (usable in CI / Linux cloud)

  python tools/perf_provider_harness.py --out results.json --execute
      → same probe (no folder required); still not a smoke-tested GPU claim

See docs/PERF-PROVIDER-HARNESS.md. ARM64 OpenCV ingest remains BLOCKED
(docs/PERF-P1-ARM64.md) — this harness does not unblock it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_record(*, execute: bool) -> dict[str, Any]:
    from semblon.engine import format_execution_status_lines, product_prefer_gpu, select_execution_provider
    from semblon.observers import optional_status

    ep = select_execution_provider(prefer_gpu=True)
    opt = optional_status()
    return {
        "harness": "perf_provider",
        "verified": False,
        "status": "measured_listing" if execute else "dry_run",
        "note": (
            "Lists ORT providers and product EP choice only. "
            "Listed ≠ smoke-tested. Azure ≠ GPU. "
            "No ingest throughput claim. Product workers default remains 1. "
            "Native ARM64 OpenCV ingest still BLOCKED (docs/PERF-P1-ARM64.md)."
        ),
        "product_prefer_gpu": product_prefer_gpu(),
        "execution": ep,
        "optional_observers": opt,
        "status_lines": format_execution_status_lines(),
        "human_steps": [
            "On Windows with CUDA/DirectML/TensorRT: re-run --execute and record EP list.",
            "Do not claim GPU acceleration until a real ingest smoke on that EP.",
            "Do not change product workers default from 1.",
            "ARM64 OpenCV load hang remains a separate blocker (PERF-P1).",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="perf_provider_harness")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument(
        "--execute",
        action="store_true",
        help="probe ORT/providers now (still verified=false; not a GPU smoke test)",
    )
    args = p.parse_args(argv)
    rec = build_record(execute=bool(args.execute))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
