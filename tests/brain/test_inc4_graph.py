"""Inc 4: Tag/ObjectCluster graph, batch DBSCAN, no eval rows for clusters."""

from __future__ import annotations

import json
import math
import struct

import numpy as np
import pytest

from semblon.brain.adoption import adopt_existing_object_dbscan
from semblon.brain.confidence import CONFIDENCE_MODEL_VERSION, object_cluster_status
from semblon.brain.edges import INC4_EDGE_TYPES, VALID_EDGE_TYPES, require_edge_type
from semblon.brain.evidence import record_observations
from semblon.brain.graph import sync_tags_from_observations
from semblon.brain.object_cluster import rebuild_object_clusters
from semblon.brain.observation import Observation
from semblon.brain.registry import CapabilityRegistry
from semblon.store import SCHEMA_VERSION, connect, init_db


def _seed(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('run-brain','t','0.0.1','pack-region',4,'l2','{}','{}','x64','native')"""
    )
    for mid, path, sha in (
        ("m1", "/a.jpg", "sha-a"),
        ("m2", "/b.jpg", "sha-b"),
        ("m3", "/c.jpg", "sha-c"),
    ):
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,10,10,0,1)",
            (mid, "folder", path, sha),
        )
    conn.commit()
    return conn


def _l2_blob(theta: float, dim: int = 4) -> bytes:
    vals = [0.0] * dim
    vals[0] = math.cos(theta)
    vals[1] = math.sin(theta)
    return struct.pack(f"<{dim}f", *vals)


def _add_c1(conn, media_id: str, tags: list[dict]):
    record_observations(
        conn,
        [
            Observation(
                photo_id=media_id,
                capability_id="C1",
                provider_name="existing_nanodet_tags",
                model_pack_hash="nanodet",
                payload={"tags": tags},
                confidence=0.9,
            )
        ],
        run_id="run-brain",
        write_tagged=True,
    )


def _add_region_embedding(conn, *, media_id: str, item_id: str, blob: bytes, pack="pack-region"):
    obs_id = f"o-{item_id}"
    conn.execute(
        "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,NULL,NULL,?)",
        (obs_id, media_id, "run-brain"),
    )
    conn.execute(
        """INSERT INTO observation_items(
             item_id, observation_id, run_id, kind, provider, payload_json)
           VALUES (?,?,?,'object','test','{}')""",
        (item_id, obs_id, "run-brain"),
    )
    dim = len(blob) // 4
    conn.execute(
        """INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
           VALUES (?,?,?,?,?,?)""",
        (f"e-{item_id}", item_id, "region", pack, dim, blob),
    )
    conn.commit()


def test_schema_12_graph_tables(tmp_path):
    conn = _seed(tmp_path)
    try:
        assert SCHEMA_VERSION == "12"
        tables = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "brain_nodes" in tables and "brain_edges" in tables
        assert "brain_gaps" not in tables
        triggers = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        }
        assert "trg_erasure_brain_nodes_bd" in triggers
        assert "trg_erasure_brain_edges_bd" in triggers
    finally:
        conn.close()


def test_edge_type_text_not_check_constrained(tmp_path):
    assert "HAS_TAG" in INC4_EDGE_TYPES
    assert "CO_OCCURS" in VALID_EDGE_TYPES
    require_edge_type("HAS_OBJECT")
    with pytest.raises(ValueError):
        require_edge_type("NOT_A_TYPE")
    # SQLite accepts any TEXT edge_type — app frozenset is the gate
    conn = _seed(tmp_path)
    try:
        now = "t"
        conn.execute(
            """INSERT INTO brain_nodes(
                 node_type, label, confidence, status, first_seen, last_seen,
                 member_count, confidence_model_version, created_at, updated_at)
               VALUES ('Photo','mx',1.0,'confirmed',?,?,0,1,?,?)""",
            (now, now, now, now),
        )
        a = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO brain_nodes(
                 node_type, label, confidence, status, first_seen, last_seen,
                 member_count, confidence_model_version, created_at, updated_at)
               VALUES ('Tag','cat',0.5,'candidate',?,?,0,1,?,?)""",
            (now, now, now, now),
        )
        b = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO brain_edges(
                 source_node_id, target_node_id, edge_type, confidence,
                 support_count, contradict_count, first_seen, last_seen,
                 contradiction_state, created_at, updated_at)
               VALUES (?,?, 'CO_OCCURS', 1.0, 1, 0, ?,?, 'none',?,?)""",
            (a, b, now, now, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def test_shared_tag_node_across_photos(tmp_path):
    conn = _seed(tmp_path)
    try:
        _add_c1(conn, "m1", [{"label": "Dog", "score": 0.9}])
        _add_c1(conn, "m2", [{"label": "dog", "score": 0.8}])
        stats = sync_tags_from_observations(conn)
        assert stats["tags"] == 1
        assert stats["photos"] == 2
        assert stats["has_tag_edges"] == 2
        tag = conn.execute(
            "SELECT label, member_count, confidence_model_version FROM brain_nodes WHERE node_type='Tag'"
        ).fetchone()
        assert tag[0] == "dog"
        assert tag[1] >= 2
        assert tag[2] == CONFIDENCE_MODEL_VERSION
        # Graph state is not an evaluation
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM identify_evaluations WHERE outcome NOT IN ('tagged','suggested','ACCEPT','UNKNOWN')"
            ).fetchone()[0]
            == 0
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM identify_evaluations WHERE reason LIKE '%cluster%'"
            ).fetchone()[0]
            == 0
        )
    finally:
        conn.close()


def test_singleton_object_cluster_candidate(tmp_path):
    conn = _seed(tmp_path)
    try:
        _add_region_embedding(conn, media_id="m1", item_id="i1", blob=_l2_blob(0.0))
        stats = rebuild_object_clusters(conn)
        assert stats["clusters"] == 1
        assert stats["members"] == 1
        row = conn.execute(
            """SELECT member_count, status, canonical_embedding, embedding_pack_hash,
                      confidence_model_version
                 FROM brain_nodes WHERE node_type='ObjectCluster'"""
        ).fetchone()
        assert row[0] == 1
        assert row[1] == object_cluster_status(1) == "candidate"
        assert row[2] is not None and len(row[2]) == 4  # int8 x dim4
        assert row[3] == "pack-region"
        assert row[4] == CONFIDENCE_MODEL_VERSION
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM brain_edges WHERE edge_type='HAS_OBJECT'"
            ).fetchone()[0]
            == 1
        )
        # No new evaluation outcome for clustering
        before = conn.execute("SELECT COUNT(*) FROM identify_evaluations").fetchone()[0]
        rebuild_object_clusters(conn)
        after = conn.execute("SELECT COUNT(*) FROM identify_evaluations").fetchone()[0]
        assert after == before
    finally:
        conn.close()


def test_object_dbscan_merges_similar_regions(tmp_path):
    conn = _seed(tmp_path)
    try:
        # Two near-identical vectors → one cluster; one orthogonal → singleton
        _add_region_embedding(conn, media_id="m1", item_id="i1", blob=_l2_blob(0.0))
        _add_region_embedding(conn, media_id="m2", item_id="i2", blob=_l2_blob(0.05))
        _add_region_embedding(conn, media_id="m3", item_id="i3", blob=_l2_blob(math.pi / 2))
        stats = rebuild_object_clusters(conn, eps=0.35, min_samples=2)
        assert stats["clusters"] == 2  # one pair + one singleton
        counts = sorted(
            r[0]
            for r in conn.execute(
                "SELECT member_count FROM brain_nodes WHERE node_type='ObjectCluster'"
            )
        )
        assert counts == [1, 2]
    finally:
        conn.close()


def _snapshot_tag(conn, label: str):
    row = conn.execute(
        """SELECT n.member_count, n.confidence, n.status,
                  (SELECT COUNT(*) FROM brain_edges e
                    WHERE e.target_node_id = n.id AND e.edge_type='HAS_TAG'),
                  (SELECT COALESCE(MAX(e.support_count), 0) FROM brain_edges e
                    WHERE e.target_node_id = n.id AND e.edge_type='HAS_TAG')
             FROM brain_nodes n
            WHERE n.node_type='Tag' AND n.label=?""",
        (label,),
    ).fetchone()
    return None if row is None else tuple(row)


def _has_tag(conn, media_id: str, label: str) -> bool:
    row = conn.execute(
        """SELECT 1
             FROM brain_edges e
             JOIN brain_nodes photo ON photo.id = e.source_node_id
             JOIN brain_nodes tag ON tag.id = e.target_node_id
            WHERE e.edge_type='HAS_TAG'
              AND photo.node_type='Photo' AND photo.label=?
              AND tag.node_type='Tag' AND tag.label=?""",
        (media_id, label),
    ).fetchone()
    return row is not None


def test_sync_tags_is_idempotent(tmp_path):
    conn = _seed(tmp_path)
    try:
        _add_c1(conn, "m1", [{"label": "dog", "score": 0.9}])
        _add_c1(conn, "m2", [{"label": "dog", "score": 0.8}])
        sync_tags_from_observations(conn, "m1")
        sync_tags_from_observations(conn, "m2")
        snap1 = _snapshot_tag(conn, "dog")
        assert snap1 is not None
        assert snap1[0] == 2
        assert snap1[1] == pytest.approx(0.7)
        assert snap1[3] == 2
        assert snap1[4] == 1

        sync_tags_from_observations(conn, "m1")
        sync_tags_from_observations(conn, "m2")
        assert _snapshot_tag(conn, "dog") == snap1

        sync_tags_from_observations(conn)
        assert _snapshot_tag(conn, "dog") == snap1
    finally:
        conn.close()


def test_sync_tags_removes_stale_edges(tmp_path):
    conn = _seed(tmp_path)
    try:
        _add_c1(
            conn,
            "m1",
            [{"label": "dog", "score": 0.9}, {"label": "cat", "score": 0.8}],
        )
        sync_tags_from_observations(conn, "m1")
        assert _has_tag(conn, "m1", "dog")
        assert _has_tag(conn, "m1", "cat")

        conn.execute(
            "UPDATE brain_observations SET payload_json=? WHERE media_id='m1'",
            (json.dumps({"tags": [{"label": "dog", "score": 0.9}]}),),
        )
        conn.commit()
        sync_tags_from_observations(conn, "m1")

        assert _has_tag(conn, "m1", "dog")
        assert not _has_tag(conn, "m1", "cat")
        dog = _snapshot_tag(conn, "dog")
        cat = _snapshot_tag(conn, "cat")
        assert dog is not None and dog[0] == 1 and dog[1] == pytest.approx(0.6)
        assert dog[2] == "candidate"
        assert dog[4] == 1
        assert cat is not None and cat[0] == 0 and cat[2] == "retracted" and cat[3] == 0

        conn.execute(
            "UPDATE brain_observations SET payload_json=? WHERE media_id='m1'",
            (
                json.dumps(
                    {
                        "tags": [
                            {"label": "dog", "score": 0.9},
                            {"label": "cat", "score": 0.8},
                        ]
                    }
                ),
            ),
        )
        conn.commit()
        sync_tags_from_observations(conn, "m1")
        cat_back = _snapshot_tag(conn, "cat")
        assert cat_back is not None
        assert cat_back[0] == 1
        assert cat_back[2] == "candidate"
        assert _has_tag(conn, "m1", "cat")
    finally:
        conn.close()


def test_adopt_object_dbscan_unmeasured(tmp_path):
    conn = _seed(tmp_path)
    try:
        reg = CapabilityRegistry(conn)
        reg.seed_baselines()
        assert all(
            not r.adopted
            for r in reg.list_for("C5")
            if r.provider_name == "existing_object_dbscan"
        )
        bid = adopt_existing_object_dbscan(conn)
        adopted = reg.adopted_provider("C5")
        assert adopted is not None
        assert adopted.provider_name == "existing_object_dbscan"
        assert adopted.benchmark_run_id == bid
        # hdbscan stays dormant
        assert all(
            not r.adopted for r in reg.list_for("C5") if r.provider_name == "hdbscan"
        )
    finally:
        conn.close()
