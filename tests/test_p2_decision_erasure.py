"""P2 — human decision preservation + ErasureIntent DB enforcement."""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from semblon.category_backfill import _clear_unnamed_faces
from semblon.erasure import delete_person, wipe_library
from semblon.erasure_intent import (
    ErasureIntent,
    erasure_authorized,
    install_erasure_guard,
)
from semblon.native_shell.presentation import decision_success
from semblon.store import SCHEMA_VERSION, connect, init_db


def _vector(n: int = 2) -> bytes:
    v = np.ones(n, dtype=np.float32)
    v /= np.linalg.norm(v)
    return v.tobytes()


def _seed_store(path):
    conn = connect(path)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r1','t','0.0.1','pack-a',2,'l2','{}','{}','x64','native')"""
    )
    conn.execute(
        "INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',10,10,0,1)"
    )
    conn.execute(
        "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id)"
        " VALUES ('o1','m1',NULL,NULL,'r1')"
    )
    conn.commit()
    return conn


def test_schema_version_is_eight(tmp_path):
    conn = _seed_store(tmp_path / "s.sqlite")
    try:
        assert SCHEMA_VERSION == "8"
        ver = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert ver == "8"
        triggers = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
        }
        assert "trg_erasure_persons_bd" in triggers
        assert "trg_erasure_faces_named_bd" in triggers
        assert "trg_erasure_decisions_human_bd" in triggers
    finally:
        conn.close()


def test_human_decision_delete_fails_without_intent(tmp_path):
    conn = _seed_store(tmp_path / "s.sqlite")
    try:
        conn.execute(
            """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
               det_score, face_w, face_h, size_band, status)
               VALUES ('f1','o1','r1',0,0,1,1,0.9,10,10,'ok','ok')"""
        )
        conn.execute(
            """INSERT INTO decisions(decision_id, kind, face_id, person_id, cluster_id, pack_id,
               policy_json, run_id, created_at)
               VALUES ('d1','reject','f1',NULL,NULL,'pack-a','{"action":"rule_out"}','r1','t')"""
        )
        conn.commit()
        with pytest.raises(sqlite3.DatabaseError, match="erasure intent"):
            conn.execute("DELETE FROM decisions WHERE decision_id='d1'")
        assert (
            conn.execute("SELECT COUNT(*) FROM decisions WHERE decision_id='d1'").fetchone()[0]
            == 1
        )
    finally:
        conn.close()


def test_machine_identify_decision_delete_without_intent(tmp_path):
    conn = _seed_store(tmp_path / "s.sqlite")
    try:
        conn.execute(
            """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
               det_score, face_w, face_h, size_band, status)
               VALUES ('f1','o1','r1',0,0,1,1,0.9,10,10,'ok','ok')"""
        )
        conn.execute(
            """INSERT INTO decisions(decision_id, kind, face_id, person_id, cluster_id, pack_id,
               policy_json, run_id, created_at)
               VALUES ('d1','identify','f1',NULL,NULL,'pack-a','{}','r1','t')"""
        )
        conn.commit()
        conn.execute("DELETE FROM decisions WHERE decision_id='d1'")
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    finally:
        conn.close()


def test_named_face_and_person_delete_require_intent(tmp_path):
    conn = _seed_store(tmp_path / "s.sqlite")
    try:
        conn.execute(
            "INSERT INTO persons(person_id, display_name, status) VALUES ('p1','Ada','active')"
        )
        conn.execute(
            """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
               det_score, face_w, face_h, size_band, status, person_id,
               embedding, embedding_pack, embedding_dim)
               VALUES ('f1','o1','r1',0,0,1,1,0.9,10,10,'ok','ok','p1',?,'pack-a',2)""",
            (_vector(),),
        )
        conn.commit()
        with pytest.raises(sqlite3.DatabaseError, match="erasure intent"):
            conn.execute("DELETE FROM faces WHERE face_id='f1'")
        with pytest.raises(sqlite3.DatabaseError, match="erasure intent"):
            conn.execute("DELETE FROM persons WHERE person_id='p1'")
        assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM faces WHERE face_id='f1'").fetchone()[0] == 1
    finally:
        conn.close()


