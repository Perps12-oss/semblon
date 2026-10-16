"""Active YuNet+SFace config + frozen buffalo_l historical constants."""

from __future__ import annotations

from semblon import identity_buffalo_frozen as buffalo
from semblon import identity_config as active
from semblon.cluster import DEFAULT_EPS, DEFAULT_MIN_SAMPLES, METRIC
from semblon.eval import DEFAULT_THRESHOLD, HARD_NEAR
from semblon.export import STRONG_MIN_INTRA
from semblon.engine import PACK_FAMILY
from semblon.temporal import DEFAULT_SAMPLE_HZ


def test_active_engine_is_yunet_sface():
    assert PACK_FAMILY == "opencv/yunet_sface"
    assert active.PACK_FAMILY == PACK_FAMILY
    assert active.EXPECTED_FACE_DIM == 128
    assert DEFAULT_EPS == active.DEFAULT_EPS
    assert DEFAULT_MIN_SAMPLES == active.DEFAULT_MIN_SAMPLES
    assert METRIC == "1-dot"
    assert STRONG_MIN_INTRA == active.STRONG_MIN_INTRA
    assert HARD_NEAR == STRONG_MIN_INTRA
    assert DEFAULT_THRESHOLD == round(1.0 - DEFAULT_EPS, 2)
    assert DEFAULT_SAMPLE_HZ == 1.0


def test_buffalo_l_s1_constants_remain_frozen_for_history():
    """docs/S1-GOLDEN.md — historical only; must not drive the active engine."""
    assert buffalo.PACK_FAMILY == "insightface/buffalo_l"
    assert buffalo.DEFAULT_EPS == 0.40
    assert buffalo.DEFAULT_MIN_SAMPLES == 2
    assert buffalo.METRIC == "1-dot"
    assert buffalo.STRONG_MIN_INTRA == 0.50
    assert buffalo.DEFAULT_THRESHOLD == 0.60
    assert buffalo.EXPECTED_FACE_DIM == 512
    assert active.DEFAULT_EPS != buffalo.DEFAULT_EPS or active.PACK_FAMILY != buffalo.PACK_FAMILY
    assert active.EXPECTED_FACE_DIM != buffalo.EXPECTED_FACE_DIM
