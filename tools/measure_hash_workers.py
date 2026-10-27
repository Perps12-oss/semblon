"""Time hash-only workers=1/2/4 on a folder of files. Does not run inference.

    python tools/measure_hash_workers.py --folder PATH --out results.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from semblon.hash_workers_measure import measure_folder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    record = measure_folder(args.folder)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(args.out),
                "semantic_equivalent": record["semantic_equivalent"],
                "speedup_best_vs_w1": record["speedup_best_vs_w1"],
                "best_workers": record["best_workers"],
            }
        )
    )
    return 0 if record["semantic_equivalent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
