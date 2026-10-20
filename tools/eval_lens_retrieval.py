"""Lens retrieval eval. Ranks on synthetic. Precision needs --eval-set confirmatory.

Builds the labelled highlight / relevant / hard-negative tuples and scores
them through production retrieve_selection. Writes
docs/evidence/lens-retrieval-eval.json.

    python tools/eval_lens_retrieval.py --eval-set synthetic
    python tools/eval_lens_retrieval.py --eval-set confirmatory
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from semblon.lens_eval import (
    EVAL_SET_CONFIRMATORY,
    EVAL_SET_SYNTHETIC,
    LensEvalError,
    normalize_eval_set,
    run_eval,
)

OUT = ROOT / "docs" / "evidence" / "lens-retrieval-eval.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score labelled Lens retrieval tuples.")
    parser.add_argument(
        "--eval-set",
        default=EVAL_SET_SYNTHETIC,
        help="synthetic reports ranks only; confirmatory is required for precision",
    )
    parser.add_argument(
        "--out",
        default=str(OUT),
        help="JSON report path",
    )
    parser.add_argument(
        "--work",
        default=str(ROOT / "docs" / "evidence" / "lens-retrieval-work"),
        help="folder for the synthetic archive",
    )
    args = parser.parse_args(argv)
    try:
        kind = normalize_eval_set(args.eval_set)
        report = run_eval(Path(args.work), eval_set=kind, out=Path(args.out))
    except LensEvalError as exc:
        print(f"ERROR {exc}")
        return 2
    print(json.dumps({k: report.get(k) for k in ("status", "eval_set", "precision", "precision_reason", "failures", "counts")}, indent=2))
    for row in report.get("cases") or []:
        mark = "PASS" if row.get("pass") else "FAIL"
        print(
            f"{row.get('case_id')}: relevant={row.get('relevant_ranks')} "
            f"hard={row.get('hard_neg_ranks')} {mark}"
        )
    if kind == EVAL_SET_CONFIRMATORY:
        print(report.get("precision_reason") or "precision refused")
        return 1
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
