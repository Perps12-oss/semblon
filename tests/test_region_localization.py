"""Lens-local region honesty: consensus boxes, crop-forward, loud colour, low-info."""

from __future__ import annotations

import numpy as np

from semblon.native_shell.adapter import ArchiveAdapter
from semblon.region_search import (
    drop_low_info_tokens,
    is_low_info_crop,
    translation_consensus,
)
from semblon.selection_retrieval import _strip_label_from_channels
from semblon.query_spec import QuerySpec


def test_translation_consensus_rejects_scattered_matches():
    # Query tokens span the crop; gallery argmaxes all collapse to one corner.
    pairs = []
    for i in range(6):
        q_nx = 0.1 + 0.15 * i
        q_ny = 0.2 + 0.1 * (i % 2)
        pairs.append((1.0, q_nx, q_ny, 0.05, 0.05, (1.0, 1.0, 10.0, 10.0)))
    boxes, size = translation_consensus(pairs, tol=0.08, min_keep=3)
    assert boxes == []
    assert size < 3


def test_translation_consensus_keeps_rigid_offset():
    pairs = []
    for i in range(5):
        q_nx = 0.1 + 0.1 * i
        q_ny = 0.2
        g_nx = q_nx + 0.35
        g_ny = q_ny + 0.15
        pairs.append((1.0, q_nx, q_ny, g_nx, g_ny, (g_nx * 100, g_ny * 100, g_nx * 100 + 8, g_ny * 100 + 8)))
    boxes, size = translation_consensus(pairs, tol=0.08, min_keep=3)
    assert size >= 3
    assert len(boxes) >= 3


def test_low_info_crop_and_token_drop():
    flat = np.full((32, 32, 3), 180, dtype=np.uint8)
    busy = np.zeros((32, 32, 3), dtype=np.uint8)
    busy[:16, :16] = (0, 0, 255)
    busy[16:, 16:] = (0, 255, 0)
    assert is_low_info_crop(flat) is True
    assert is_low_info_crop(busy) is False

    # Five near-constant tokens + one structured token → keep the informative row.
    base = np.ones((6, 8), dtype=np.float32) * 0.25
    base[0] = np.linspace(-1.0, 1.0, 8, dtype=np.float32)
    filtered, boxes = drop_low_info_tokens(base, [(0, 0, 1, 1)] * 6)
    assert filtered.shape[0] < 6
    assert filtered.shape[0] >= 1
    assert boxes is not None
    assert len(boxes) == filtered.shape[0]


def test_strip_label_keeps_colour_only():
    spec = QuerySpec(mode="look", modifier="", part_index=-1)
    channels = [
        {
            "door": "region",
            "status": "SUCCESS",
            "similarity_basis": "Colour only",
            "engine": "color-hist",
            "count": 2,
        }
    ]
    # Channel door is "region" in retrieve_selection; DOOR_LOOK is the ranked key.
    assert _strip_label_from_channels(spec, channels) == "Colour only"


def test_adapter_never_overrides_colour_with_similar_look(tmp_path):
    from semblon.application import Application
    from semblon.store import init_db
    import sqlite3

    store = tmp_path / "s.sqlite"
    conn = sqlite3.connect(str(store))
    init_db(conn)
    conn.close()
    adapter = ArchiveAdapter(Application(store))
    result = adapter.similar_region(
        {
            "similar": {
                "status": "SUCCESS",
                "items": [{"media_id": "m2", "score": 0.7, "match_norm": [0, 0, 0, 0]}],
                "similarity_basis": "Colour only",
                "engine": "color-hist",
                "strip_label": "Similar look",
                "query_source": "low-info",
                "error_id": "region.LOW_INFO",
            }
        }
    )
    assert result.data["basis_label"] == "Colour only"
    assert "colour" in result.message.lower()
    assert "similar look" not in result.message.lower()
    assert result.data.get("low_info") is True


def test_score_one_block_hides_inconsistent_union():
    from semblon.region_search import _score_one_block

    # Two query tokens; gallery argmaxes land at opposite corners → no box.
    block = np.array(
        [
            [0.9, 0.1, 0.05, 0.05],
            [0.05, 0.05, 0.1, 0.9],
        ],
        dtype=np.float32,
    )
    group = {
        "media_id": "m2",
        "width": 100,
        "height": 100,
        "boxes": [
            (0.0, 0.0, 10.0, 10.0),
            (20.0, 20.0, 30.0, 30.0),
            (40.0, 40.0, 50.0, 50.0),
            (90.0, 90.0, 100.0, 100.0),
        ],
    }
    query_boxes = [(0.0, 0.0, 10.0, 10.0), (40.0, 0.0, 50.0, 10.0)]
    item = _score_one_block(
        block,
        group,
        token_floor=0.2,
        score_floor=0.2,
        coverage_floor=0.2,
        keep_weak=True,
        query_boxes=query_boxes,
        query_size=(50, 20),
    )
    assert item is not None
    assert item["location_uncertain"] is True
    assert item["match_norm"] == [0.0, 0.0, 0.0, 0.0]
