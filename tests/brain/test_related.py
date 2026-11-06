"""Related-to-this-photo reads and human object corrections.

Schema stays 12. Person rows are not written here.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from semblon.brain.cooccur import rebuild_cooccurs
from semblon.brain.evidence import record_observations
from semblon.brain.face_link import link_faces
from semblon.brain.graph import (
    ensure_labeled_node,
    ensure_photo_node,
    insert_counted_edge,
    sync_tags_from_observations,
    upsert_edge,
)
from semblon.brain.object_decisions import (
    ObjectDecisionError,
    confirm_different,
    confirm_same,
)
from semblon.brain.observation import Observation
from semblon.brain.quantize import mean_l2_int8
from semblon.brain.related import (
    EMPTY_OBJECTS,
    EXPLORE_LIMIT,
    GROUPING_NOT_RUN,
    NOT_IN_MEMORY,
    PEOPLE_UNLINKED,
    photos_for_related,
    related_for_media,
)
from semblon.brain.same_as import link_same_as
from semblon.store import SCHEMA_VERSION, connect, init_db


def _vec(axis: int, dim: int = 4) -> bytes:
    vals = [0.0] * dim
    vals[axis] = 1.0
    return struct.pack(f"<{dim}f", *vals)


def _seed(tmp_path):
    conn = connect(tmp_path / "related.sqlite")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('run-brain','t','0.0.1','pack',4,'l2','{}','{}','x64','emulated')"""
    )
    for media_id, mtime, name in (
        ("m1", 10, "a"),
        ("m2", 30, "b"),
        ("m3", 20, "c"),
    ):
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", f"/{name}.jpg", f"sha-{name}", 10, 10, mtime, 1),
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


def _objects(conn):
    left = ensure_labeled_node(conn, "ObjectCluster", "obj:pack:0")
    right = ensure_labeled_node(conn, "ObjectCluster", "obj:pack:1")
    photo = ensure_photo_node(conn, "m1")
    other = ensure_photo_node(conn, "m2")
    upsert_edge(conn, source_id=photo, target_id=left, edge_type="HAS_OBJECT")
    upsert_edge(conn, source_id=other, target_id=left, edge_type="HAS_OBJECT")
    upsert_edge(conn, source_id=other, target_id=right, edge_type="HAS_OBJECT")
    conn.commit()
    return left, right


def _face(conn, *, cluster_id="c1", person_id="p1", name="Ada"):
    conn.execute(
        """INSERT INTO clusters(cluster_id, run_id, strategy, face_count, status)
           VALUES ('c1','run-brain','dbscan',1,'auto')"""
    )
    conn.execute(
        """INSERT INTO persons(person_id, display_name, status, created_run)
           VALUES (?,?, 'active','run-brain')""",
        (person_id, name),
    )
    conn.execute(
        """INSERT INTO cluster_person(cluster_id, person_id) VALUES (?,?)""",
        (cluster_id, person_id),
    )
    conn.execute(
        """INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id)
           VALUES ('o1','m1',NULL,NULL,'run-brain')"""
    )
    conn.execute(
        """INSERT INTO faces(
             face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
             det_score, face_w, face_h, size_band, status, cluster_id, person_id)
           VALUES ('f1','o1','run-brain',0,0,8,8,0.42,8,8,'80-119','ok',?,?)""",
        (cluster_id, person_id),
    )
    conn.commit()


def test_schema_stays_12(tmp_path):
    conn = _seed(tmp_path)
    try:
        assert SCHEMA_VERSION == "12"
    finally:
        conn.close()


def test_missing_graph_is_not_an_empty_relationship(tmp_path):
    conn = connect(tmp_path / "bare.sqlite")
    try:
        payload = related_for_media(conn, "m1")
    finally:
        conn.close()
    assert payload["objects"] == []
    assert payload["coverage"] == NOT_IN_MEMORY
    assert payload["objectsNote"] == EMPTY_OBJECTS
    assert "no related" not in payload["coverage"].lower()


