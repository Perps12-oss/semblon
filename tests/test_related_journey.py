"""One persisted archive, opened again after each human step.

The store is a real sqlite file. Each return to Related is a new shell
on that file, after the previous shell has shut down.
"""

from __future__ import annotations

import struct
import time

import pytest

from semblon.brain.graph import ensure_labeled_node, ensure_photo_node, insert_counted_edge, upsert_edge
from semblon.brain.object_cluster import OBJECT_DBSCAN_EPS
from semblon.brain.quantize import mean_l2_int8
from semblon.brain.same_as import _distance, link_same_as
from semblon.store import SCHEMA_VERSION, connect, init_db


def _spin(app, seconds: float = 0.45) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)


def _walk(item, visit) -> None:
    visit(item)
    for child in item.childItems():
        _walk(child, visit)


def _texts(root) -> list[str]:
    found: list[str] = []

    def visit(item) -> None:
        text = item.property("text")
        if isinstance(text, str) and text:
            found.append(text)

    _walk(root.contentItem(), visit)
    return found


def _press(root, card_name: str, title: str, button: str) -> None:
    cards = []

    def collect(item) -> None:
        if item.objectName() == card_name:
            cards.append(item)

    _walk(root.contentItem(), collect)
    chosen = None
    for card in cards:
        titles: list[str] = []

        def titles_of(item, bucket=titles) -> None:
            if item.property("text") == title:
                bucket.append(title)
            for child in item.childItems():
                titles_of(child, bucket)

        titles_of(card)
        if titles:
            chosen = card
            break
    assert chosen is not None, (card_name, title, len(cards))
    found = []

    def buttons(item) -> None:
        if item.property("label") == button:
            found.append(item)
        for child in item.childItems():
            buttons(child)

    buttons(chosen)
    assert found, (button, title)
    found[0].fire()


def _boot(store):
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    return app, engine, engine._semblon_bridge


def _shutdown(engine) -> None:
    from semblon.native_shell.host import shutdown_shell

    shutdown_shell(engine)


