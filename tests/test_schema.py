"""Schema smoke tests — Contracts V1.1-corrected."""

from __future__ import annotations

import sqlite3
import struct

import pytest

from semblon.compare import CompareError, compare
from semblon.store import init_db


def _conn(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "t.sqlite"))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


def _run(conn, run_id="r1"):
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (run_id, "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )


def test_init(tmp_path):
    conn = _conn(tmp_path)
    ver = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    assert ver[0] == "1"


def test_duplicate_sha256(tmp_path):
    conn = _conn(tmp_path)
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','abc',1,1,0,1)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO media VALUES ('m2','folder','/b.jpg','abc',1,1,0,1)")


def test_orphan_cluster_fk(tmp_path):
    conn = _conn(tmp_path)
    _run(conn)
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',10,10,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,cluster_id)
               VALUES ('f1','o1','r1',0,0,10,10,0.9,10,10,'80-119','ok','missing')"""
        )


def test_stills_unique_per_run(tmp_path):
    conn = _conn(tmp_path)
    _run(conn)
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',10,10,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO observations VALUES ('o2','m1',NULL,NULL,'r1')")


def test_embedding_length_check(tmp_path):
    conn = _conn(tmp_path)
    _run(conn)
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',10,10,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    bad = b"\x00\x00"
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES ('f1','o1','r1',0,0,10,10,0.9,10,10,'80-119','ok',?,'pack-a',2)""",
            (bad,),
        )


def test_eval_pair_canonical(tmp_path):
    conn = _conn(tmp_path)
    _run(conn)
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',10,10,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    for fid in ("fa", "fb"):
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status)
               VALUES (?, 'o1','r1',0,0,10,10,0.9,10,10,'80-119','rejected')""",
            (fid,),
        )
    conn.execute("INSERT INTO eval_sets VALUES ('e1','confirmatory_hard',1,'pack-a','')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO eval_pairs VALUES ('e1','fb','fa','different','lookalike')")


def test_compare_rejects():
    blob = struct.pack("<2f", 1.0, 0.0)
    with pytest.raises(CompareError):
        compare("a", 2, blob, "b", 2, blob)
    with pytest.raises(CompareError):
        compare("a", 2, blob, "a", 3, blob)
    with pytest.raises(CompareError):
        compare("a", 2, None, "a", 2, blob)
    assert compare("a", 2, blob, "a", 2, blob) == pytest.approx(1.0)
