"""Fuse independent ranked lists, then rescore the top candidates.

Doors are not calibrated. Reciprocal Rank Fusion is the combine.
A cheap weighted sum is the CPU rerank. Not identity.
"""

from __future__ import annotations

from semblon.query_spec import DOOR_KIND, DOOR_LOOK, DOOR_OBJECT, DOOR_TEXT, QuerySpec, parse_query_spec


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[str]],
    *,
    k: int = 60,
    weights: dict[str, float] | None = None,
) -> dict[str, float]:
    """media_id → RRF score. Higher is better."""
    fused: dict[str, float] = {}
    weight_map = {str(key): float(value) for key, value in (weights or {}).items()}
    for door, ranked in ranked_lists.items():
        weight = weight_map.get(str(door), 1.0)
        seen: set[str] = set()
        rank = 0
        for media_id in ranked:
            key = str(media_id or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            rank += 1
            fused[key] = fused.get(key, 0.0) + weight / (k + rank)
    return fused


def feature_rerank(
    items: list[dict],
    *,
    spec=None,
    limit: int = 20,
) -> list[dict]:
    """Rescore fused hits. Uses door scores already on the row.

    Door scores are not on one scale (cosine, an OCR flag, an RRF sum near
    1/60). Each feature is divided by the best value in this pool before the
    published weights are applied. The weights themselves stay fixed.
    """
    query = spec if isinstance(spec, QuerySpec) else parse_query_spec(spec)
    prepared: list[tuple[dict, dict[str, float]]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        doors = item.get("door_scores") if isinstance(item.get("door_scores"), dict) else {}
        prepared.append(
            (
                item,
                {
                    "visual": _unit(doors.get(DOOR_LOOK, item.get("visual_score"))),
                    "text": _unit(doors.get(DOOR_TEXT, item.get("text_score"))),
                    "obj": _unit(doors.get(DOOR_OBJECT, item.get("object_score"))),
                    "kind": _unit(doors.get(DOOR_KIND, item.get("kind_score"))),
                    "rrf": _unit(item.get("rrf") or item.get("score")),
                },
            )
        )
    peaks = {
        key: max((feats[key] for _item, feats in prepared), default=0.0)
        for key in ("visual", "text", "obj", "kind", "rrf")
    }
    packed = []
    for item, feats in prepared:
        visual = _pool_fraction(feats["visual"], peaks["visual"])
        text = _pool_fraction(feats["text"], peaks["text"])
        obj = _pool_fraction(feats["obj"], peaks["obj"])
        kind = _pool_fraction(feats["kind"], peaks["kind"])
        rrf = _pool_fraction(feats["rrf"], peaks["rrf"])
        score = (
            query.look_weight * visual
            + 0.22 * text
            + 0.15 * obj
            + query.kind_weight * kind
            + 0.30 * rrf
        )
        if query.modifier and feats["text"] > 0:
            score += 0.08
        row = dict(item)
        row["score"] = float(score)
        row["rrf"] = float(item.get("rrf") or 0.0)
        packed.append(row)
    packed.sort(
        key=lambda row: (
            -float(row.get("score") or 0.0),
            -len(row.get("bases") or []),
            str(row.get("media_id") or ""),
        )
    )
    return packed[: max(1, int(limit))]


def _pool_fraction(value: float, peak: float) -> float:
    """Map one door onto 0–1 inside this candidate pool. A missing door stays 0."""
    if peak <= 0:
        return 0.0
    return value / peak


def _unit(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number < 0:
        return 0.0
    if number > 1.0:
        return 1.0 / (1.0 + number) if number > 4 else min(1.0, number / 4.0)
    return number
