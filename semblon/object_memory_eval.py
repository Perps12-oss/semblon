"""Focused evaluation metrics for saved object-memory retrieval.

This complements Lens evaluation; it does not replace or tune the Lens ranker.
A real-photo claim requires a manifest explicitly marked real_photo with image
references and frozen relevance/hard-negative judgments.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ObjectMemoryEvalError(ValueError):
    pass


def reciprocal_rank(relevant: set[str], ranked: list[str]) -> float:
    for rank, media_id in enumerate(ranked, 1):
        if media_id in relevant:
            return 1.0 / rank
    return 0.0


def evaluate_cases(cases: list[dict[str, Any]], *, ks=(1, 5, 10)) -> dict:
    if not cases:
        return {
            "status": "NOT_RUN",
            "evaluation": "object-memory",
            "case_count": 0,
            "dataset_type": "empty_manifest",
            "recall_at_k": {str(k): None for k in ks},
            "mrr": None,
            "hard_negative_win_rate": None,
            "real_photo_claim_allowed": False,
            "warning": "Manifest has no cases. Not a recognition baseline.",
            "cases": [],
        }
    recalls = {int(k): [] for k in ks}
    reciprocal_ranks: list[float] = []
    hard_negative_wins: list[bool] = []
    evaluated = 0
    for case in cases:
        relevant = {str(v) for v in case.get("relevant_media_ids", []) if str(v)}
        hard = {str(v) for v in case.get("hard_negative_media_ids", []) if str(v)}
        ranked = [str(v) for v in case.get("ranked_media_ids", []) if str(v)]
        if not relevant:
            raise ObjectMemoryEvalError(f"{case.get('case_id', '<unknown>')}: no relevant media IDs")
        evaluated += 1
        reciprocal_ranks.append(reciprocal_rank(relevant, ranked))
        for k in recalls:
            recalls[k].append(float(any(mid in relevant for mid in ranked[:k])))
        if hard:
            best_relevant = min((i for i, mid in enumerate(ranked, 1) if mid in relevant), default=None)
            best_hard = min((i for i, mid in enumerate(ranked, 1) if mid in hard), default=None)
            hard_negative_wins.append(best_relevant is not None and (best_hard is None or best_relevant < best_hard))
    real_photo = all(bool(case.get("real_photo")) for case in cases)
    return {
        "status": "SCORED",
        "evaluation": "object-memory",
        "case_count": evaluated,
        "dataset_type": "real_photo" if real_photo else "synthetic_or_unverified",
        "recall_at_k": {str(k): round(sum(vals) / len(vals), 6) for k, vals in recalls.items()},
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 6),
        "hard_negative_win_rate": (
            round(sum(hard_negative_wins) / len(hard_negative_wins), 6)
            if hard_negative_wins else None
        ),
        "real_photo_claim_allowed": real_photo and all(
            bool(case.get("query_image")) and bool(case.get("candidate_images"))
            for case in cases
        ),
        "warning": None if real_photo else "Synthetic/unverified cases do not prove cross-photo recognition.",
        "cases": cases,
    }


def evaluate_manifest(path: Path, out: Path | None = None) -> dict:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ObjectMemoryEvalError(f"cannot read manifest: {exc}") from exc
    cases = manifest.get("cases") if isinstance(manifest, dict) else None
    if not isinstance(cases, list):
        raise ObjectMemoryEvalError("manifest must contain a cases array")
    report = evaluate_cases(cases)
    report["manifest"] = str(path)
    if out is not None:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
