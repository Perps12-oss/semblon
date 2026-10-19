"""RRF fusion is retrieval structure, not identity."""

from __future__ import annotations

from semblon.retrieval_fuse import (
    fuse_hits,
    reciprocal_rank_fusion,
    rerank_score,
)
from semblon.selection_retrieval import retrieve_selection


def test_rrf_rewards_agreement_across_channels():
    fused = reciprocal_rank_fusion(
        {
            "region": ["photo-a", "photo-b"],
            "text": ["photo-a", "photo-c"],
            "object": ["photo-d"],
        }
    )
    assert fused["photo-a"] > fused["photo-b"]
    assert fused["photo-a"] > fused["photo-c"]
    assert fused["photo-a"] > fused["photo-d"]


def test_rrf_ignores_duplicate_ids_inside_one_channel():
    fused = reciprocal_rank_fusion({"text": ["brand", "brand", "other"]})
    single = reciprocal_rank_fusion({"text": ["brand", "other"]})
    assert fused == single


def test_face_rows_are_dropped_from_fusion():
    ranked = fuse_hits(
        {
            "region": [
                {"media_id": "keep", "score": 0.4, "similarity_basis": "Similar look"},
                {
                    "media_id": "face-hit",
                    "score": 0.99,
                    "modality": "face",
                    "similarity_basis": "Same face",
                },
            ]
        },
        limit=10,
    )
    assert [row["media_id"] for row in ranked] == ["keep"]
    assert all(row.get("modality") != "face" for row in ranked)


def test_text_overlap_rerank_beats_visual_only_when_brands_agree():
    visual_only = rerank_score(rrf=0.02, visual=0.80)
    with_text = rerank_score(rrf=0.02, visual=0.55, text_overlap=1.0)
    assert with_text > visual_only


def test_fuse_ranks_by_rrf_not_raw_visual_score():
    ranked = fuse_hits(
        {
            "region": [
                {"media_id": "true-hit", "score": 0.51, "similarity_basis": "Similar look"},
                {"media_id": "colour-distractor", "score": 0.88, "similarity_basis": "Similar look"},
            ],
            "text": [
                {"media_id": "true-hit", "score": 1.0, "similarity_basis": "Text in photos (OCR substring)"},
            ],
        },
        limit=5,
    )
    assert ranked[0]["media_id"] == "true-hit"
    assert ranked[0]["rrf"] > ranked[1]["rrf"]


def test_class_and_colour_are_optional_rerank_signals():
    base = rerank_score(rrf=0.016)
    with_class = rerank_score(rrf=0.016, class_match=1.0, colour_similarity=0.9)
    assert with_class > base
    assert rerank_score(rrf=0.016, class_match=None) == base


def test_selection_retrieval_fuses_with_rrf(monkeypatch, tmp_path):
    import numpy as np

    monkeypatch.setattr(
        "semblon.region_search.find_similar_crop",
        lambda *_args, **_kwargs: {
            "status": "SUCCESS",
            "items": [
                {"media_id": "mug-other-angle", "score": 0.51, "match_norm": [0.1, 0.1, 0.2, 0.2]},
                {"media_id": "same-colour-tile", "score": 0.70, "match_norm": [0, 0, 1, 1]},
            ],
            "similarity_basis": "Similar look",
            "engine": "dinov2-patch",
        },
    )
    monkeypatch.setattr(
        "semblon.search.search_text",
        lambda *_args, **_kwargs: {
            "status": "SUCCESS",
            "items": [{"media_id": "mug-other-angle", "score": 1.0}],
            "similarity_basis": "Text in photos (OCR substring)",
        },
    )
    monkeypatch.setattr(
        "semblon.search.search_object",
        lambda *_args, **_kwargs: {
            "status": "SUCCESS",
            "items": [{"media_id": "mug-other-angle", "score": 0.8}],
            "similarity_basis": "COCO object detection (NanoDet)",
        },
    )
    rec = retrieve_selection(
        tmp_path / "s.sqlite",
        crop=np.zeros((8, 8, 3), dtype=np.uint8),
        observations=[
            {"kind": "text", "payload": {"text": "ACME", "role": "ocr"}},
            {"kind": "object", "payload": {"label": "cup"}},
        ],
        selection_kind="region",
    )
    assert rec["items"][0]["media_id"] == "mug-other-angle"
    assert rec["items"][0]["rrf"] > rec["items"][1]["rrf"]
    assert "Similar look" in rec["items"][0]["similarity_basis"]
    assert "Text in photos (OCR substring)" in rec["items"][0]["similarity_basis"]
