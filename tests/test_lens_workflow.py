"""One coherent Lens-style local workflow."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import cv2
import numpy as np

from semblon.cli import main
from semblon.observers import APPEARANCE_DIM, APPEARANCE_PACK, color_histogram
from semblon.review import name_cluster
from semblon.search import search_lens_workflow
from tests.test_review import _clustered


def _seed_lens_store(path: Path) -> None:
    assigned = _clustered(path)
    c1 = assigned["f1"]
    name_cluster(path, "r1", c1, "Alice")
    conn = sqlite3.connect(str(path))
    img_a = np.zeros((24, 24, 3), dtype=np.uint8)
    img_a[:, :] = (20, 200, 20)
    img_b = np.zeros((24, 24, 3), dtype=np.uint8)
    img_b[:, :] = (220, 20, 20)
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
        INSERT INTO observation_items(
          item_id, observation_id, run_id, kind, provider, payload_json
        ) VALUES ('obj1','o1','r1','object','opencv-contour',?)
        """,
        (json.dumps({"class": "region"}),),
    )
    conn.execute(
        """
        INSERT INTO observation_items(
          item_id, observation_id, run_id, kind, provider, payload_json
        ) VALUES ('txt1','o1','r1','text','tesseract',?)
        """,
        (json.dumps({"text": "HELLO from lake"}),),
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
    conn.commit()
    conn.close()


def test_search_lens_workflow_sections(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_lens_store(store)
    qimg = tmp_path / "q.jpg"
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    img[:, :] = (20, 200, 20)
    assert cv2.imwrite(str(qimg), img) is True
    rec = search_lens_workflow(store, qimg, modality="appearance", limit=10)
    assert rec["kind"] == "lens_workflow"
    sec = rec["sections"]
    assert sec["similar_images"]
    assert sec["people"]
    assert sec["people"][0]["display_name"] == "Alice"
    assert "face_identity_path" in rec["identity_firewall"]
    assert "Local Lens-style" in rec["note"]


def test_cli_search_lens(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_lens_store(store)
    qimg = tmp_path / "q.jpg"
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    img[:, :] = (20, 200, 20)
    assert cv2.imwrite(str(qimg), img) is True
    assert main(["search", "--store", str(store), "--lens", str(qimg), "--modality", "appearance"]) == 0
