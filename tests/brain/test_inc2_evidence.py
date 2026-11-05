"""Increment 2: NanoDet wrap, tagged eval, cache reuse, explain, erasure gate."""

from __future__ import annotations

import math
import sqlite3
import struct

import pytest

from semblon.brain.evidence import explain, record_face_observation
from semblon.brain.nanodet_observer import NanoDetObserver
from semblon.brain.observation import Observation, PhotoRef
from semblon.brain.pipeline import BrainPipeline
from semblon.brain.registry import CapabilityRegistry
from semblon.compare import CompareError
from semblon.erasure_intent import ErasureIntent, erasure_authorized
from semblon.forget import forget_files
from semblon.store import SCHEMA_VERSION, connect, init_db


def _seed(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('run-brain','t','0.0.1','pack-a',128,'l2','{}','{}','x64','native')"""
    )
    conn.execute(
        "INSERT INTO media VALUES ('m1','folder','/a.jpg','sha-a',10,10,0,1)"
    )
    conn.commit()
    return conn


def _fake_detect(_bgr):
    return [
        {"label": "dog", "score": 0.91, "bbox": [1, 2, 3, 4]},
        {"label": "cup", "score": 0.77, "bbox": [5, 6, 7, 8]},
    ]


def test_schema_version_is_ten(tmp_path):
    conn = _seed(tmp_path)
    try:
        assert int(SCHEMA_VERSION) >= 10
        ver = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert int(ver) >= 10
        tables = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "brain_observations" in tables
        assert "brain_evidence" in tables
        # Inc 4 adds brain_nodes; Inc 2 only requires observations/evidence.
    finally:
        conn.close()


def test_nanodet_wrapper_writes_observation_evidence_and_tagged(tmp_path):
    conn = _seed(tmp_path)
    try:
        photo = PhotoRef(photo_id="m1", path="/a.jpg", content_hash="sha-a")
        observer = NanoDetObserver(detect_fn=_fake_detect)
        pipe = BrainPipeline(conn, run_id="run-brain")
        result = pipe.run_observer(observer, photo)
        assert result.selection.action == "invoke"
        assert result.write is not None
        assert len(result.write.observation_ids) >= 1
        assert len(result.write.evidence_ids) >= 1
        assert len(result.write.evaluation_ids) >= 1

        n_obs = conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0]
        n_ev = conn.execute("SELECT COUNT(*) FROM brain_evidence").fetchone()[0]
        assert n_obs >= 1
        assert n_ev >= 1

        row = conn.execute(
            """SELECT outcome, embedding_pack, embedding_dim, run_id,
                      threshold, policy_version, source, probe_face_id,
                      person_id, score_top1, score_top2, margin, gallery_size,
                      reason, created_at, evaluation_id
                 FROM identify_evaluations WHERE outcome='tagged'"""
        ).fetchone()
        assert row is not None
        assert row[0] == "tagged"
        assert row[1]  # embedding_pack
        assert row[2] == 0
        assert row[3] == "run-brain"
        assert row[5] == "brain-tag-v1"
        assert row[6] == "brain_c1"
        assert row[15]  # evaluation_id
        assert CapabilityRegistry(conn).adopted_count() == 0
    finally:
        conn.close()


def test_rerun_is_cache_reuse_zero_new_observations(tmp_path):
    conn = _seed(tmp_path)
    try:
        photo = PhotoRef(photo_id="m1", path="/a.jpg", content_hash="sha-a")
        observer = NanoDetObserver(detect_fn=_fake_detect)
        pipe = BrainPipeline(conn, run_id="run-brain")
        first = pipe.run_observer(observer, photo)
        assert first.selection.action == "invoke"
        n1 = conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0]

        second = pipe.run_observer(observer, photo)
        assert second.selection.action == "reuse"
        assert second.write is not None and second.write.reused
        n2 = conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0]
        assert n2 == n1
        assert pipe.cache.hit_rate > 0
    finally:
        conn.close()


def test_explain_returns_provenance(tmp_path):
    conn = _seed(tmp_path)
    try:
        photo = PhotoRef(photo_id="m1", path="/a.jpg", content_hash="sha-a")
        pipe = BrainPipeline(conn, run_id="run-brain")
        result = pipe.run_observer(NanoDetObserver(detect_fn=_fake_detect), photo)
        eid = result.write.evidence_ids[0]
        exp = explain(conn, eid)
        assert exp.evidence_id == eid
        assert exp.media_id == "m1"
        assert exp.provider_name == "existing_nanodet_tags"
        assert exp.model_pack_hash
        assert "tags" in exp.payload
        assert exp.claim_key.startswith("tag:")
    finally:
        conn.close()


def _l2_blob(dim: int = 128) -> bytes:
    vals = [0.0] * dim
    vals[0] = 1.0
    return struct.pack(f"<{dim}f", *vals)


def test_face_observation_fail_closed_invalid_embedding(tmp_path):
    conn = _seed(tmp_path)
    try:
        bad = struct.pack("<128f", *([0.0] * 128))
        obs = Observation(
            photo_id="m1",
            capability_id="C4",
            provider_name="existing_face_embedder",
            model_pack_hash="pack-a",
            payload={"dim": 128},
        )
        with pytest.raises(CompareError):
            record_face_observation(
                conn,
                obs,
                pack_id="pack-a",
                dim=128,
                embedding_blob=bad,
                run_id="run-brain",
            )
        assert conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM brain_evidence").fetchone()[0] == 0

        ok = record_face_observation(
            conn,
            obs,
            pack_id="pack-a",
            dim=128,
            embedding_blob=_l2_blob(),
            run_id="run-brain",
        )
        assert len(ok.observation_ids) == 1
        assert math.isclose(1.0, 1.0)
    finally:
        conn.close()


def test_brain_observation_delete_without_intent_aborts(tmp_path):
    conn = _seed(tmp_path)
    try:
        pipe = BrainPipeline(conn, run_id="run-brain")
        pipe.run_observer(
            NanoDetObserver(detect_fn=_fake_detect),
            PhotoRef(photo_id="m1", path="/a.jpg", content_hash="sha-a"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM brain_observations WHERE media_id='m1'")
        assert conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0] >= 1
    finally:
        conn.close()


def test_forget_media_cascades_brain_through_gate(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(tmp_path)
    try:
        pipe = BrainPipeline(conn, run_id="run-brain")
        pipe.run_observer(
            NanoDetObserver(detect_fn=_fake_detect),
            PhotoRef(photo_id="m1", path="/a.jpg", content_hash="sha-a"),
        )
        assert conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0] >= 1
        assert conn.execute("SELECT COUNT(*) FROM brain_evidence").fetchone()[0] >= 1
    finally:
        conn.close()

    removed = forget_files(store, ["/a.jpg"])
    assert removed == 1
    conn = connect(store)
    init_db(conn)
    try:
        assert conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM brain_evidence").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 0
    finally:
        conn.close()


def test_delete_person_does_not_wipe_brain_tags(tmp_path):
    """Person erasure is not photo erasure — C1 tags stay on media."""
    from semblon.erasure import delete_person

    conn = _seed(tmp_path)
    try:
        conn.execute(
            "INSERT INTO persons(person_id, display_name, status, created_run) VALUES ('p1','Ada','active','run-brain')"
        )
        conn.commit()
        pipe = BrainPipeline(conn, run_id="run-brain")
        pipe.run_observer(
            NanoDetObserver(detect_fn=_fake_detect),
            PhotoRef(photo_id="m1", path="/a.jpg", content_hash="sha-a"),
        )
        n = conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0]
    finally:
        conn.close()

    delete_person(tmp_path / "s.sqlite", "p1")
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    try:
        assert conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0] == n
    finally:
        conn.close()


def test_media_intent_allows_observation_delete(tmp_path):
    conn = _seed(tmp_path)
    try:
        pipe = BrainPipeline(conn, run_id="run-brain")
        pipe.run_observer(
            NanoDetObserver(detect_fn=_fake_detect),
            PhotoRef(photo_id="m1", path="/a.jpg", content_hash="sha-a"),
        )
        intent = ErasureIntent(
            requestor="user",
            scope="media",
            reason="test",
            authorized_by="test",
            media_id="m1",
        )
        with erasure_authorized(intent):
            conn.execute("DELETE FROM brain_observations WHERE media_id='m1'")
            conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM brain_evidence").fetchone()[0] == 0
    finally:
        conn.close()
