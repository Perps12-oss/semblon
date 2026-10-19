"""Fuse ranked retrieval lists. Not identity.

Independent evidence channels (dense visual, sparse text, object labels,
colour) produce their own ranked lists. Reciprocal Rank Fusion combines
those ranks. A later cheap rescore may add class, OCR overlap, and colour
distance. Missing signals are skipped, not invented.

Never writes the store. Never reads ``faces.person_id``. Never compares
face embeddings. Geometry, text, objects, and colour stay retrieval
evidence. They do not vote on identity.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

# Standard RRF constant. Rank is 1-based. Larger k dampens top-heavy lists.
RRF_K = 60

# Lightweight rerank. Tuned later on a photographic holdout, not on identity.
WEIGHT_RRF = 1.0
WEIGHT_VISUAL = 0.35
WEIGHT_TEXT = 0.45
WEIGHT_CLASS = 0.20
WEIGHT_COLOUR = 0.15


def reciprocal_rank_fusion(
    rankings: Mapping[str, Sequence[str]],
    *,
    k: int = RRF_K,
    weights: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Combine per-channel ranked media ids.

    ``rankings`` maps a channel name to media ids, best first. Duplicate ids
    inside one channel keep the first rank. Empty or unknown channels are
    ignored. The result is ``media_id -> RRF score``.
    """
    fused: dict[str, float] = {}
    damp = max(1, int(k))
    for channel, ordered in rankings.items():
        weight = 1.0
        if weights is not None and channel in weights:
            try:
                weight = float(weights[channel])
            except (TypeError, ValueError):
                weight = 1.0
        if weight <= 0:
            continue
        seen: set[str] = set()
        rank = 0
        for raw in ordered:
            media_id = str(raw or "").strip()
            if not media_id or media_id in seen:
                continue
            seen.add(media_id)
            rank += 1
            fused[media_id] = fused.get(media_id, 0.0) + weight / float(damp + rank)
    return fused


def _clip01(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return 0.0
    if number > 1:
        return 1.0
    return number


def rerank_score(
    *,
    rrf: float = 0.0,
    visual: float | None = None,
    text_overlap: float | None = None,
    class_match: float | None = None,
    colour_similarity: float | None = None,
) -> float:
    """Weighted sum of present signals. Absent signals contribute nothing."""
    total = WEIGHT_RRF * float(rrf or 0.0)
    visual_n = _clip01(visual)
    if visual_n is not None:
        total += WEIGHT_VISUAL * visual_n
    text_n = _clip01(text_overlap)
    if text_n is not None:
        total += WEIGHT_TEXT * text_n
    class_n = _clip01(class_match)
    if class_n is not None:
        total += WEIGHT_CLASS * class_n
    colour_n = _clip01(colour_similarity)
    if colour_n is not None:
        total += WEIGHT_COLOUR * colour_n
    return float(total)


def fuse_hits(
    channels: Mapping[str, Sequence[Mapping]],
    *,
    k: int = RRF_K,
    weights: Mapping[str, float] | None = None,
    text_priority: bool = False,
    limit: int = 10,
) -> list[dict]:
    """Turn per-channel hit rows into one ranked list.

    Each channel sequence is already best-first. A hit must carry
    ``media_id``. Optional per-hit fields used when present:

    - ``score`` visual or detector score
    - ``text_overlap``
    - ``class_match``
    - ``colour_similarity``
    - ``match_norm``
    - ``basis`` / ``similarity_basis``

    Face identity is not a channel. Rows with ``modality='face'`` are dropped.
    """
    rankings: dict[str, list[str]] = {}
    packed: dict[str, dict] = {}
    for channel, rows in channels.items():
        order: list[str] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            if str(row.get("modality") or "") == "face":
                continue
            media_id = str(row.get("media_id") or "").strip()
            if not media_id:
                continue
            order.append(media_id)
            item = packed.setdefault(
                media_id,
                {
                    "media_id": media_id,
                    "score": 0.0,
                    "bases": [],
                    "match_norm": [0.0, 0.0, 0.0, 0.0],
                    "visual": None,
                    "text_overlap": None,
                    "class_match": None,
                    "colour_similarity": None,
                },
            )
            basis = str(row.get("basis") or row.get("similarity_basis") or channel).strip()
            if basis and basis not in item["bases"]:
                item["bases"].append(basis)
            raw_score = row.get("score")
            try:
                score = float(raw_score) if raw_score is not None else None
            except (TypeError, ValueError):
                score = None
            if score is not None and score > float(item["score"]):
                item["score"] = score
            norm = row.get("match_norm")
            if isinstance(norm, (list, tuple)) and len(norm) == 4:
                if not any(float(v) > 0 for v in item["match_norm"]):
                    item["match_norm"] = [float(v) for v in norm]
            for key in ("visual", "text_overlap", "class_match", "colour_similarity"):
                if item[key] is None and row.get(key) is not None:
                    item[key] = row.get(key)
            # Do not copy the region channel score into `visual`. That score
            # already ordered the dense list; folding it again undoes RRF.
        rankings[channel] = order
    channel_weights = dict(weights or {})
    if text_priority and "text" not in channel_weights:
        channel_weights["text"] = 1.5
    fused = reciprocal_rank_fusion(rankings, k=k, weights=channel_weights or None)
    ranked: list[dict] = []
    for media_id, rrf in fused.items():
        item = packed[media_id]
        combined = rerank_score(
            rrf=rrf,
            visual=item.get("visual"),
            text_overlap=item.get("text_overlap"),
            class_match=item.get("class_match"),
            colour_similarity=item.get("colour_similarity"),
        )
        ranked.append(
            {
                "media_id": media_id,
                "score": float(item["score"]),
                "rrf": float(rrf),
                "rerank": float(combined),
                "bases": list(item["bases"]),
                "match_norm": list(item["match_norm"]),
                "why": "multi-channel RRF; not a person",
            }
        )
    ranked.sort(
        key=lambda row: (-float(row["rerank"]), -float(row["rrf"]), str(row["media_id"]))
    )
    return ranked[: max(1, int(limit))]


def channel_media_ids(rows: Iterable[Mapping] | None) -> list[str]:
    """Best-first unique media ids from one channel. Drops face rows."""
    seen: set[str] = set()
    ordered: list[str] = []
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("modality") or "") == "face":
            continue
        media_id = str(row.get("media_id") or "").strip()
        if not media_id or media_id in seen:
            continue
        seen.add(media_id)
        ordered.append(media_id)
    return ordered
