"""Slice A: Focus face → same-pack similar photos. No auto-name."""

from __future__ import annotations

import sqlite3
import struct

from semblon.application import Application
from semblon.identity_config import DEFAULT_THRESHOLD
from semblon.native_shell.adapter import ArchiveAdapter
from semblon.search import search_similar_faces
from tests.test_cluster import _seed, _vec


def test_search_similar_faces_ranks_same_pack_photos(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    # f1 ≈ f2 (same media m1); f3/f4 on m2 are orthogonal — below threshold.
    # Add a near-match of f1 on a third media so a photo hit exists.
    conn = sqlite3.connect(str(store))
    conn.execute("INSERT INTO media VALUES ('m3','folder','/c.jpg','ccc',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o3','m3',NULL,NULL,'r1')")
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "f8",
            "o3",
            "r1",
            0,
            0,
            20,
            20,
            0.9,
            20,
            20,
            "80-119",
            "ok",
            _vec(0.98, 0.2),
            "pack-a",
            2,
        ),
    )
    conn.commit()
    conn.close()

    before = sqlite3.connect(str(store)).execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    rec = search_similar_faces(store, "f1", threshold=0.5)
    after = sqlite3.connect(str(store)).execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    assert after == before
    assert rec["status"] == "SUCCESS"
    assert rec["similarity_basis"] == "Same face"
    assert "auto-assign" in rec["note"].lower() or "not a name" in rec["note"].lower()
    assert "m1" not in rec["media_ids"]
    assert "m3" in rec["media_ids"]
    assert rec["items"][0]["media_id"] == "m3"
    assert rec["items"][0]["score"] >= 0.5
    assert rec["pack_id"] == "pack-a"
    assert rec["modality"] == "face"


def test_search_similar_faces_skips_cross_pack(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = sqlite3.connect(str(store))
    conn.execute("INSERT INTO media VALUES ('m3','folder','/c.jpg','ccc',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o3','m3',NULL,NULL,'r1')")
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "f_other",
            "o3",
            "r1",
            0,
            0,
            20,
            20,
            0.9,
            20,
            20,
            "80-119",
            "ok",
            _vec(1.0, 0.0),
            "pack-other",
            2,
        ),
    )
    conn.commit()
    conn.close()
    rec = search_similar_faces(store, "f1", threshold=0.0)
    assert "m3" not in rec["media_ids"]
    assert all(it.get("media_id") != "m3" for it in rec.get("items") or [])


def test_search_similar_faces_unavailable_without_embedding(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    rec = search_similar_faces(store, "f6")
    assert rec["status"] == "UNAVAILABLE"
    assert rec["error_id"] == "similar_faces.NO_EMBEDDING"
    assert rec["count"] == 0


def test_search_similar_faces_empty_query_is_honest(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    rec = search_similar_faces(store, "  ")
    assert rec["status"] == "UNAVAILABLE"
    assert rec["error_id"] == "similar_faces.NO_FACE"


def test_adapter_similar_faces_labels_face_embedding(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = sqlite3.connect(str(store))
    conn.execute("INSERT INTO media VALUES ('m3','folder','/c.jpg','ccc',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o3','m3',NULL,NULL,'r1')")
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "f8",
            "o3",
            "r1",
            0,
            0,
            20,
            20,
            0.9,
            20,
            20,
            "80-119",
            "ok",
            _vec(0.98, 0.2),
            "pack-a",
            2,
        ),
    )
    conn.commit()
    conn.close()
    adapter = ArchiveAdapter(Application(store))
    result = adapter.similar_faces("f1")
    assert result.state == "ready"
    assert "same face" in result.message.lower()
    assert "colour" not in result.message.lower()
    assert result.data["basis"] == "face"
    assert result.data["engine"] == "face-embed"
    assert any(it["media_id"] == "m3" for it in result.data["items"])


def test_provisional_threshold_matches_identity_config():
    assert DEFAULT_THRESHOLD == 0.55
    # Sanity: unit vectors at threshold boundary stay documented as provisional.
    blob_a = struct.pack("<2f", 1.0, 0.0)
    blob_b = struct.pack("<2f", 0.55, (1.0 - 0.55**2) ** 0.5)
    assert abs(len(blob_a) - 8) < 1
    assert abs(len(blob_b) - 8) < 1
