"""Non-identity retrieval layer and search wiring."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import cv2
import numpy as np
import pytest

from semblon.cli import main
from semblon.observers import APPEARANCE_DIM, APPEARANCE_PACK, color_histogram
from semblon.search import SearchError, search_image, search_text
from tests.test_cluster import _seed


def _seed_retrieval_store(path: Path) -> None:
    conn = _seed(path)
    img_a = np.zeros((16, 16, 3), dtype=np.uint8)
    img_a[:, :] = (20, 200, 20)
    img_b = np.zeros((16, 16, 3), dtype=np.uint8)
    img_b[:, :] = (200, 20, 20)
    emb_a = color_histogram(img_a)
    emb_b = color_histogram(img_b)

    conn.execute(
        """
        INSERT INTO observation_items(
            item_id, observation_id, run_id, kind, provider, payload_json
        ) VALUES ('ia','o1','r1','appearance','color-hist','{}')
        """
    )
    conn.execute(
        """
        INSERT INTO observation_items(
            item_id, observation_id, run_id, kind, provider, payload_json
        ) VALUES ('ib','o2','r1','appearance','color-hist','{}')
        """
    )
    conn.execute(
        """
        INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
        VALUES ('ea','ia','appearance',?,?,?)
        """,
        (APPEARANCE_PACK, APPEARANCE_DIM, emb_a),
    )
    conn.execute(
        """
        INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
        VALUES ('eb','ib','appearance',?,?,?)
        """,
        (APPEARANCE_PACK, APPEARANCE_DIM, emb_b),
    )
    conn.execute(
        """
        INSERT INTO observation_items(
            item_id, observation_id, run_id, kind, provider, payload_json
        ) VALUES ('txt1','o1','r1','text','tesseract',?)
        """,
        (json.dumps({"text": "HELLO from lake"}),),
    )
    conn.commit()
    conn.close()


def test_search_image_prefers_closest_item(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_retrieval_store(store)
    qimg = tmp_path / "query.jpg"
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    img[:, :] = (20, 200, 20)
    assert cv2.imwrite(str(qimg), img) is True
    rec = search_image(store, qimg, modality="appearance", limit=5)
    assert rec["kind"] == "query_image"
    assert rec["count"] >= 1
    assert rec["items"][0]["item_id"] == "ia"
    assert "non-identity" in rec["note"]


def test_search_text_returns_payload_matches(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_retrieval_store(store)
    rec = search_text(store, "lake")
    assert rec["kind"] == "query_text"
    assert rec["count"] == 1
    assert rec["items"][0]["item_id"] == "txt1"


def test_search_image_missing_file_errors(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_retrieval_store(store)
    with pytest.raises(SearchError):
        search_image(store, tmp_path / "missing.jpg")


def test_cli_search_image_and_text(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_retrieval_store(store)
    qimg = tmp_path / "query.jpg"
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    img[:, :] = (20, 200, 20)
    assert cv2.imwrite(str(qimg), img) is True
    assert main(["search", "--store", str(store), "--image", str(qimg), "--modality", "appearance"]) == 0
    assert main(["search", "--store", str(store), "--text", "lake"]) == 0