def test_photo_without_labels_says_not_saved(tmp_path):
    conn = _seed(tmp_path)
    try:
        ensure_photo_node(conn, "m1")
        conn.commit()
        payload = related_for_media(conn, "m1")
        assert payload["objects"] == []
        assert payload["objectsNote"] == EMPTY_OBJECTS
        assert "Visual labels have not been saved" in payload["coverage"]
        assert payload["empty"] is True
    finally:
        conn.close()


def test_tags_are_counted_without_inventing_clusters(tmp_path):
    conn = _seed(tmp_path)
    try:
        _tags(conn, "m1", ["dog"])
        _tags(conn, "m2", ["dog"])
        payload = related_for_media(conn, "m1")
        assert len(payload["objects"]) == 1
        card = payload["objects"][0]
        assert card["title"] == "dog"
        assert card["count"] == 2
        assert card["countLabel"] == "Appears in 2 photographs"
        assert card["stateLabel"] == "Seen in more than one photo"
        assert card["canCorrect"] is False
        assert GROUPING_NOT_RUN in payload["coverage"]
        assert "obj:" not in card["title"]
    finally:
        conn.close()


def test_retracted_tag_stays_hidden(tmp_path):
    conn = _seed(tmp_path)
    try:
        _tags(conn, "m1", ["gone"])
        conn.execute(
            "UPDATE brain_nodes SET status='retracted' WHERE node_type='Tag' AND label='gone'"
        )
        conn.commit()
        payload = related_for_media(conn, "m1")
        assert payload["objects"] == []
        assert payload["objectsNote"] == EMPTY_OBJECTS
    finally:
        conn.close()


def test_object_card_hides_internal_label_and_offers_a_match(tmp_path):
    conn = _seed(tmp_path)
    try:
        left, right = _objects(conn)
        insert_counted_edge(
            conn,
            source_id=min(left, right),
            target_id=max(left, right),
            edge_type="SAME_AS",
            confidence=0.4,
            support_count=1,
        )
        conn.commit()
        payload = related_for_media(conn, "m1")
        cards = [row for row in payload["objects"] if row["kind"] == "object"]
        assert len(cards) == 1
        assert cards[0]["title"] == "Similar object"
        assert "obj:" not in cards[0]["title"]
        assert "pack" not in cards[0]["title"]
        assert cards[0]["stateLabel"] == "Possible visual match"
        assert cards[0]["canCorrect"] is True
        assert cards[0]["countLabel"] == "Appears in 2 photographs"
        assert any(row["detail"] == "Possible visual match" for row in payload["relationships"])
    finally:
        conn.close()


def test_cooccurs_is_not_ownership(tmp_path):
    conn = _seed(tmp_path)
    try:
        _tags(conn, "m1", ["dog", "leash"])
        _tags(conn, "m2", ["dog", "leash"])
        _tags(conn, "m3", ["dog", "leash"])
        rebuild_cooccurs(conn)
        payload = related_for_media(conn, "m1")
        together = [row for row in payload["relationships"] if " and " in row["title"]]
        assert len(together) == 1
        assert "Often in the same photographs (3)." in together[0]["detail"]
        assert "not a claim about who owns them" in together[0]["detail"]
        assert "identity" not in together[0]["detail"].lower()
    finally:
        conn.close()


def test_people_from_the_graph_do_not_write_identity(tmp_path):
    conn = _seed(tmp_path)
    try:
        _face(conn)
        before = conn.execute("SELECT person_id, det_score FROM faces WHERE face_id='f1'").fetchone()
        link_faces(conn)
        payload = related_for_media(conn, "m1")
        after = conn.execute("SELECT person_id, det_score, cluster_id FROM faces WHERE face_id='f1'").fetchone()
        assert before[0] == after[0] == "p1"
        assert after[1] == 0.42
        assert after[2] == "c1"
        assert len(payload["people"]) == 1
        person = payload["people"][0]
        assert person["title"] == "Ada"
        assert person["named"] is True
        assert person["inMemory"] is True
        assert person["subject"] == "c1"
        assert "Named in People" == person["stateLabel"]
        assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 1
    finally:
        conn.close()


