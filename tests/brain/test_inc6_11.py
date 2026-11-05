"""Inc 6–11: reserved edges, scene gaps, and centroid assignment.

Schema stays 12. No new model. No person_id writes. No brain_gaps table.
"""

from __future__ import annotations

import struct
from pathlib import Path

from semblon.brain.cooccur import rebuild_cooccurs
from semblon.brain.evidence import record_observations
from semblon.brain.face_link import link_faces
from semblon.brain.graph import ensure_labeled_node, ensure_photo_node, sync_tags_from_observations
from semblon.brain.object_cluster import approximate_predict, rebuild_object_clusters
from semblon.brain.observation import Observation
from semblon.brain.quantize import mean_l2_int8
from semblon.brain.same_as import link_same_as
from semblon.brain.scene_link import brain_gaps, link_scenes
from semblon.brain.temporal import rebuild_temporal_next
from semblon.store import SCHEMA_VERSION, connect, init_db


def _vec(axis: int, dim: int = 4) -> bytes:
    vals = [0.0] * dim
    vals[axis] = 1.0
    return struct.pack(f"<{dim}f", *vals)


def _seed(tmp_path):
    conn = connect(tmp_path / "g.sqlite")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('run-brain','t','0.0.1','pack',4,'l2','{}','{}','x64','emulated')"""
    )
    conn.execute(
        "INSERT INTO media VALUES ('m1','folder','/a.jpg','sha-a',10,10,10,1)"
    )
    conn.execute(
        "INSERT INTO media VALUES ('m2','folder','/b.jpg','sha-b',10,10,30,1)"
    )
    conn.execute(
        "INSERT INTO media VALUES ('m3','folder','/c.jpg','sha-c',10,10,20,1)"
    )
    conn.commit()
    return conn


def _tags(conn, media_id: str, labels: list[str]) -> None:
    record_observations(
        conn,
        [
            Observation(
                photo_id=media_id,
                capability_id="C1",
                provider_name="existing_nanodet_tags",
                model_pack_hash=f"pack-{media_id}",
                payload={"tags": [{"label": label, "score": 0.9} for label in labels]},
                confidence=0.9,
            )
        ],
        run_id="run-brain",
        write_tagged=True,
    )
    sync_tags_from_observations(conn, media_id)


def test_schema_stays_12(tmp_path):
    conn = _seed(tmp_path)
    try:
        assert SCHEMA_VERSION == "12"
    finally:
        conn.close()


def test_temporal_orders_by_mtime(tmp_path):
    conn = _seed(tmp_path)
    try:
        for media_id in ("m1", "m2", "m3"):
            ensure_photo_node(conn, media_id)
        conn.commit()
        first = rebuild_temporal_next(conn)
        second = rebuild_temporal_next(conn)
        assert first == {"photos": 3, "edges": 2}
        assert second["edges"] == 2
        rows = conn.execute(
            """
            SELECT src.label, dst.label
              FROM brain_edges e
              JOIN brain_nodes src ON src.id = e.source_node_id
              JOIN brain_nodes dst ON dst.id = e.target_node_id
             WHERE e.edge_type='TEMPORAL_NEXT'
             ORDER BY src.label
            """
        ).fetchall()
        # mtimes: m1=10, m3=20, m2=30.
        assert [(row[0], row[1]) for row in rows] == [("m1", "m3"), ("m3", "m2")]
    finally:
        conn.close()


def test_cooccurs_counts_shared_tags(tmp_path):
    conn = _seed(tmp_path)
    try:
        _tags(conn, "m1", ["dog", "cat"])
        _tags(conn, "m2", ["dog", "cat"])
        _tags(conn, "m3", ["dog"])
        result = rebuild_cooccurs(conn)
        assert result["pairs"] == 1
        row = conn.execute(
            """
            SELECT support_count FROM brain_edges WHERE edge_type='CO_OCCURS'
            """
        ).fetchone()
        assert int(row[0]) == 2
        rebuild_cooccurs(conn)
        assert conn.execute(
            "SELECT COUNT(*) FROM brain_edges WHERE edge_type='CO_OCCURS'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_same_as_ignores_person_and_identity(tmp_path):
    conn = _seed(tmp_path)
    try:
        blob = mean_l2_int8([_vec(0)], 4)
        left = ensure_labeled_node(conn, "ObjectCluster", "obj-a")
        right = ensure_labeled_node(conn, "ObjectCluster", "obj-b")
        person = ensure_labeled_node(conn, "Person", "ada", status="confirmed")
        conn.execute(
            "UPDATE brain_nodes SET canonical_embedding=? WHERE id IN (?, ?)",
            (blob, left, right),
        )
        conn.execute(
            """INSERT INTO clusters(cluster_id, run_id, strategy, face_count, status)
               VALUES ('c1','run-brain','dbscan',1,'auto')"""
        )
        conn.execute(
            """INSERT INTO persons(person_id, display_name, status, created_run)
               VALUES ('p1','Ada','active','run-brain')"""
        )
        conn.execute(
            """INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id)
               VALUES ('o1','m1',NULL,NULL,'run-brain')"""
        )
        conn.execute(
            """INSERT INTO faces(
                 face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                 det_score, face_w, face_h, size_band, status, cluster_id, person_id)
               VALUES ('f1','o1','run-brain',0,0,8,8,0.42,8,8,'80-119','ok','c1','p1')"""
        )
        conn.commit()
        linked = link_same_as(conn)
        assert linked["edges"] == 1
        person_edges = conn.execute(
            """
            SELECT COUNT(*) FROM brain_edges e
              JOIN brain_nodes n
                ON n.id = e.source_node_id OR n.id = e.target_node_id
             WHERE e.edge_type='SAME_AS' AND n.id=?
            """,
            (person,),
        ).fetchone()[0]
        assert person_edges == 0
        face = conn.execute(
            "SELECT person_id, det_score, cluster_id FROM faces WHERE face_id='f1'"
        ).fetchone()
        assert face[0] == "p1"
        assert face[1] == 0.42
        assert face[2] == "c1"
    finally:
        conn.close()


def test_has_face_reads_cluster_without_writing_identity(tmp_path):
    conn = _seed(tmp_path)
    try:
        conn.execute(
            """INSERT INTO clusters(cluster_id, run_id, strategy, face_count, status)
               VALUES ('c1','run-brain','dbscan',1,'auto')"""
        )
        conn.execute(
            """INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id)
               VALUES ('o1','m1',NULL,NULL,'run-brain')"""
        )
        conn.execute(
            """INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id)
               VALUES ('o2','m2',NULL,NULL,'run-brain')"""
        )
        conn.execute(
            """INSERT INTO faces(
                 face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                 det_score, face_w, face_h, size_band, status, cluster_id)
               VALUES ('f1','o1','run-brain',0,0,8,8,0.5,8,8,'80-119','ok','c1')"""
        )
        conn.execute(
            """INSERT INTO faces(
                 face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                 det_score, face_w, face_h, size_band, status)
               VALUES ('f2','o2','run-brain',0,0,8,8,0.5,8,8,'80-119','ok')"""
        )
        conn.commit()
        before = conn.execute("SELECT person_id, det_score FROM faces WHERE face_id='f1'").fetchone()
        created = link_faces(conn)
        again = link_faces(conn)
        assert created["edges_new"] == 1
        assert again["edges_new"] == 0
        after = conn.execute("SELECT person_id, det_score FROM faces WHERE face_id='f1'").fetchone()
        assert after == before
        assert conn.execute(
            "SELECT COUNT(*) FROM brain_edges WHERE edge_type='HAS_FACE'"
        ).fetchone()[0] == 1
        src = Path("semblon/brain/face_link.py").read_text(encoding="utf-8")
        assert "UPDATE faces" not in src
        assert "INSERT INTO faces" not in src
    finally:
        conn.close()


def test_has_scene_and_gap_query_create_no_table(tmp_path):
    conn = _seed(tmp_path)
    try:
        conn.execute(
            """INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id)
               VALUES ('os','m1',NULL,NULL,'run-brain')"""
        )
        conn.execute(
            """INSERT INTO observation_items(
                 item_id, observation_id, run_id, kind, provider, payload_json)
               VALUES ('item-s','os','run-brain','clip','scene','{}')"""
        )
        blob = _vec(0)
        conn.execute(
            """INSERT INTO embeddings(
                 embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
               VALUES ('emb-s','item-s','scene','scene-pack',4,?)""",
            (blob,),
        )
        conn.commit()
        before = brain_gaps(conn)
        assert before["scene"] == 1
        link_scenes(conn)
        after = brain_gaps(conn)
        assert after["scene"] == 0
        names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "brain_gaps" not in names
        assert conn.execute(
            "SELECT COUNT(*) FROM brain_edges WHERE edge_type='HAS_SCENE'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_approximate_predict_assigns_inside_eps_without_dbscan(tmp_path, monkeypatch):
    conn = _seed(tmp_path)
    try:
        def _explode(_conn):
            raise AssertionError("DBSCAN rebuild must not run")

        monkeypatch.setattr(
            "semblon.brain.object_cluster.rebuild_object_clusters",
            _explode,
        )
        blob = mean_l2_int8([_vec(0)], 4)
        node_id = ensure_labeled_node(conn, "ObjectCluster", "obj-near")
        conn.execute(
            """UPDATE brain_nodes
                  SET canonical_embedding=?, embedding_pack_hash=?
                WHERE id=?""",
            (blob, "pack", node_id),
        )
        conn.commit()
        near = approximate_predict(conn, _vec(0), media_id="m1", dim=4)
        far = approximate_predict(conn, _vec(1), media_id="m2", dim=4)
        assert near["matched"] is True
        assert near["created"] is True
        assert far["matched"] is False
        assert conn.execute(
            "SELECT COUNT(*) FROM brain_nodes WHERE node_type='ObjectCluster'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM brain_edges WHERE edge_type='HAS_OBJECT'"
        ).fetchone()[0] == 1
        again = approximate_predict(conn, _vec(0), media_id="m1", dim=4)
        assert again["created"] is False
        assert rebuild_object_clusters is not None
    finally:
        conn.close()