def _seed(store) -> None:
    conn = connect(store)
    init_db(conn)
    assert (
        conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]
        == SCHEMA_VERSION
        == "12"
    )
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('run-journey','2026-01-01T00:00:00Z','0.0.1','pack-journey',4,'l2','{}','{}','x64','emulated')"""
    )
    for media_id, mtime, name in (("m1", 10, "a"), ("m2", 30, "b")):
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(store.parent / f"{name}.jpg"), f"sha-{name}", 10, 10, mtime, 1),
        )
    cedar = ensure_labeled_node(conn, "Tag", "cedar")
    harbor = ensure_labeled_node(conn, "Tag", "harbor")
    left = ensure_labeled_node(conn, "ObjectCluster", "obj:pack:0")
    right = ensure_labeled_node(conn, "ObjectCluster", "obj:pack:1")
    photo1 = ensure_photo_node(conn, "m1")
    photo2 = ensure_photo_node(conn, "m2")
    upsert_edge(conn, source_id=photo1, target_id=cedar, edge_type="HAS_TAG")
    upsert_edge(conn, source_id=photo2, target_id=harbor, edge_type="HAS_TAG")
    upsert_edge(conn, source_id=photo1, target_id=left, edge_type="HAS_OBJECT")
    upsert_edge(conn, source_id=photo2, target_id=left, edge_type="HAS_OBJECT")
    upsert_edge(conn, source_id=photo2, target_id=right, edge_type="HAS_OBJECT")
    insert_counted_edge(
        conn,
        source_id=min(left, right),
        target_id=max(left, right),
        edge_type="SAME_AS",
        confidence=0.2,
        support_count=1,
    )
    blob = mean_l2_int8([struct.pack("<4f", 1.0, 0.0, 0.0, 0.0)], 4)
    conn.execute(
        "UPDATE brain_nodes SET canonical_embedding=? WHERE id IN (?, ?)",
        (blob, left, right),
    )
    assert _distance(blob, blob) == 0.0
    assert _distance(blob, blob) <= OBJECT_DBSCAN_EPS
    conn.execute(
        """INSERT INTO clusters(cluster_id, run_id, strategy, face_count, min_intra, status)
           VALUES ('c1','run-journey','dbscan',1,1.0,'auto')"""
    )
    conn.execute(
        """INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id)
           VALUES ('o1','m1',NULL,NULL,'run-journey')"""
    )
    face_vec = struct.pack("<4f", 1.0, 0.0, 0.0, 0.0)
    conn.execute(
        """INSERT INTO faces(
             face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
             det_score, face_w, face_h, size_band, status, embedding, embedding_pack,
             embedding_dim, cluster_id)
           VALUES ('f1','o1','run-journey',0,0,8,8,0.9,8,8,'80-119','ok',?,?,4,'c1')""",
        (face_vec, "pack-journey"),
    )
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()


def _edge_state(store) -> tuple:
    conn = connect(store)
    try:
        edge = conn.execute(
            "SELECT contradiction_state, contradict_count FROM brain_edges WHERE edge_type='SAME_AS'"
        ).fetchall()
        claims = [
            row[0]
            for row in conn.execute(
                """SELECT claim_key FROM brain_evidence
                   WHERE claim_key LIKE 'human:%' ORDER BY created_at, id"""
            )
        ]
        persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        decisions = [
            row[0]
            for row in conn.execute("SELECT kind FROM decisions ORDER BY created_at, decision_id")
        ]
        return edge, claims, persons, decisions
    finally:
        conn.close()


def test_human_correction_is_still_there_when_related_opens_again(tmp_path):
    pytest.importorskip("PySide6")
    store = tmp_path / "journey.sqlite"
    _seed(store)

    app, engine, bridge = _boot(store)
    try:
        bridge.openFocus("m1")
        bridge.openRelated()
        _spin(app)
        titles = _texts(engine.rootObjects()[0])
        assert "Similar object" in titles
        assert "Possible visual match" in titles
        assert "cedar" in titles
        assert "Unnamed person" in titles
        assert "harbor" not in titles
        root = engine.rootObjects()[0]
        _press(root, "relatedObjectCard", "Similar object", "Photographs")
        _spin(app)
        assert bridge.relatedView == "photos"
        assert [row["mediaId"] for row in bridge.relatedPhotos] == ["m1", "m2"]
        assert "Oldest first. Choose a photograph to open it." in _texts(root)
        bridge.backRelated()
        _spin(app)

        bridge.openFocus("m2")
        bridge.openRelated()
        _spin(app)
        switched = _texts(engine.rootObjects()[0])
        assert "harbor" in switched
        assert "cedar" not in switched
        stale = bridge._related_gen
        bridge._load_related("m1", stale - 1)
        _spin(app)
        held = _texts(engine.rootObjects()[0])
        assert "harbor" in held
        assert "cedar" not in held

        bridge.openFocus("m1")
        bridge.openRelated()
        _spin(app)
        assert conn_persons(store) == 0
        _press(engine.rootObjects()[0], "relatedObjectCard", "Similar object", "Same object")
        _spin(app)
        assert bridge.relatedNote == "Saved."
        assert "You said these are the same object" in _texts(engine.rootObjects()[0])
    finally:
        _shutdown(engine)

    edges, claims, persons, decisions = _edge_state(store)
    assert len(edges) == 1
    assert edges[0][0] == "none"
    assert claims == ["human:same_object"]
    assert persons == 0
    assert decisions == []

    app, engine, bridge = _boot(store)
    try:
        bridge.openFocus("m1")
        bridge.openRelated()
        _spin(app)
        assert "You said these are the same object" in _texts(engine.rootObjects()[0])
        _press(engine.rootObjects()[0], "relatedObjectCard", "Similar object", "Not the same")
        _spin(app)
        assert bridge.relatedNote == "Saved."
        assert "You said these are different" in _texts(engine.rootObjects()[0])
    finally:
        _shutdown(engine)

    edges, claims, persons, decisions = _edge_state(store)
    assert len(edges) == 1
    assert edges[0][0] == "contradicted"
    assert int(edges[0][1]) >= 1
    assert claims == ["human:same_object", "human:different_object"]
    assert persons == 0
    assert decisions == []

    conn = connect(store)
    try:
        rebuilt = link_same_as(conn)
    finally:
        conn.close()
    assert rebuilt["edges"] == 0
    assert rebuilt["skipped"] is False
    edges, claims, _persons, _decisions = _edge_state(store)
    assert len(edges) == 1
    assert edges[0][0] == "contradicted"
    assert int(edges[0][1]) >= 1
    assert claims == ["human:same_object", "human:different_object"]

    app, engine, bridge = _boot(store)
    try:
        bridge.openFocus("m1")
        bridge.openRelated()
        _spin(app)
        titles = _texts(engine.rootObjects()[0])
        assert "You said these are different" in titles
        assert "Possible visual match" not in titles
        assert "Unnamed person" in titles
        _press(engine.rootObjects()[0], "relatedPersonCard", "Unnamed person", "Open in People")
        _spin(app)
        assert bridge.peopleOpen is True
        assert bridge.selectedSubject == "c1"
        assert bridge.people_model.row("c1")["named"] is False
        named = bridge.relatedPersonDecision("name", "c1", "Ada")
        assert named == "Saved name: Ada."
        _spin(app)
        assert bridge.people_model.row("c1")["named"] is True
    finally:
        _shutdown(engine)

    conn = connect(store)
    try:
        person = conn.execute(
            "SELECT person_id, display_name FROM persons WHERE status='active'"
        ).fetchone()
        face = conn.execute("SELECT person_id FROM faces WHERE face_id='f1'").fetchone()
        kind = conn.execute("SELECT kind FROM decisions").fetchall()
        brain_people = conn.execute(
            "SELECT COUNT(*) FROM brain_nodes WHERE node_type='Person'"
        ).fetchone()[0]
        assert person[1] == "Ada"
        assert face[0] == person[0]
        assert [row[0] for row in kind] == ["name"]
        assert brain_people == 0
        assert (
            conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]
            == "12"
        )
    finally:
        conn.close()
    edges, claims, persons, decisions = _edge_state(store)
    assert edges[0][0] == "contradicted"
    assert claims == ["human:same_object", "human:different_object"]
    assert persons == 1
    assert decisions == ["name"]

    app, engine, bridge = _boot(store)
    try:
        bridge.openFocus("m1")
        bridge.openRelated()
        _spin(app)
        titles = _texts(engine.rootObjects()[0])
        assert "Ada" in titles
        assert "You said these are different" in titles
        assert "Unnamed person" not in titles
        bridge.openFocus("m2")
        bridge.openRelated()
        _spin(app)
        stale_token = bridge._related_gen
        shown = _texts(engine.rootObjects()[0])
        assert "harbor" in shown
        assert "cedar" not in shown
        bridge._load_related("m1", stale_token - 1)
        _spin(app)
        held = _texts(engine.rootObjects()[0])
        assert "harbor" in held
        assert "cedar" not in held
        assert "You said these are different" in held
    finally:
        _shutdown(engine)


def conn_persons(store) -> int:
    conn = connect(store)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0])
    finally:
        conn.close()
