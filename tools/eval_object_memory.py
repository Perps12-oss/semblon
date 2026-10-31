"""Run the focused saved object-memory evaluation without overwriting Lens reports.

Manifest cases contain ranked_media_ids captured from a retrieval run, frozen
relevant/hard-negative media IDs, and explicit real-photo evidence fields.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from semblon.object_memory_eval import ObjectMemoryEvalError, evaluate_manifest

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate saved object-memory retrieval.")
    parser.add_argument("--manifest", default=str(ROOT / "docs/evidence/object-memory-eval.json"))
    parser.add_argument("--out", default=str(ROOT / "docs/evidence/object-memory-eval-report.json"))
    args = parser.parse_args(argv)
    try:
        report = evaluate_manifest(Path(args.manifest), Path(args.out))
    except ObjectMemoryEvalError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps({k: report.get(k) for k in (
        "status", "dataset_type", "case_count", "recall_at_k", "mrr",
        "hard_negative_win_rate", "real_photo_claim_allowed", "warning"
    )}, indent=2))
    if report.get("status") == "NOT_RUN":
        return 0
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