def test_delete_person_with_intent_clears_protected_rows(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed_store(store)
    conn.execute(
        "INSERT INTO persons(person_id, display_name, status) VALUES ('p1','Ada','active')"
    )
    conn.execute(
        """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
           det_score, face_w, face_h, size_band, status, person_id,
           embedding, embedding_pack, embedding_dim)
           VALUES ('f1','o1','r1',0,0,1,1,0.9,10,10,'ok','ok','p1',?,'pack-a',2)""",
        (_vector(),),
    )
    conn.execute(
        """INSERT INTO decisions(decision_id, kind, face_id, person_id, cluster_id, pack_id,
           policy_json, run_id, created_at)
           VALUES ('d1','name','f1','p1',NULL,'pack-a','{}','r1','t')"""
    )
    conn.execute(
        """INSERT INTO identify_evaluations(
             evaluation_id, probe_face_id, embedding_pack, embedding_dim, run_id,
             outcome, reason, threshold, policy_version, person_id, source, created_at)
           VALUES ('e1','f1','pack-a',2,'r1','ACCEPT',NULL,0.5,'v1','p1','test','t')"""
    )
    conn.commit()
    conn.close()

    rec = delete_person(store, "p1")
    assert rec["erased"] is True
    assert rec["faces_deleted"] == 1
    conn = connect(store)
    try:
        assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM identify_evaluations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 1
    finally:
        conn.close()


def test_wipe_library_requires_intent_and_clears_with_it(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed_store(store)
    conn.execute(
        "INSERT INTO persons(person_id, display_name, status) VALUES ('p1','Ada','active')"
    )
    conn.execute(
        """INSERT INTO decisions(decision_id, kind, face_id, person_id, cluster_id, pack_id,
           policy_json, run_id, created_at)
           VALUES ('d1','note',NULL,'p1',NULL,'pack-a','{}','r1','t')"""
    )
    conn.commit()
    with pytest.raises(sqlite3.DatabaseError, match="erasure intent"):
        conn.execute("DELETE FROM persons")
    conn.close()

    wiped = wipe_library(store)
    assert wiped["erased"] is True
    assert wiped["files_deleted"] is False
    conn = connect(store)
    try:
        assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 0
    finally:
        conn.close()


def test_connection_without_guard_cannot_delete_protected_rows(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed_store(store)
    conn.execute(
        "INSERT INTO persons(person_id, display_name, status) VALUES ('p1','Ada','active')"
    )
    conn.commit()
    conn.close()

    raw = sqlite3.connect(str(store))
    raw.execute("PRAGMA foreign_keys=ON")
    try:
        with pytest.raises(sqlite3.DatabaseError):
            raw.execute("DELETE FROM persons WHERE person_id='p1'")
        assert raw.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 1
    finally:
        raw.close()


def test_clear_unnamed_preserves_human_reject(tmp_path):
    conn = _seed_store(tmp_path / "s.sqlite")
    try:
        conn.execute(
            """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
               det_score, face_w, face_h, size_band, status)
               VALUES ('f-reject','o1','r1',0,0,1,1,0.9,10,10,'ok','ok')"""
        )
        conn.execute(
            """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
               det_score, face_w, face_h, size_band, status)
               VALUES ('f-plain','o1','r1',2,2,3,3,0.9,10,10,'ok','ok')"""
        )
        conn.execute(
            """INSERT INTO decisions(decision_id, kind, face_id, person_id, cluster_id, pack_id,
               policy_json, run_id, created_at)
               VALUES ('d-reject','reject','f-reject',NULL,NULL,'pack-a','{"action":"rule_out"}','r1','t')"""
        )
        conn.execute(
            """INSERT INTO decisions(decision_id, kind, face_id, person_id, cluster_id, pack_id,
               policy_json, run_id, created_at)
               VALUES ('d-id','identify','f-plain',NULL,NULL,'pack-a','{}','r1','t')"""
        )
        conn.commit()
        _clear_unnamed_faces(conn, "m1")
        conn.commit()
        faces = {
            r[0]
            for r in conn.execute("SELECT face_id FROM faces").fetchall()
        }
        assert faces == {"f-reject"}
        assert (
            conn.execute(
                "SELECT kind FROM decisions WHERE decision_id='d-reject'"
            ).fetchone()[0]
            == "reject"
        )
        assert (
            conn.execute("SELECT COUNT(*) FROM decisions WHERE decision_id='d-id'").fetchone()[0]
            == 0
        )
    finally:
        conn.close()


def test_person_scope_does_not_authorize_other_person(tmp_path):
    conn = _seed_store(tmp_path / "s.sqlite")
    try:
        conn.execute(
            "INSERT INTO persons(person_id, display_name, status) VALUES ('p1','Ada','active')"
        )
        conn.execute(
            "INSERT INTO persons(person_id, display_name, status) VALUES ('p2','Bob','active')"
        )
        conn.commit()
        intent = ErasureIntent(
            requestor="user",
            scope="person",
            reason="test",
            authorized_by="test",
            person_id="p1",
        )
        with erasure_authorized(intent):
            conn.execute("DELETE FROM persons WHERE person_id='p1'")
            with pytest.raises(sqlite3.DatabaseError, match="erasure intent"):
                conn.execute("DELETE FROM persons WHERE person_id='p2'")
        assert conn.execute("SELECT person_id FROM persons").fetchone()[0] == "p2"
    finally:
        conn.close()


def test_rule_out_copy_does_not_imply_removal():
    text = decision_success("rule_out")
    assert "Nothing was removed" in text
    assert "stop suggesting" in text.lower()


def test_erasure_intent_rejects_incomplete():
    with pytest.raises(ValueError):
        ErasureIntent(
            requestor="user",
            scope="person",
            reason="x",
            authorized_by="test",
            person_id=None,
        )
    with pytest.raises(ValueError):
        ErasureIntent(
            requestor="",
            scope="library",
            reason="x",
            authorized_by="test",
        )


def test_install_guard_is_idempotent(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    install_erasure_guard(conn)
    install_erasure_guard(conn)
    conn.close()
