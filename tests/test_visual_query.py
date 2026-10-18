from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from semblon.visual_query import VisualQuery, run_visual_query


def test_media_query_returns_unavailable_when_photo_missing(tmp_path):
    rec = run_visual_query(
        tmp_path / "missing.sqlite",
        VisualQuery(source="media", media_id="m1"),
    ).as_dict()
    assert rec["status"] == "UNAVAILABLE"
    assert "Nothing was searched" in rec["reason"]


def test_media_query_forwards_rect_into_query(monkeypatch, tmp_path):
    seen = {}

    def fake_load(_store, _media_id):
        return np.zeros((12, 12, 3), dtype=np.uint8)

    def fake_query(image, *, capabilities=None, **kwargs):
        seen["shape"] = tuple(image.shape)
        seen["caps"] = capabilities
        seen["kwargs"] = kwargs
        return SimpleNamespace(region={"x": 1, "y": 2, "w": 3, "h": 4}, results=())

    monkeypatch.setattr("semblon.visual_query.load_media_bgr", fake_load)
    monkeypatch.setattr("semblon.visual_query.query_image", fake_query)
    monkeypatch.setattr(
        "semblon.visual_query.lens_result_summary",
        lambda _report: {"status": "NO_RESULT", "item_count": 0, "reason": "none"},
    )
    monkeypatch.setattr("semblon.visual_query.format_query_lines", lambda _report: ["Lens", "none"])
    rec = run_visual_query(
        tmp_path / "s.sqlite",
        VisualQuery(
            source="media",
            media_id="m1",
            rect={"x": 10, "y": 11, "w": 20, "h": 21},
            capabilities=("ocr",),
        ),
    ).as_dict()
    assert rec["source"] == "media"
    assert rec["media_id"] == "m1"
    assert rec["region"] == {"x": 1, "y": 2, "w": 3, "h": 4}
    assert seen["shape"] == (12, 12, 3)
    assert seen["caps"] == ("ocr",)
    assert seen["kwargs"] == {"x": 10, "y": 11, "w": 20, "h": 21}


def test_screen_query_attaches_local_retrieval(monkeypatch, tmp_path):
    crop = np.ones((8, 6, 3), dtype=np.uint8)
    monkeypatch.setattr(
        "semblon.visual_query.query_screen_with_image",
        lambda *args, **kwargs: (
            SimpleNamespace(region={"x": 0, "y": 0, "w": 8, "h": 8}, results=()),
            crop,
        ),
    )
    monkeypatch.setattr(
        "semblon.visual_query.lens_result_summary",
        lambda _report: {"status": "SUCCESS", "item_count": 1, "summary": "1 result"},
    )
    monkeypatch.setattr("semblon.visual_query.format_query_lines", lambda _report: ["Lens", "ok"])
    monkeypatch.setattr(
        "semblon.region_search.find_similar_crop",
        lambda store, *, crop, limit, selection_kind, cancelled: {
            "status": "SUCCESS",
            "count": 1,
            "items": [{"media_id": "m1", "score": 0.9}],
            "selection_kind": selection_kind,
            "limit": limit,
        },
    )
    rec = run_visual_query(
        tmp_path / "s.sqlite",
        VisualQuery(
            source="screen",
            screen_rect={"x": 2, "y": 3, "w": 40, "h": 22},
            limit=7,
            selection_kind="text",
        ),
    ).as_dict()
    assert rec["source"] == "screen"
    assert rec["status"] == "SUCCESS"
    assert rec["similar"]["count"] == 1
    assert rec["similar"]["selection_kind"] == "text"
    assert rec["similar"]["limit"] == 7

