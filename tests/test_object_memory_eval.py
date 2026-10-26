from __future__ import annotations

import pytest

from semblon.object_memory_eval import ObjectMemoryEvalError, evaluate_cases


def test_object_memory_metrics_compute_recall_mrr_and_hard_negatives():
    report = evaluate_cases([{
        "case_id": "toolbox-view-1",
        "relevant_media_ids": ["same-toolbox"],
        "hard_negative_media_ids": ["red-suitcase"],
        "ranked_media_ids": ["red-suitcase", "same-toolbox", "desk"],
        "real_photo": False,
    }])
    assert report["recall_at_k"]["1"] == 0.0
    assert report["recall_at_k"]["5"] == 1.0
    assert report["mrr"] == 0.5
    assert report["hard_negative_win_rate"] == 0.0
    assert report["real_photo_claim_allowed"] is False


def test_object_memory_eval_rejects_cases_without_relevant_ids():
    with pytest.raises(ObjectMemoryEvalError):
        evaluate_cases([{"case_id": "bad", "ranked_media_ids": ["x"]}])


def test_object_memory_eval_does_not_call_unverified_case_real_photo():
    report = evaluate_cases([{
        "case_id": "fixture-only",
        "relevant_media_ids": ["match"],
        "ranked_media_ids": ["match"],
    }])
    assert report["dataset_type"] == "synthetic_or_unverified"
    assert "do not prove" in report["warning"]