def test_faces_without_a_memory_link_are_not_treated_as_absent(tmp_path):
    conn = _seed(tmp_path)
    try:
        _face(conn)
        edges_before = conn.execute(
            "SELECT COUNT(*) FROM brain_edges WHERE edge_type='HAS_FACE'"
        ).fetchone()[0]
        payload = related_for_media(conn, "m1")
        edges_after = conn.execute(
            "SELECT COUNT(*) FROM brain_edges WHERE edge_type='HAS_FACE'"
        ).fetchone()[0]
        assert edges_before == edges_after == 0
        assert payload["people"][0]["inMemory"] is False
        assert payload["people"][0]["title"] == "Ada"
        assert payload["people"][0]["state"] == "not_linked"
        assert PEOPLE_UNLINKED in payload["coverage"]
        photos = photos_for_related(conn, payload["people"][0])
        assert [row["mediaId"] for row in photos] == ["m1"]
    finally:
        conn.close()


def test_explore_is_chronological_and_bounded(tmp_path, monkeypatch):
    conn = _seed(tmp_path)
    try:
        _tags(conn, "m1", ["dog"])
        _tags(conn, "m2", ["dog"])
        _tags(conn, "m3", ["dog"])
        payload = related_for_media(conn, "m1")
        photos = photos_for_related(conn, payload["objects"][0])
        assert [row["mediaId"] for row in photos] == ["m1", "m3", "m2"]
        assert EXPLORE_LIMIT == 240
        monkeypatch.setattr("semblon.brain.related.EXPLORE_LIMIT", 2)
        bounded = photos_for_related(conn, payload["objects"][0])
        assert [row["mediaId"] for row in bounded] == ["m1", "m3"]
    finally:
        conn.close()


