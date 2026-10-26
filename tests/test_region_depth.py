"""The region encoder can do the whole picture first and the fine detail later."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import numpy as np
import pytest

from semblon import region_encoder as R
from semblon.store import connect, init_db


def _fake_hidden(count: int) -> list[np.ndarray]:
    rng = np.random.default_rng(3)
    return [rng.standard_normal((257, R.OUTPUT_DIM)).astype(np.float32) for _ in range(count)]


def _store(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m','folder','/a.jpg','aaa',300,400,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o','m',NULL,NULL,'r')")
    conn.commit()
    return conn


def _index(conn, depth):
    sizes: list[int] = []

    def encode(images, **_kw):
        sizes.append(len(images))
        return _fake_hidden(len(images))

    image = np.random.default_rng(1).integers(0, 255, (400, 300, 3), dtype=np.uint8)
    with (
        patch.object(R, "probe_region_pack", return_value=(True, "")),
        patch.object(R, "encode_images", side_effect=encode),
        patch.object(R, "proposal_boxes", return_value=[(0.1, 0.1, 0.5, 0.5)]),
    ):
        counts = R.index_image_regions(conn, observation_id="o", run_id="r", img=image, depth=depth)
    conn.commit()
    return counts, sizes


def _rows(conn, modality):
    return conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality=?", (modality,)).fetchone()[0]


def test_frame_depth_encodes_one_piece_and_stores_the_scene(tmp_path):
    conn = _store(tmp_path)
    counts, sizes = _index(conn, R.DEPTH_FRAME)
    assert sizes == [1]
    assert counts["scene"] == 1 and counts["patch"] > 0 and counts["region"] == 0
    assert _rows(conn, R.MODALITY_SCENE) == 1
    assert _rows(conn, R.MODALITY_REGION) == 0


def test_detail_after_frame_adds_the_rest_without_a_second_scene(tmp_path):
    conn = _store(tmp_path)
    _index(conn, R.DEPTH_FRAME)
    frame_patches = _rows(conn, R.MODALITY_PATCH)
    counts, sizes = _index(conn, R.DEPTH_DETAIL)
    assert sizes[0] == counts["jobs"] > 1
    assert counts["scene"] == 0
    assert _rows(conn, R.MODALITY_SCENE) == 1
    assert _rows(conn, R.MODALITY_PATCH) > frame_patches


def test_frame_then_detail_stores_what_full_stores(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    conn_a = _store(a)
    conn_b = _store(b)
    _index(conn_a, R.DEPTH_FRAME)
    _index(conn_a, R.DEPTH_DETAIL)
    _index(conn_b, R.DEPTH_FULL)
    for modality in (R.MODALITY_SCENE, R.MODALITY_REGION, R.MODALITY_PATCH):
        assert _rows(conn_a, modality) == _rows(conn_b, modality)


def test_unknown_depth_is_rejected(tmp_path):
    conn = _store(tmp_path)
    with pytest.raises(ValueError):
        R.index_image_regions(conn, observation_id="o", run_id="r", img=np.zeros((9, 9, 3)), depth="x")


def test_sqlite_is_usable_after_depth_passes(tmp_path):
    conn = _store(tmp_path)
    _index(conn, R.DEPTH_FULL)
    assert isinstance(conn, sqlite3.Connection)
