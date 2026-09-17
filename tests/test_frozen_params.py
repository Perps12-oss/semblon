"""FACE-005: frozen S1 identity params must not drift. No InsightFace."""

from __future__ import annotations

from semblon.cluster import DEFAULT_EPS, DEFAULT_MIN_SAMPLES, METRIC
from semblon.eval import DEFAULT_THRESHOLD, HARD_NEAR
from semblon.export import STRONG_MIN_INTRA
from semblon.engine import PACK_FAMILY
from semblon.temporal import DEFAULT_SAMPLE_HZ


def test_s1_golden_params_are_frozen():
    """docs/S1-GOLDEN.md: eps=0.40, min_samples=2, 1-dot, STRONG_MIN_INTRA=0.50."""
    assert DEFAULT_EPS == 0.40
    assert DEFAULT_MIN_SAMPLES == 2
    assert METRIC == "1-dot"
    assert STRONG_MIN_INTRA == 0.50
    assert HARD_NEAR == STRONG_MIN_INTRA
    assert DEFAULT_THRESHOLD == 0.60
    assert round(1.0 - DEFAULT_EPS, 2) == DEFAULT_THRESHOLD
    assert PACK_FAMILY == "insightface/buffalo_l"
    assert DEFAULT_SAMPLE_HZ == 1.0
