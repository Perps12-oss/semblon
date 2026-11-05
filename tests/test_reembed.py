"""Re-embed contract: fail-closed writes; invalidate identify_evaluations."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.identify import identify_face
from semblon.reembed import _contract_blob, reembed_stills
from semblon.review import name_cluster
from semblon.store import init_db
from tests.test_review import _clustered


def test_contract_blob_rejects_non_unit_l2():
    face = {
        "det_score": 0.99,
        "face_w": 100,
        "face_h": 100,
        "embedding": np.zeros(4, dtype=np.float32),
    }
    status, blob, pack, dim = _contract_blob("pack-a", face)
    assert status == "rejected"
    assert blob is None and pack is None and dim is None


def test_reembed_invalidates_identify_evaluations(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    unknown = identify_face(store, "r1", "f5")
    assert unknown["evaluation_id"]
    conn = sqlite3.connect(str(store))
    before = conn.execute("SELECT COUNT(*) FROM identify_evaluations").fetchone()[0]
    conn.close()
    assert before >= 1

    unit = np.array([1.0, 0.0], dtype=np.float32)

    def fake_embed(_app, _img):
        return [
            {
                "bbox": (0.0, 0.0, 20.0, 20.0),
                "det_score": 0.99,
                "face_w": 20,
                "face_h": 20,
                "embedding": unit,
            }
        ]

    monkeypatch.setattr("semblon.reembed.load_app", lambda *a, **k: object())
    monkeypatch.setattr("semblon.reembed.discover_weight_hashes", lambda: {})
    monkeypatch.setattr("semblon.reembed.pack_id", lambda *a, **k: "pack-re")
    monkeypatch.setattr("semblon.reembed.embed_bgr", fake_embed)

    from semblon.source_integrity import SourceBuffer

    def fake_load(path, *, expected_sha256=None):
        return np.zeros((20, 20, 3), np.uint8), SourceBuffer(
            digest=str(expected_sha256 or "x"),
            data=b"\x00",
            mtime_ns=0,
            byte_size=1,
        )

    monkeypatch.setattr("semblon.source_integrity.load_source_bgr", fake_load)
    photos = tmp_path / "photos"
    photos.mkdir()
    a = photos / "a.jpg"
    b = photos / "b.jpg"
    a.write_bytes(b"jpeg")
    b.write_bytes(b"jpeg")
    conn = sqlite3.connect(str(store))
    conn.execute("UPDATE media SET path=? WHERE media_id='m1'", (str(a),))
    conn.execute("UPDATE media SET path=? WHERE media_id='m2'", (str(b),))
    conn.commit()
    conn.close()

    rec = reembed_stills(store, resume=False, clear_clusters=True, iou_match=0.1)
    assert rec["status"] == "SUCCESS"
    conn = sqlite3.connect(str(store))
    left = conn.execute("SELECT COUNT(*) FROM identify_evaluations").fetchone()[0]
    conn.close()
    assert left == 0
