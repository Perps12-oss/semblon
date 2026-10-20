"""Labelled Lens eval: ranks and hard negatives. No precision on synthetic."""

from __future__ import annotations

import json

from semblon.lens_eval import (
    EVAL_SET_CONFIRMATORY,
    EVAL_SET_SYNTHETIC,
    FAMILY_BRAND_TEXT,
    FAMILY_HARD_NEG_COLOUR,
    FAMILY_PART_VS_WHOLE,
    FAMILY_SAME_KIND,
    FAMILY_SAME_LOOK,
    LensEvalError,
    build_synthetic_store,
    identity_clean,
    labelled_cases,
    normalize_eval_set,
    precision_allowed,
    precision_refusal,
    relevant_above_hard_neg,
    run_case,
    run_eval,
    score_report,
)
from semblon.store import connect


def _by_family(family: str):
    for case in labelled_cases():
        if case.family == family:
            return case
    raise AssertionError(family)


def test_eval_set_aliases():
    assert normalize_eval_set("synthetic") == EVAL_SET_SYNTHETIC
    assert normalize_eval_set("confirmatory") == EVAL_SET_CONFIRMATORY
    assert precision_allowed("synthetic") is False
    assert precision_allowed("confirmatory") is True
    assert "refused" in precision_refusal("synthetic")
    try:
        normalize_eval_set("ann")
    except LensEvalError as exc:
        assert "unknown" in str(exc)
    else:
        raise AssertionError("ann is not an eval set")


def test_relevant_above_hard_neg_needs_a_relevant_hit():
    assert relevant_above_hard_neg(["rel", "neg"], ["rel"], ["neg"]) is True
    assert relevant_above_hard_neg(["neg", "rel"], ["rel"], ["neg"]) is False
    assert relevant_above_hard_neg(["rel"], ["rel"], ["neg"]) is True
    assert relevant_above_hard_neg(["neg"], ["rel"], ["neg"]) is False


def test_synthetic_brand_text_finds_acme(tmp_path):
    """BM25 must recall ACME. Beating a confident look-alike is the measured bar."""
    case = _by_family(FAMILY_BRAND_TEXT)
    assert case.observations[0]["payload"]["text"] == "ACME"
    rec = run_case(build_synthetic_store(tmp_path), case)
    assert rec["relevant_ranks"]["acme-hit"] is not None
    assert rec["ranked"]
    assert "acme-hit" in rec["ranked"]


def test_synthetic_same_kind_cup_above_chair(tmp_path):
    rec = run_case(build_synthetic_store(tmp_path), _by_family(FAMILY_SAME_KIND))
    assert rec["pass"] is True
    assert rec["query_spec"]["mode_label"] == "Same kind"
    assert rec["relevant_ranks"]["cup-blue"] is not None
    chair = rec["hard_neg_ranks"]["chair-red"]
    assert chair is None or rec["relevant_ranks"]["cup-blue"] < chair


def test_synthetic_same_look_prefers_red_cup_over_blue(tmp_path):
    rec = run_case(build_synthetic_store(tmp_path), _by_family(FAMILY_SAME_LOOK))
    assert rec["pass"] is True
    assert rec["query_spec"]["mode"] == "look"
    assert rec["relevant_ranks"]["cup-red-2"] < (rec["hard_neg_ranks"]["cup-blue"] or 99)


def test_synthetic_part_recalls_the_logo(tmp_path):
    rec = run_case(build_synthetic_store(tmp_path), _by_family(FAMILY_PART_VS_WHOLE))
    assert rec["query_spec"]["part_index"] == 0
    assert rec["relevant_ranks"]["logo-hit"] is not None
    assert "logo-hit" in rec["ranked"]


def test_synthetic_hard_neg_same_colour_chair_loses(tmp_path):
    rec = run_case(build_synthetic_store(tmp_path), _by_family(FAMILY_HARD_NEG_COLOUR))
    assert rec["pass"] is True
    assert rec["ranked"][0] != "chair-red"
    assert rec["relevant_ranks"]["cup-red-2"] < (rec["hard_neg_ranks"]["chair-red"] or 99)


def test_synthetic_refuses_precision(tmp_path):
    report = run_eval(tmp_path / "work", eval_set="synthetic")
    assert report["eval_set"] == EVAL_SET_SYNTHETIC
    assert report["precision"] is None
    assert report["precision_at_5"] is None
    assert report["recall_at_5"] is None
    assert "refused" in report["precision_reason"]
    assert report["status"] in {"PASS", "FAIL"}
    families = {row["family"] for row in report["cases"]}
    assert families == {
        FAMILY_BRAND_TEXT,
        FAMILY_SAME_KIND,
        FAMILY_SAME_LOOK,
        FAMILY_PART_VS_WHOLE,
        FAMILY_HARD_NEG_COLOUR,
    }
    dumped = json.dumps(report)
    assert '"precision": null' in dumped
    assert report["timing"]["ann_justified"] is False


def test_confirmatory_refuses_precision_without_frozen_set(tmp_path):
    report = run_eval(tmp_path / "work", eval_set="confirmatory")
    assert report["eval_set"] == EVAL_SET_CONFIRMATORY
    assert report["status"] == "not_confirmatory"
    assert report["precision"] is None
    assert "confirmatory" in report["precision_reason"]


def test_eval_does_not_write_identity(tmp_path):
    store = build_synthetic_store(tmp_path)
    for case in labelled_cases():
        run_case(store, case)
    assert identity_clean(store)
    conn = connect(store)
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0] == 0
    assert (
        conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
        == 0
    )
    conn.close()


def test_ann_stays_parked_on_synthetic_timing(tmp_path):
    report = score_report(
        [
            {
                "case_id": "x",
                "pass": True,
                "relevant_ranks": {"a": 1},
                "hard_neg_ranks": {"b": None},
            }
        ],
        eval_set="synthetic",
        elapsed_ms=4.0,
        corpus_size=10,
    )
    assert report["timing"]["ann_justified"] is False
    assert report["timing"]["index"]["ann"]["enabled"] is False
    assert "parked" in report["timing"]["ann_reason"].lower() or "small" in report["timing"]["ann_reason"].lower()
