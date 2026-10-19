"""Selection retrieval merges region, text, and object doors without identity."""

from __future__ import annotations

import numpy as np

from semblon.selection_retrieval import retrieve_selection


def test_merge_keeps_each_basis(monkeypatch, tmp_path):
    crop = np.zeros((8, 8, 3), dtype=np.uint8)

    def fake_region(*_args, **_kwargs):
        return {
            "status": "SUCCESS",
            "reason": "Matching region.",
            "items": [{"media_id": "m-visual", "score": 0.8, "match_norm": [0.1, 0.2, 0.3, 0.4]}],
            "similarity_basis": "Similar look",
            "engine": "dinov2-patch",
            "understanding": "Unlabelled region.",
        }

    def fake_text(_store, query, limit=10, **_kwargs):
        assert query == "Nike"
        return {
            "status": "SUCCESS",
            "items": [{"media_id": "m-visual", "score": 1.0}, {"media_id": "m-text", "score": 1.0}],
            "similarity_basis": "Text in photos (OCR substring)",
        }

    def fake_object(_store, query, limit=10, **_kwargs):
        assert query == "cup"
        return {
            "status": "SUCCESS",
            "items": [{"media_id": "m-object", "score": 0.7}],
            "similarity_basis": "COCO object detection (NanoDet)",
        }

    monkeypatch.setattr("semblon.region_search.find_similar_crop", fake_region)
    monkeypatch.setattr("semblon.search.search_text", fake_text)
    monkeypatch.setattr("semblon.search.search_object", fake_object)
    rec = retrieve_selection(
        tmp_path / "s.sqlite",
        crop=crop,
        observations=[
            {"kind": "text", "payload": {"text": "Nike Air", "role": "ocr"}},
            {"kind": "object", "payload": {"label": "cup", "class": "cup"}},
        ],
        selection_kind="text_priority",
    )
    assert rec["status"] == "SUCCESS"
    ids = [item["media_id"] for item in rec["items"]]
    assert ids[0] == "m-visual"
    assert set(ids) == {"m-visual", "m-text", "m-object"}
    visual = rec["items"][0]
    assert "Similar look" in visual["similarity_basis"]
    assert "Text in photos (OCR substring)" in visual["similarity_basis"]
    assert "Similar look" in rec["similarity_basis"]
    assert "Text in photos (OCR substring)" in rec["similarity_basis"]
    assert "COCO object detection (NanoDet)" in rec["similarity_basis"]
    doors = {row["door"]: row["status"] for row in rec["channels"]}
    assert doors == {"region": "SUCCESS", "text": "SUCCESS", "object": "SUCCESS"}


def test_text_only_skips_visual_similarity(monkeypatch, tmp_path):
    def fail_region(*_args, **_kwargs):
        raise AssertionError("text-only selection must not run visual similarity")

    monkeypatch.setattr("semblon.region_search.find_similar_crop", fail_region)
    monkeypatch.setattr(
        "semblon.search.search_text",
        lambda *_args, **_kwargs: {"status": "NO_RESULT", "items": []},
    )
    rec = retrieve_selection(
        tmp_path / "s.sqlite",
        crop=np.zeros((4, 4, 3), dtype=np.uint8),
        observations=[{"kind": "text", "payload": {"text": "label", "role": "ocr"}}],
        selection_kind="text",
    )
    assert rec["channels"][0]["door"] == "region"
    assert rec["channels"][0]["status"] == "SKIPPED"
    assert rec["status"] == "NO_RESULT"


def test_missing_region_stays_unavailable_when_nothing_else_matches(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "semblon.region_search.find_similar_crop",
        lambda *_args, **_kwargs: {
            "status": "UNAVAILABLE",
            "reason": "Region encoder is not installed.",
            "error_id": "region.NO_PACK",
            "items": [],
            "similarity_basis": "Similar look",
        },
    )
    rec = retrieve_selection(
        tmp_path / "s.sqlite",
        crop=np.zeros((4, 4, 3), dtype=np.uint8),
        observations=[],
        selection_kind="region",
    )
    assert rec["status"] == "UNAVAILABLE"
    assert rec["error_id"] == "region.NO_PACK"
    assert rec["items"] == []
