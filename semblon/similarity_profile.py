"""Visual-similarity quality profiles.

Profiles tune latency vs recall for whole-image and region Similar.
They never touch identity comparisons.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SEARCH_QUALITY = "balanced"
SEARCH_QUALITIES = ("fast", "balanced", "max")


@dataclass(frozen=True)
class SimilarityProfile:
    key: str
    label: str
    max_results: int
    whole_probe_multiplier: int
    whole_scene_floor: float
    whole_colour_floor: float
    region_score_floor: float
    patch_token_stride: int
    patch_token_floor: float
    patch_score_floor: float
    patch_coverage_floor: float


_PROFILES: dict[str, SimilarityProfile] = {
    "fast": SimilarityProfile(
        key="fast",
        label="Fast mode",
        max_results=6,
        whole_probe_multiplier=2,
        whole_scene_floor=0.55,
        whole_colour_floor=0.88,
        region_score_floor=0.80,
        patch_token_stride=2,
        patch_token_floor=0.40,
        patch_score_floor=0.34,
        patch_coverage_floor=0.34,
    ),
    "balanced": SimilarityProfile(
        key="balanced",
        label="Balanced",
        max_results=8,
        whole_probe_multiplier=4,
        whole_scene_floor=0.50,
        whole_colour_floor=0.85,
        region_score_floor=0.76,
        patch_token_stride=1,
        patch_token_floor=0.35,
        patch_score_floor=0.28,
        patch_coverage_floor=0.28,
    ),
    "max": SimilarityProfile(
        key="max",
        label="Max power",
        max_results=12,
        whole_probe_multiplier=6,
        whole_scene_floor=0.42,
        whole_colour_floor=0.80,
        region_score_floor=0.70,
        patch_token_stride=1,
        patch_token_floor=0.30,
        patch_score_floor=0.22,
        patch_coverage_floor=0.20,
    ),
}


def normalize_search_quality(value: str | None) -> str:
    key = str(value or "").strip().lower()
    if key in SEARCH_QUALITIES:
        return key
    return DEFAULT_SEARCH_QUALITY


def resolve_search_quality(value: str | None) -> SimilarityProfile:
    return _PROFILES[normalize_search_quality(value)]


def search_quality_label(value: str | None) -> str:
    return resolve_search_quality(value).label
