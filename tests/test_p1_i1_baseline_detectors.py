"""P1 baseline detectors for I1 — evidence only. No production fix in this commit.

Issue #6 (compare accepts NaN/Inf) and the eight rejection-path audit from
P0-IDENTITY-COVERAGE pack/contract checks. Expected-red cases use strict xfail
so CI stays honest: when a fix lands, XPASS fails until the mark is removed.
"""

from __future__ import annotations

import math
import struct

import pytest

from semblon.compare import CompareError, compare
from semblon.eval import DEFAULT_THRESHOLD
from semblon.identify import IdentifyError, _decide


def _blob(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def _unit(dim: int = 4) -> bytes:
    # L2-normal unit along first axis.
    vals = [0.0] * dim
    vals[0] = 1.0
    return _blob(vals)


# --- Eight rejection paths (P0 pack/contract inventory) -------------------
# R1 pack_id mismatch
# R2 dimension mismatch
# R3 embedding byte length != 4 * dim
# R4 NaN in payload
# R5 Inf in payload
# R6 L2 norm not ~1 (contract says l2)
# R7 non-finite / invalid threshold at decide/identify boundary
# R8 empty / unknown pack_id (incompatible contract)


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


@pytest.mark.xfail(strict=True, reason="P0 issue #6 / R4: compare() does not reject NaN on baseline")
def test_r4_nan_must_not_produce_score():
    good = _unit(4)
    bad = _blob([float("nan"), 0.0, 0.0, 0.0])
    with pytest.raises(CompareError):
        compare("pack", 4, good, "pack", 4, bad)


@pytest.mark.xfail(strict=True, reason="P0 issue #6 / R5: compare() does not reject Inf on baseline")
def test_r5_inf_must_not_produce_score():
    good = _unit(4)
    bad = _blob([float("inf"), 0.0, 0.0, 0.0])
    with pytest.raises(CompareError):
        compare("pack", 4, good, "pack", 4, bad)


@pytest.mark.xfail(strict=True, reason="R6: compare() does not enforce L2 norm on baseline")
def test_r6_non_unit_l2_must_not_produce_score():
    good = _unit(4)
    # Same direction, magnitude 2 — not L2-normalised.
    bad = _blob([2.0, 0.0, 0.0, 0.0])
    with pytest.raises(CompareError):
        compare("pack", 4, good, "pack", 4, bad)


@pytest.mark.xfail(strict=True, reason="R7: identify._decide does not reject non-finite threshold on baseline")
def test_r7_non_finite_threshold_must_not_accept():
    ranked = [{"person_id": "p1", "display_name": "A", "score": 0.99, "exemplar_face_id": "f1"}]
    # NaN threshold: score < threshold is False for NaN comparisons in Python…
    # Baseline may ACCEPT or UNKNOWN depending on IEEE; invariant requires refuse.
    if not (isinstance(DEFAULT_THRESHOLD, float) and math.isfinite(DEFAULT_THRESHOLD)):
        pytest.fail("DEFAULT_THRESHOLD itself is non-finite")
    try:
        out = _decide(ranked, float("nan"))
    except (IdentifyError, ValueError, CompareError):
        return
    assert out["decision"] != "ACCEPT", "non-finite threshold must not ACCEPT"


@pytest.mark.xfail(strict=True, reason="R8: empty pack_id is not treated as incompatible contract on baseline")
def test_r8_empty_pack_must_fail_closed():
    a = _unit(4)
    with pytest.raises(CompareError):
        compare("", 4, a, "", 4, a)


def test_issue6_nan_score_is_currently_non_finite_acceptance_risk():
    """Positive evidence of the defect: baseline returns a non-finite score."""
    good = _unit(4)
    bad = _blob([float("nan"), 0.0, 0.0, 0.0])
    score = compare("pack", 4, good, "pack", 4, bad)
    assert not math.isfinite(score), "expected baseline defect: NaN score from compare()"


def test_same_dim_different_pack_already_fail_closed():
    """Same-dimension cross-pack cannot compare (already enforced)."""
    a = _unit(4)
    b = _unit(4)
    with pytest.raises(CompareError, match="pack_id mismatch"):
        compare("yunet-a", 4, a, "yunet-b", 4, b)


def test_rejection_path_audit_matrix_documented():
    """Living checklist — keep in sync with docs/invariants/P1-REJECTION-PATH-AUDIT.md."""
    matrix = {
        "R1_pack_mismatch": "fail_closed",
        "R2_dimension_mismatch": "fail_closed",
        "R3_length_mismatch": "fail_closed",
        "R4_nan": "baseline_defect",
        "R5_inf": "baseline_defect",
        "R6_l2_norm": "baseline_defect",
        "R7_threshold": "baseline_defect",
        "R8_empty_pack": "baseline_defect",
    }
    assert len(matrix) == 8
    assert matrix["R1_pack_mismatch"] == "fail_closed"
    assert matrix["R4_nan"] == "baseline_defect"
