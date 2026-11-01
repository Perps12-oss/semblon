"""Lens-local region honesty: consensus boxes, crop-forward, loud colour, low-info."""

from __future__ import annotations

import numpy as np

from semblon.native_shell.adapter import ArchiveAdapter
from semblon.region_search import (
    drop_low_info_tokens,
    geometric_consensus,
    is_low_info_crop,
    shortlist_media_by_cls,
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


def test_geometric_consensus_accepts_scaled_match():
    # Spread query points so translation-only cannot absorb a 1.8× scale.
    pairs = []
    scale = 1.8
    tx, ty = 0.05, 0.02
    for i in range(6):
        q_nx = 0.05 + 0.15 * i
        q_ny = 0.1 + 0.12 * (i % 3)
        g_nx = scale * q_nx + tx
        g_ny = scale * q_ny + ty
        pairs.append((1.0, q_nx, q_ny, g_nx, g_ny, (g_nx * 100, g_ny * 100, g_nx * 100 + 6, g_ny * 100 + 6)))
    boxes, size = translation_consensus(pairs, tol=0.05, min_keep=4)
    assert boxes == []  # scale≠1 must not pass translation-only
    boxes, size, model = geometric_consensus(pairs, tol=0.05, min_keep=4)
    assert size >= 4
    assert len(boxes) >= 4
    assert model is not None
    assert 1.6 <= float(model["scale"]) <= 2.0


def test_shortlist_media_by_cls_ranks_region_neighbours(tmp_path, monkeypatch):
    from semblon.region_encoder import OUTPUT_DIM, MODALITY_REGION, pack_id_for, KNOWN_SHA256, WEIGHT_NAME
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", OUTPUT_DIM, "l2", "{}", "{}", "x64", "native"),
    )
    pack = pack_id_for(KNOWN_SHA256[WEIGHT_NAME])
    query = np.zeros(OUTPUT_DIM, dtype=np.float32)
    query[0] = 1.0
    near = query.copy()
    near[0] = 0.95
    near[1] = (1.0 - 0.95**2) ** 0.5
    far = np.zeros(OUTPUT_DIM, dtype=np.float32)
    far[2] = 1.0
    for media_id, vec in (("m-near", near), ("m-far", far), ("m-query", query)):
        path = tmp_path / f"{media_id}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)
        conn.execute(
            "INSERT INTO media(media_id, source_type, path, sha256, width, height, mtime_ns, byte_size) VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 32, 32, 0, 1),
        )
        obs = f"o-{media_id}"
        item = f"i-{media_id}"
        conn.execute(
            "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
            (obs, media_id, None, None, "r1"),
        )
        conn.execute(
            """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
               bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (item, obs, "r1", "clip", "dinov2", 0, 0, 8, 8, 1.0, "{}"),
        )
        blob = (vec / max(float(np.linalg.norm(vec)), 1e-8)).astype(np.float32).tobytes()
        conn.execute(
            """INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
               VALUES (?,?,?,?,?,?)""",
            (f"e-{media_id}", item, MODALITY_REGION, pack, OUTPUT_DIM, blob),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        "semblon.region_search.active_pack",
        lambda root=None: (pack, OUTPUT_DIM),
    )
    ids, status = shortlist_media_by_cls(
        store,
        query.astype(np.float32).tobytes(),
        exclude_media_id="m-query",
        limit=2,
    )
    assert status == "ok"
    assert ids[0] == "m-near"
    assert "m-query" not in ids
