"""Related is a shell action on the existing bridge. Person decisions forward to decide."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from semblon.brain.graph import ensure_labeled_node, ensure_photo_node, insert_counted_edge, upsert_edge
from semblon.store import connect, init_db


def test_related_is_a_photo_action_not_a_fifth_top_bar_button():
    viewer = Path("semblon/native_shell/qml/Viewer.qml").read_text(encoding="utf-8")
    table = Path("semblon/native_shell/qml/Table.qml").read_text(encoding="utf-8")
    related = Path("semblon/native_shell/qml/Related.qml").read_text(encoding="utf-8")
    assert 'objectName: "relatedAction"' in viewer
    assert "Related to this photo" in viewer
    assert 'label: "Back to related"' in viewer
    assert "v-related" in table
    assert "Related { " in table or "Related {" in table
    assert 'objectName: "relatedDesk"' in related
    assert "No related objects found yet." not in related  # the copy comes from the graph read
    assert "brain" not in related.lower()
    assert "embedding" not in related.lower()
    assert "cluster" not in related.lower()


def test_person_decision_slot_only_forwards_to_decide():
    from semblon.native_shell.bridge import ShellBridge

    src = inspect.getsource(ShellBridge.relatedPersonDecision)
    assert "return self.decide" in src
    assert "person_id" not in src
    assert "UPDATE" not in src
    body = inspect.getsource(ShellBridge.openRelatedPerson)
    assert "apply_name" not in body
    assert "INSERT" not in body


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    QApplication.instance() or QApplication([])
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(tmp_path / "a.jpg"), "ha", 10, 10, 10, 1),
    )
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m2", "folder", str(tmp_path / "b.jpg"), "hb", 10, 10, 20, 1),
    )
    conn.commit()
    conn.close()
    jobs = Application(store)
    made = ShellBridge(ArchiveModel(jobs), jobs)
    yield made
    made.shutdown()


def test_related_opens_from_the_focused_photo_and_ignores_a_stale_read(bridge):
    bridge.openFocus("m1")
    bridge.openRelated()
    assert bridge.relatedOpen is True
    assert bridge.relatedOriginId == "m1"
    assert bridge.relatedObjects == []
    assert "not in memory yet" in bridge.relatedCoverage.lower()
    assert bridge.relatedObjectsNote == "No related objects found yet."

    bridge._related_objects = [{"key": "keep", "title": "kept"}]
    bridge._related_gen += 1
    bridge._load_related("m1", bridge._related_gen - 1)
    assert bridge.relatedObjects[0]["title"] == "kept"
    bridge._load_related("m1", bridge._related_gen)
    assert bridge.relatedObjects == []
    assert "could not be read" not in bridge.relatedNote.lower()


def test_object_correction_from_the_bridge_is_human_evidence(bridge, tmp_path):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    left = ensure_labeled_node(conn, "ObjectCluster", "obj:pack:0")
    right = ensure_labeled_node(conn, "ObjectCluster", "obj:pack:1")
    photo = ensure_photo_node(conn, "m1")
    other = ensure_photo_node(conn, "m2")
    upsert_edge(conn, source_id=photo, target_id=left, edge_type="HAS_OBJECT")
    upsert_edge(conn, source_id=other, target_id=right, edge_type="HAS_OBJECT")
    insert_counted_edge(
        conn,
        source_id=min(left, right),
        target_id=max(left, right),
        edge_type="SAME_AS",
        confidence=0.2,
        support_count=1,
    )
    conn.commit()
    conn.close()

    bridge.openFocus("m1")
    bridge.openRelated()
    card = next(row for row in bridge.relatedObjects if row["canCorrect"])
    assert card["stateLabel"] == "Possible visual match"
    assert "obj:" not in card["title"]
    note = bridge.confirmSameObject(card["key"])
    assert note == "Saved."
    saved = next(row for row in bridge.relatedObjects if row["kind"] == "object")
    assert saved["stateLabel"] == "You said these are the same object"

    conn = connect(store)
    try:
        row = conn.execute(
            """
            SELECT o.provider_name, ev.claim_key, ev.role, e.contradiction_state
              FROM brain_evidence ev
              JOIN brain_observations o ON o.id = ev.observation_id
              JOIN brain_edges e ON e.id = ev.edge_id
             WHERE ev.claim_key LIKE 'human:%'
            """
        ).fetchone()
        assert tuple(row) == ("human", "human:same_object", "supports", "none")
        assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    finally:
        conn.close()

    bridge.openRelatedItem(saved["key"])
    assert bridge.relatedView == "photos"
    assert [row["mediaId"] for row in bridge.relatedPhotos] == ["m1"]
    bridge.openRelatedPhoto("m2")
    assert bridge.relatedOpen is False
    assert bridge.relatedReturn is True
    assert bridge.focusId == "m2"
    bridge.returnToRelated()
    assert bridge.relatedOpen is True
    assert bridge.focusId == "m1"
    assert bridge.relatedView == "photos"


def test_related_overlay_opens_in_the_production_shell(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(tmp_path / "a.jpg"), "ha", 10, 10, 10, 1),
    )
    left = ensure_labeled_node(conn, "ObjectCluster", "obj:pack:0")
    right = ensure_labeled_node(conn, "ObjectCluster", "obj:pack:1")
    photo = ensure_photo_node(conn, "m1")
    upsert_edge(conn, source_id=photo, target_id=left, edge_type="HAS_OBJECT")
    insert_counted_edge(
        conn,
        source_id=min(left, right),
        target_id=max(left, right),
        edge_type="SAME_AS",
        confidence=0.2,
        support_count=1,
    )
    conn.commit()
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    warnings = []
    engine.warnings.connect(lambda w: warnings.append(getattr(w, "toString", lambda: str(w))()))
    bridge = engine._semblon_bridge
    try:
        bridge.openFocus("m1")
        bridge.openRelated()
        import time
        for _ in range(20):
            app.processEvents()
            time.sleep(0.05)
        root = engine.rootObjects()[0]
        desk = root.findChild(QObject, "relatedDesk")
        assert desk is not None, warnings
        assert desk.property("visible") is True, warnings
        assert bridge.relatedOpen is True
        # Repeater delegates are visual children. findChildren misses them after the event loop.
        titles = []

        def _visual_text(item):
            text = item.property("text")
            if isinstance(text, str) and text:
                titles.append(text)
            for child in item.childItems():
                _visual_text(child)

        _visual_text(root.contentItem())
        assert "Related" in titles
        grid = root.findChild(QObject, "relatedObjectGrid")
        shown = [title for title in titles if "object" in title.lower() or title in {"Objects", "People", "Relationships"}]
        assert grid is not None and grid.property("count") == 1, (None if grid is None else grid.property("count"), shown, warnings)
        assert "Similar object" in titles, (shown, warnings)
        assert "Possible visual match" in titles
        assert any(label == "Related to this photo" for label in titles)
        assert not any("obj:pack" in label for label in titles)
    finally:
        shutdown_shell(engine)


def test_related_person_decision_calls_decide_and_does_not_name(bridge):
    called = {}

    def fake(kind, subject, text):
        called["args"] = (kind, subject, text)
        return "from-decide"

    bridge.decide = fake
    assert bridge.relatedPersonDecision("name", "c1", "Ada") == "from-decide"
    assert called["args"] == ("name", "c1", "Ada")
    bridge.openRelatedPerson("missing-group")
    assert bridge.peopleOpen is True
    assert bridge.selectedSubject == ""