def test_human_same_is_idempotent_and_beats_a_later_model_note(tmp_path):
    conn = _seed(tmp_path)
    try:
        left, right = _objects(conn)
        _face(conn)
        first = confirm_same(conn, media_id="m1", left_id=left, right_id=right)
        second = confirm_same(conn, media_id="m1", left_id=right, right_id=left)
        assert first["reused"] is False
        assert second["reused"] is True
        assert conn.execute(
            "SELECT COUNT(*) FROM brain_observations WHERE capability_id='H-OBJ'"
        ).fetchone()[0] == 1
        evidence = conn.execute(
            """
            SELECT o.provider_name, ev.claim_key, ev.role, ev.weight
              FROM brain_evidence ev
              JOIN brain_observations o ON o.id = ev.observation_id
            """
        ).fetchone()
        assert evidence[0] == "human"
        assert evidence[1] == "human:same_object"
        assert evidence[2] == "supports"
        assert evidence[3] == 1.0
        edge_id = int(first["edge_id"])
        conn.execute(
            """INSERT INTO brain_observations(
                 media_id, capability_id, provider_name, model_pack_hash,
                 payload_json, confidence, created_at)
               VALUES ('m1','C5','model','pack-model','{}',0.2,'2099-01-01T00:00:00.000000Z')"""
        )
        model_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO brain_evidence(
                 observation_id, edge_id, role, weight, claim_key, created_at)
               VALUES (?, ?, 'supports', 0.2, 'model:similarity', '2099-01-01T00:00:00.000000Z')""",
            (model_id, edge_id),
        )
        conn.commit()
        payload = related_for_media(conn, "m1")
        card = next(row for row in payload["objects"] if row["kind"] == "object")
        assert card["state"] == "confirmed"
        assert card["stateLabel"] == "You said these are the same object"
        face = conn.execute("SELECT person_id FROM faces WHERE face_id='f1'").fetchone()
        assert face[0] == "p1"
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    finally:
        conn.close()


def test_human_different_preserves_contradiction_and_survives_rebuild(tmp_path):
    conn = _seed(tmp_path)
    try:
        left, right = _objects(conn)
        blob = mean_l2_int8([_vec(0)], 4)
        conn.execute(
            "UPDATE brain_nodes SET canonical_embedding=? WHERE id IN (?, ?)",
            (blob, left, right),
        )
        conn.commit()
        confirm_different(conn, media_id="m1", left_id=left, right_id=right)
        confirm_different(conn, media_id="m1", left_id=left, right_id=right)
        assert conn.execute(
            """SELECT COUNT(*) FROM brain_evidence WHERE claim_key='human:different_object'"""
        ).fetchone()[0] == 1
        edge = conn.execute(
            "SELECT contradiction_state, contradict_count FROM brain_edges WHERE edge_type='SAME_AS'"
        ).fetchone()
        assert edge[0] == "contradicted"
        assert int(edge[1]) == 1
        confirm_same(conn, media_id="m2", left_id=left, right_id=right)
        claims = {
            row[0]
            for row in conn.execute("SELECT claim_key FROM brain_evidence WHERE claim_key LIKE 'human:%'")
        }
        assert claims == {"human:different_object", "human:same_object"}
        edge = conn.execute(
            "SELECT contradiction_state, contradict_count FROM brain_edges WHERE edge_type='SAME_AS'"
        ).fetchone()
        assert edge[0] == "none"
        assert int(edge[1]) == 1
        linked = link_same_as(conn)
        assert linked["edges"] == 0
        rows = conn.execute(
            "SELECT contradiction_state, contradict_count FROM brain_edges WHERE edge_type='SAME_AS'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "none"
        assert int(rows[0][1]) == 1
        confirm_different(conn, media_id="m3", left_id=left, right_id=right)
        link_same_as(conn)
        rows = conn.execute(
            "SELECT contradiction_state FROM brain_edges WHERE edge_type='SAME_AS'"
        ).fetchall()
        assert [row[0] for row in rows] == ["contradicted"]
        payload = related_for_media(conn, "m1")
        card = next(row for row in payload["objects"] if row["kind"] == "object")
        assert card["stateLabel"] == "You said these are different"
    finally:
        conn.close()


def test_rebuild_does_not_delete_a_human_edge_the_model_would_not_make(tmp_path):
    conn = _seed(tmp_path)
    try:
        left, right = _objects(conn)
        apart = mean_l2_int8([_vec(0)], 4)
        other = mean_l2_int8([_vec(1)], 4)
        conn.execute(
            "UPDATE brain_nodes SET canonical_embedding=? WHERE id=?",
            (apart, left),
        )
        conn.execute(
            "UPDATE brain_nodes SET canonical_embedding=? WHERE id=?",
            (other, right),
        )
        conn.commit()
        confirm_same(conn, media_id="m1", left_id=left, right_id=right)
        link_same_as(conn)
        row = conn.execute(
            """
            SELECT contradiction_state, ev.claim_key
              FROM brain_edges e
              JOIN brain_evidence ev ON ev.edge_id = e.id
             WHERE e.edge_type='SAME_AS'
            """
        ).fetchone()
        assert row[0] == "none"
        assert row[1] == "human:same_object"
    finally:
        conn.close()


def test_object_correction_rejects_a_person_and_does_not_assign_a_face(tmp_path):
    conn = _seed(tmp_path)
    try:
        _face(conn)
        left, _right = _objects(conn)
        person = ensure_labeled_node(conn, "Person", "ada", status="confirmed")
        conn.commit()
        with pytest.raises(ObjectDecisionError, match="only applies to objects"):
            confirm_same(conn, media_id="m1", left_id=person, right_id=left)
        assert conn.execute("SELECT COUNT(*) FROM brain_evidence").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM brain_edges WHERE edge_type='SAME_AS'"
        ).fetchone()[0] == 0
        face = conn.execute("SELECT person_id FROM faces WHERE face_id='f1'").fetchone()
        assert face[0] == "p1"
        assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 1
    finally:
        conn.close()


def test_related_modules_do_not_touch_identity_writers():
    root = Path("semblon/brain")
    for name in ("related.py", "object_decisions.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "UPDATE faces" not in text
        assert "INSERT INTO persons" not in text
        assert "INSERT INTO faces" not in text
        assert "review_board" not in text
        assert "apply_name" not in text
