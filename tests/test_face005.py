"""FACE-005 incremental ingest + inbox — no InsightFace."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.cli import main
from semblon.cluster import cluster_run
from semblon.identify import identify_face, identify_run
from semblon.inbox import inbox
from semblon.ingest import media_skip_reason
from semblon.review import ReviewError, name_cluster, name_face
from semblon.store import init_db
from tests.test_cluster import _seed, _vec
from tests.test_review import _clustered
import pytest


def _conn(store: Path):
    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    return conn


def test_media_skip_seen_across_runs(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    reason, mid = media_skip_reason(conn, "aaa", "r2", reprocess=False)
    assert reason == "seen"
    assert mid == "m1"
    reason, mid = media_skip_reason(conn, "aaa", "r1", reprocess=False)
    assert reason == "same_run"
    reason, _ = media_skip_reason(conn, "aaa", "r2", reprocess=True)
    assert reason is None
    reason, mid = media_skip_reason(conn, "missing-hash", "r2", reprocess=False)
    assert reason is None
    assert mid is None
    conn.close()


def test_identify_gallery_is_cross_run(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")

    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r2", "t2", "1.1.0", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m3','folder','/c.jpg','ccc',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o3','m3',NULL,NULL,'r2')")
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("f-new", "o3", "r2", 0, 0, 20, 20, 0.9, 20, 20, "80-119", "ok", _vec(1.0, 0.0), "pack-a", 2),
    )
    conn.commit()
    conn.close()

    rec = identify_face(store, "r2", "f-new")
    assert rec["decision"] == "ACCEPT"
    assert rec["display_name"] == "Alice"
    conn = _conn(store)
    assert conn.execute("SELECT person_id FROM faces WHERE face_id='f-new'").fetchone()[0] is None
    conn.close()


def test_inbox_buckets_and_name_unassigned_face(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = _conn(store)
    assigned = {
        r["face_id"]: r["cluster_id"]
        for r in conn.execute("SELECT face_id, cluster_id FROM faces WHERE cluster_id IS NOT NULL")
    }
    conn.close()
    name_cluster(store, "r1", assigned["f1"], "Alice")
    identify_run(store, "r1")
    rec = inbox(store, "r1")
    by_id = {i["face_id"]: i["bucket"] for i in rec["items"]}
    assert by_id["f6"] == "REJECTED"
    assert by_id["f7"] == "REVIEW_REQUIRED"
    assert by_id["f1"] == "KNOWN"
    assert by_id["f2"] == "KNOWN"
    assert rec["counts"]["REJECTED"] == 1
    assert rec["counts"]["REVIEW_REQUIRED"] == 1

    named = name_face(store, "r1", "f5", "Solo")
    assert named["created_person"] is True
    assert named["faces_named"] == 1
    rec2 = inbox(store, "r1")
    by_id = {i["face_id"]: i["bucket"] for i in rec2["items"]}
    assert by_id["f5"] == "KNOWN"

    with pytest.raises(ReviewError, match="cluster"):
        name_face(store, "r1", "f1", "Nope")
    assert main(["name", "--face", "f5", "--as", "Solo", "--run", "r1", "--store", str(store)]) == 2
    assert main(["inbox", "--run", "r1", "--store", str(store)]) == 0
    assert main(["name", "--run", "r1", "--store", str(store), "--as", "X"]) == 2


def test_cli_name_requires_cluster_or_face(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    assert (
        main(
            [
                "name",
                "--cluster",
                assigned["f1"],
                "--face",
                "f5",
                "--as",
                "X",
                "--run",
                "r1",
                "--store",
                str(store),
            ]
        )
        == 2
    )
