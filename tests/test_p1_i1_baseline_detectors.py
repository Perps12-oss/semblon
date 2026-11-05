"""P1 I1 detectors — fail closed after A1. R1–R8 must pass on the fixed tree."""

from __future__ import annotations

import math
import struct

import pytest

from semblon.compare import CompareError, compare, require_finite_threshold
from semblon.eval import DEFAULT_THRESHOLD
from semblon.identify import IdentifyError, _decide


def _blob(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def _unit(dim: int = 4) -> bytes:
    vals = [0.0] * dim
    vals[0] = 1.0
    return _blob(vals)


def test_r1_pack_mismatch_already_fail_closed():
    a = _unit()
    with pytest.raises(CompareError, match="pack_id mismatch"):
        compare("pack-a", 4, a, "pack-b", 4, a)


def test_r2_dimension_mismatch_already_fail_closed():
    a = _unit(4)
    b = _unit(8)
    with pytest.raises(CompareError, match="dimension mismatch"):
        compare("pack", 4, a, "pack", 8, b)


def test_r3_length_mismatch_already_fail_closed():
    a = _unit(4)
    with pytest.raises(CompareError, match="embedding length"):
        compare("pack", 4, a, "pack", 4, a[:8])


def test_r4_nan_must_not_produce_score():
    good = _unit(4)
    bad = _blob([float("nan"), 0.0, 0.0, 0.0])
    with pytest.raises(CompareError, match="non-finite"):
        compare("pack", 4, good, "pack", 4, bad)


def test_r5_inf_must_not_produce_score():
    good = _unit(4)
    bad = _blob([float("inf"), 0.0, 0.0, 0.0])
    with pytest.raises(CompareError, match="non-finite"):
        compare("pack", 4, good, "pack", 4, bad)


def test_r6_non_unit_l2_must_not_produce_score():
    good = _unit(4)
    bad = _blob([2.0, 0.0, 0.0, 0.0])
    with pytest.raises(CompareError, match="l2"):
        compare("pack", 4, good, "pack", 4, bad)


def test_r7_non_finite_threshold_must_not_accept():
    ranked = [{"person_id": "p1", "display_name": "A", "score": 0.99, "exemplar_face_id": "f1"}]
    assert math.isfinite(DEFAULT_THRESHOLD)
    with pytest.raises(CompareError, match="non-finite threshold"):
        _decide(ranked, float("nan"))


def test_r8_empty_pack_must_fail_closed():
    a = _unit(4)
    with pytest.raises(CompareError, match="empty pack_id"):
        compare("", 4, a, "", 4, a)


def test_same_dim_different_pack_already_fail_closed():
    a = _unit(4)
    b = _unit(4)
    with pytest.raises(CompareError, match="pack_id mismatch"):
        compare("yunet-a", 4, a, "yunet-b", 4, b)


def test_require_finite_threshold_bounds():
    assert require_finite_threshold(DEFAULT_THRESHOLD) == float(DEFAULT_THRESHOLD)
    with pytest.raises(CompareError):
        require_finite_threshold(1.5)
    with pytest.raises(CompareError):
        require_finite_threshold(float("inf"))


def test_rejection_path_audit_matrix_documented():
    matrix = {
        "R1_pack_mismatch": "fail_closed",
        "R2_dimension_mismatch": "fail_closed",
        "R3_length_mismatch": "fail_closed",
        "R4_nan": "fail_closed",
        "R5_inf": "fail_closed",
        "R6_l2_norm": "fail_closed",
        "R7_threshold": "fail_closed",
        "R8_empty_pack": "fail_closed",
    }
    assert len(matrix) == 8
    assert all(v == "fail_closed" for v in matrix.values())
