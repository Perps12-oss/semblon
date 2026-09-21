"""R3 §6 measurement harness — refuse fake PASS; pure logic."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from r3_measure import (  # noqa: E402
    CRITERIA,
    CRITERION_IDS,
    FakePassError,
    assert_no_fake_pass,
    mark_unverified,
    run_a11y_tree,
    run_accent_suppress,
    run_all,
    run_frame_time_4k60,
    run_mica_opaque,
    run_virtualized_grid_10k,
    run_wcag_aa,
)


REQUIRED_KEYS = {"criterion_id", "verified", "pass", "metrics", "notes", "status"}

RUNNERS = (
    run_accent_suppress,
    run_mica_opaque,
    run_frame_time_4k60,
    run_wcag_aa,
    run_virtualized_grid_10k,
    run_a11y_tree,
)


def test_six_criteria_match_brief_order():
    assert len(CRITERIA) == 6
    assert CRITERION_IDS == (
        "accent_suppress",
        "mica_opaque",
        "frame_time_4k60",
        "wcag_aa",
        "virtualized_grid_10k",
        "a11y_tree",
    )


def test_default_runners_are_unverified_not_pass():
    for runner, cid in zip(RUNNERS, CRITERION_IDS, strict=True):
        result = runner()
        assert set(result) >= REQUIRED_KEYS
        assert result["criterion_id"] == cid
        assert result["verified"] is False
        assert result["pass"] is False
        assert result["status"] == "unverified"
        assert_no_fake_pass(result)


def test_run_all_default_six_unverified():
    results = run_all()
    assert len(results) == 6
    assert [r["criterion_id"] for r in results] == list(CRITERION_IDS)
    assert all(r["verified"] is False and r["pass"] is False for r in results)
    assert all(r["status"] == "unverified" for r in results)


def test_simulate_fail_verified_true_pass_false():
    for runner in RUNNERS:
        result = runner(simulate_fail=True)
        assert result["verified"] is True
        assert result["pass"] is False
        assert result["status"] == "fail"
        assert result["metrics"].get("simulate_fail") is True
        assert_no_fake_pass(result)


def test_assert_no_fake_pass_raises_on_pass_without_verified():
    with pytest.raises(FakePassError, match="fake PASS refused"):
        assert_no_fake_pass(
            {
                "criterion_id": "accent_suppress",
                "verified": False,
                "pass": True,
                "status": "pass",
                "metrics": {},
                "notes": "invented",
            }
        )


def test_assert_no_fake_pass_allows_verified_pass_and_fail():
    assert_no_fake_pass(
        {
            "criterion_id": "wcag_aa",
            "verified": True,
            "pass": True,
            "status": "pass",
            "metrics": {},
            "notes": "host-measured",
        }
    )
    assert_no_fake_pass(
        {
            "criterion_id": "wcag_aa",
            "verified": True,
            "pass": False,
            "status": "fail",
            "metrics": {},
            "notes": "host-measured",
        }
    )
    assert_no_fake_pass(mark_unverified("not run", criterion_id="wcag_aa"))


def test_mark_unverified_shape():
    shell = mark_unverified("needs Windows host", criterion_id="mica_opaque")
    assert shell["criterion_id"] == "mica_opaque"
    assert shell["verified"] is False
    assert shell["pass"] is False
    assert shell["status"] == "unverified"
    assert shell["notes"] == "needs Windows host"


def test_no_silent_simulate_pass_kwarg():
    """Runners must not expose a simulate_pass path that claims product PASS."""
    for runner in RUNNERS:
        with pytest.raises(TypeError):
            runner(simulate_pass=True)  # type: ignore[call-arg]


def test_measurement_can_pass_only_when_verified():
    result = run_frame_time_4k60(measurement={"frame_time_ms": 12.5})
    assert result["verified"] is True
    assert result["pass"] is True
    assert result["status"] == "pass"
    assert_no_fake_pass(result)


def test_measurement_fail_is_verified():
    result = run_frame_time_4k60(measurement={"frame_time_ms": 20.0})
    assert result["verified"] is True
    assert result["pass"] is False
    assert result["status"] == "fail"


def test_incomplete_measurement_is_verified_fail_not_pass():
    result = run_accent_suppress(measurement={"focus_accent_suppressed": True})
    assert result["verified"] is True
    assert result["pass"] is False
    assert result["status"] == "fail"
