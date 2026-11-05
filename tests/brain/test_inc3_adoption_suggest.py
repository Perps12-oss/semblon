"""Inc 3: NanoDet first-adoption + FaceSuggest suggested band."""

from __future__ import annotations

import math
import sqlite3
import struct

import pytest

from semblon.brain.adoption import UNMEASURED, adopt_existing_nanodet_tags
from semblon.brain.face_suggest import FaceSuggestObserver, run_face_suggest
from semblon.brain.observation import Observation, PhotoRef
from semblon.brain.registry import CapabilityRegistry
from semblon.brain.suggest_policy import (
    CONFIRM_THRESHOLD,
    SUGGEST_FLOOR,
    SUGGEST_POLICY_VERSION,
)
from semblon.compare import CompareError
from semblon.erasure_intent import ErasureIntent, erasure_authorized
from semblon.identity_config import DEFAULT_THRESHOLD
from semblon.store import SCHEMA_VERSION, connect, init_db


PACK = "opencv/yunet_sface@test"
DIM = 128


def _blob_at_angle(theta: float, dim: int = DIM) -> bytes:
    vals = [0.0] * dim
    vals[0] = math.cos(theta)
    vals[1] = math.sin(theta)
    return struct.pack(f"<{dim}f", *vals)


def _seed(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('run-brain','t','0.0.1',?,?, 'l2','{}','{}','x64','native')""",
        (PACK, DIM),
    )
    conn.execute(
        "INSERT INTO media VALUES ('m1','folder','/a.jpg','sha-a',10,10,0,1)"
    )
    conn.execute(
        "INSERT INTO media VALUES ('m2','folder','/b.jpg','sha-b',10,10,0,1)"
    )
    conn.commit()
    return conn


def _insert_confirmed_person(conn, *, person_id: str, face_id: str, blob: bytes):
    conn.execute(
        "INSERT INTO persons(person_id, display_name, status, created_run) VALUES (?,?,?,?)",
        (person_id, "Ada", "active", "run-brain"),
    )
    conn.execute(
        "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
        (f"o-{face_id}", "m2", None, None, "run-brain"),
    )
    conn.execute(
        """INSERT INTO faces(
             face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
             det_score, face_w, face_h, size_band, status,
             embedding, embedding_pack, embedding_dim, person_id)
           VALUES (?,?,?,0,0,10,10,0.99,10,10,'80-119','ok',?,?,?,?)""",
        (face_id, f"o-{face_id}", "run-brain", blob, PACK, DIM, person_id),
    )
    conn.commit()


def test_schema_version_is_eleven(tmp_path):
    conn = _seed(tmp_path)
    try:
        assert int(SCHEMA_VERSION) >= 11
        ver = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert int(ver) >= 11
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='identify_evaluations'"
        ).fetchone()[0]
        assert "'ACCEPT'" in ddl and "'UNKNOWN'" in ddl
        assert "'tagged'" in ddl and "'suggested'" in ddl
        # Inc 4 adds brain_nodes; Inc 3 only requires outcome CHECK widen.
    finally:
        conn.close()


def test_confirm_threshold_untouched():
    assert CONFIRM_THRESHOLD == DEFAULT_THRESHOLD
    assert SUGGEST_FLOOR < CONFIRM_THRESHOLD


def test_nanodet_adoption_requires_benchmark_row(tmp_path):
    conn = _seed(tmp_path)
    try:
        reg = CapabilityRegistry(conn)
        reg.seed_baselines()
        assert reg.adopted_count() == 0
        with pytest.raises(ValueError, match="benchmark"):
            reg.adopt("C1", "existing_nanodet_tags", benchmark_run_id=99999)

        bid = adopt_existing_nanodet_tags(conn)
        assert reg.adopted_count() == 1
        row = conn.execute(
            """SELECT coverage, quality, latency_p50_ms, latency_p95_ms
                 FROM brain_benchmarks WHERE id=?""",
            (bid,),
        ).fetchone()
        assert row[0] == UNMEASURED
        assert row[1] is None
        assert row[2] is None
        assert row[3] is None
        cap = reg.adopted_provider("C1")
        assert cap is not None
        assert cap.provider_name == "existing_nanodet_tags"
        assert cap.benchmark_run_id == bid

        # Candidates remain dormant
        names = {r.provider_name: r.adopted for r in reg.list_for("C1")}
        assert names.get("ram_plus") is False
        for cap_id in ("C2", "C4", "C5"):
            for r in reg.list_for(cap_id):
                if r.provider_kind == "brain_model":
                    assert r.adopted is False
    finally:
        conn.close()


def test_empty_library_zero_suggested_only_observations(tmp_path):
    conn = _seed(tmp_path)
    try:
        observer = FaceSuggestObserver(pack_id=PACK, dim=DIM)
        photo = PhotoRef(photo_id="m1", content_hash="sha-a")
        probe = _blob_at_angle(0.0)
        result = run_face_suggest(
            conn, observer, photo, run_id="run-brain", embedding_blob=probe
        )
        assert len(result.observation_ids) == 1
        assert result.evaluation_ids == []
        n = conn.execute(
            "SELECT COUNT(*) FROM identify_evaluations WHERE outcome='suggested'"
        ).fetchone()[0]
        assert n == 0
        assert conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0] == 1
    finally:
        conn.close()


def test_synthetic_person_produces_suggested_row(tmp_path):
    conn = _seed(tmp_path)
    try:
        # Gallery at angle 0; probe at acos(0.50) → score ~0.50 in [0.40, 0.55)
        gallery = _blob_at_angle(0.0)
        probe = _blob_at_angle(math.acos(0.50))
        _insert_confirmed_person(conn, person_id="p1", face_id="f1", blob=gallery)

        observer = FaceSuggestObserver(pack_id=PACK, dim=DIM)
        photo = PhotoRef(photo_id="m1", content_hash="sha-a")
        result = run_face_suggest(
            conn, observer, photo, run_id="run-brain", embedding_blob=probe
        )
        assert len(result.evaluation_ids) == 1

        row = conn.execute(
            """SELECT outcome, reason, threshold, policy_version,
                      score_top1, person_id, embedding_pack, embedding_dim,
                      run_id, source, gallery_size, score_top2, margin,
                      probe_face_id, created_at, evaluation_id
                 FROM identify_evaluations WHERE outcome='suggested'"""
        ).fetchone()
        assert row is not None
        assert row[0] == "suggested"
        assert "below_confirm_threshold" in row[1]
        assert f"confirm={CONFIRM_THRESHOLD}" in row[1]
        assert f"suggest_floor={SUGGEST_FLOOR}" in row[1]
        assert row[2] == SUGGEST_FLOOR
        assert row[3] == SUGGEST_POLICY_VERSION
        assert SUGGEST_FLOOR <= float(row[4]) < CONFIRM_THRESHOLD
        assert row[5] == "p1"

        # Firewall: faces.person_id on the probe media unchanged (no probe face row);
        # gallery face still named; decisions empty of brain writes.
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
        named = conn.execute(
            "SELECT person_id FROM faces WHERE face_id='f1'"
        ).fetchone()[0]
        assert named == "p1"
    finally:
        conn.close()


def test_suggest_cache_hit_zero_new_evaluations(tmp_path):
    conn = _seed(tmp_path)
    try:
        gallery = _blob_at_angle(0.0)
        probe = _blob_at_angle(math.acos(0.50))
        _insert_confirmed_person(conn, person_id="p1", face_id="f1", blob=gallery)
        observer = FaceSuggestObserver(pack_id=PACK, dim=DIM)
        photo = PhotoRef(photo_id="m1", content_hash="sha-a")
        first = run_face_suggest(
            conn, observer, photo, run_id="run-brain", embedding_blob=probe
        )
        assert first.evaluation_ids
        n1 = conn.execute(
            "SELECT COUNT(*) FROM identify_evaluations WHERE outcome='suggested'"
        ).fetchone()[0]
        second = run_face_suggest(
            conn, observer, photo, run_id="run-brain", embedding_blob=probe
        )
        assert second.reused is True
        n2 = conn.execute(
            "SELECT COUNT(*) FROM identify_evaluations WHERE outcome='suggested'"
        ).fetchone()[0]
        assert n2 == n1
    finally:
        conn.close()


def test_invalid_embedding_fail_closed(tmp_path):
    conn = _seed(tmp_path)
    try:
        bad = struct.pack(f"<{DIM}f", *([0.0] * DIM))
        observer = FaceSuggestObserver(pack_id=PACK, dim=DIM)
        with pytest.raises(CompareError):
            run_face_suggest(
                conn,
                observer,
                PhotoRef(photo_id="m1", content_hash="sha-a"),
                run_id="run-brain",
                embedding_blob=bad,
            )
        assert conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM brain_evidence").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM identify_evaluations").fetchone()[0] == 0
    finally:
        conn.close()


def test_face_observation_erasure_gate_not_silent_cascade(tmp_path):
    """MIGRATION_10 trigger covers brain_observations — face path included."""
    conn = _seed(tmp_path)
    try:
        triggers = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            )
        }
        assert "trg_erasure_brain_observations_bd" in triggers

        observer = FaceSuggestObserver(pack_id=PACK, dim=DIM)
        run_face_suggest(
            conn,
            observer,
            PhotoRef(photo_id="m1", content_hash="sha-a"),
            run_id="run-brain",
            embedding_blob=_blob_at_angle(0.0),
        )
        assert conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0] == 1

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM brain_observations WHERE media_id='m1'")

        intent = ErasureIntent(
            requestor="user",
            scope="media",
            reason="test face path erasure",
            authorized_by="test",
            media_id="m1",
        )
        with erasure_authorized(intent):
            conn.execute("DELETE FROM brain_observations WHERE media_id='m1'")
            conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM brain_observations").fetchone()[0] == 0
    finally:
        conn.close()


def test_score_at_or_above_confirm_does_not_suggest(tmp_path):
    conn = _seed(tmp_path)
    try:
        gallery = _blob_at_angle(0.0)
        # Identical → score 1.0 >= confirm → P1 path owns ACCEPT; no suggested
        _insert_confirmed_person(conn, person_id="p1", face_id="f1", blob=gallery)
        result = run_face_suggest(
            conn,
            FaceSuggestObserver(pack_id=PACK, dim=DIM),
            PhotoRef(photo_id="m1", content_hash="sha-a"),
            run_id="run-brain",
            embedding_blob=gallery,
        )
        assert result.observation_ids
        assert result.evaluation_ids == []
    finally:
        conn.close()
