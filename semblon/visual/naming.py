"""Propose, bind, abstain. A hint list is not the universe."""

from __future__ import annotations

import re

from semblon.visual.model import HINTS, MATERIALS, VisualConfig, VisualRegion

_PROPER = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$")


def split_proposals(nouns: list[str]) -> tuple[list[str], list[str]]:
    """Concepts vs proper-name proposals. Proper names never become labels."""
    concepts: list[str] = []
    proper: list[str] = []
    for raw in nouns:
        text = (raw or "").strip()
        if not text:
            continue
        if _PROPER.match(text) and text.lower() not in HINTS:
            proper.append(text)
            continue
        concepts.append(text.lower())
    return concepts, proper


def bind_label(
    region: VisualRegion,
    nouns: list[str],
    score_fn,
    *,
    parent: VisualRegion | None,
    config: VisualConfig,
) -> None:
    """score_fn(region_id, noun) -> float in 0..1. Abstain leaves label None."""
    concepts, proper = split_proposals(nouns)
    region.proper_name_proposals = proper
    if not concepts or score_fn is None:
        region.label = None
        region.confidence = None
        region.fate = "abstained" if region.fate.startswith("hover") or region.fate == "sliced" else region.fate
        return
    scored = []
    for noun in concepts:
        scored.append((noun, _invoke_score(score_fn, region, noun, parent)))
    scored.sort(key=lambda t: t[1], reverse=True)
    region.label_candidates = scored[:5]
    best, best_s = scored[0]
    second = scored[1][1] if len(scored) > 1 else 0.0
    if parent is not None and best in MATERIALS and parent.label and parent.label not in MATERIALS:
        region.label = None
        region.confidence = best_s
        region.fate = "abstained_material"
        return
    if best_s < config.name_abs or (best_s - second) < config.name_margin:
        region.label = None
        region.confidence = best_s
        region.fate = "abstained"
        return
    region.label = best
    region.confidence = best_s
    region.level = max(region.level, 3)
    region.fate = "named"


def _invoke_score(score_fn, region: VisualRegion, noun: str, parent: VisualRegion | None) -> float:
    """Prefer (region, noun, parent). Fall back to (region_id, noun)."""
    try:
        return float(score_fn(region, noun, parent))
    except TypeError:
        return float(score_fn(region.region_id, noun))
