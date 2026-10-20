"""Focus presents a selection bar. Search behaviour stays on the existing doors."""

from __future__ import annotations

import threading

import pytest

pytest.importorskip("PySide6")


def _store(tmp_path):
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id in ("m1", "m2"):
        path = tmp_path / f"{media_id}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 100, 80, 0, 1),
        )
    conn.commit()
    conn.close()
    return store


def _hit(status="SUCCESS", items=None):
    if items is None:
        items = [
            {
                "media_id": "m2",
                "score": 0.8,
                "match_norm": [0.1, 0.2, 0.3, 0.4],
            }
        ]
    return {
        "region": {},
        "similar": {
            "status": status,
            "items": items,
            "similarity_basis": "Similar look",
            "engine": "dinov2-patch",
            "search_phase": "refined",
            "understanding": "Unlabelled region.",
        },
        "persons": 0,
        "wrote_embedding": False,
    }


def _shell(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(_store(tmp_path), app=app)
    root = engine.rootObjects()[0]
    root.setWidth(1100)
    root.setHeight(760)
    bridge = engine._semblon_bridge
    return app, engine, root, bridge


def _item(root, name):
    from PySide6.QtQuick import QQuickItem

    found = root.findChild(QQuickItem, name)
    assert found is not None, name
    return found


def test_focus_states_keep_the_photo_and_the_selection_bar(tmp_path, monkeypatch):
    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")
    monkeypatch.setattr(Application, "remember_and_find_region", lambda *args, **kwargs: _hit())
    app, engine, root, bridge = _shell(tmp_path, monkeypatch)
    try:
        bridge.openFocus("m1")
        app.processEvents()
        assert root.property("focusDetailsOpen") is False
        assert _item(root, "focusDetails").isVisible() is False
        assert _item(root, "focusDetailsButton").isVisible() is True
        assert _item(root, "pointHint").isVisible() is True
        assert _item(root, "searchThisArea").isVisible() is True
        assert _item(root, "searchThisArea").property("actionEnabled") is False
        assert _item(root, "findSimilarReason").property("text") == "Draw on the photo first."
        assert _item(root, "clearSelection").isVisible() is False
        assert _item(root, "cancelSearch").isVisible() is False
        assert _item(root, "nameThisArea").isVisible() is False
        assert _item(root, "refineModeRow").isVisible() is False

        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        app.processEvents()
        assert bridge.selectionOnFocus is True
        assert _item(root, "pointHint").isVisible() is False
        assert _item(root, "searchThisArea").property("actionEnabled") is True
        assert _item(root, "nameThisArea").isVisible() is True
        assert _item(root, "clearSelection").isVisible() is True
        assert _item(root, "refineModeRow").isVisible() is True
        assert _item(root, "refineSameLook").isVisible() is True
        assert _item(root, "refineSameKind").isVisible() is True
        assert _item(root, "refineWord").isVisible() is True
        assert _item(root, "selectionScopeNote").property("text") == "Selection scope. Not a named person."
        assert _item(root, "focusLifecycle").property("text") == (
            "Search for this visual detail across your archive."
        )

        for name in (
            "sameFaceDoor",
            "wholePhoto",
            "duplicatesDoor",
            "screenQueryAction",
            "showDayAction",
            "askPhotoAction",
        ):
            assert _item(root, name) is not None
        assert _item(root, "sameFaceDoor").property("actionEnabled") is False
        assert "face" in _item(root, "sameFaceReason").property("text")
        assert _item(root, "wholePhoto").property("actionEnabled") is True
        assert _item(root, "duplicatesDoor").property("actionEnabled") is True
        assert _item(root, "askPhotoAction").property("actionEnabled") is True
        assert _item(root, "showDayAction").property("actionEnabled") is False
        assert _item(root, "showDayReason").property("text") == "No date on this photo."

        bridge.findSimilar()
        app.processEvents()
        assert bridge.similarCount == 1
        assert bridge.similarId(0) == "m2"
        strip = _item(root, "similarStrip")
        assert int(strip.property("height")) >= 140
        assert _item(root, "keepDiscoveryAction").isVisible() is True
        assert _item(root, "searchTiming").isVisible() is False
        assert _item(root, "searchPhaseBadge").isVisible() is False
        assert _item(root, "searchQualityFocus").isVisible() is False
        assert bridge.keepDiscovery() == "Kept this find."
        assert bridge.similarCount == 1

        bridge.setMode("advanced")
        app.processEvents()
        assert _item(root, "searchTiming").isVisible() is True
        assert _item(root, "searchPhaseBadge").isVisible() is True
        bridge.setMode("primary")
        app.processEvents()

        root.setProperty("focusDetailsOpen", True)
        app.processEvents()
        assert _item(root, "focusDetails").isVisible() is True
        root.setProperty("focusDetailsOpen", False)
        app.processEvents()
        assert _item(root, "focusDetails").isVisible() is False

        bridge.clearDrawnQuery()
        app.processEvents()
        assert bridge.selectionOnFocus is False
        assert _item(root, "clearSelection").isVisible() is False
        assert _item(root, "searchThisArea").property("actionEnabled") is False
        assert _item(root, "pointHint").isVisible() is True
        assert _item(root, "keepDiscoveryAction").isVisible() is False
    finally:
        shutdown_shell(engine)


def test_empty_search_leaves_keep_hidden(tmp_path, monkeypatch):
    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")
    monkeypatch.setattr(
        Application,
        "remember_and_find_region",
        lambda *args, **kwargs: _hit("NO_RESULT", []),
    )
    app, engine, root, bridge = _shell(tmp_path, monkeypatch)
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        bridge.findSimilar()
        app.processEvents()
        assert bridge.similarCount == 0
        assert _item(root, "keepDiscoveryAction").isVisible() is False
        assert _item(root, "similarStrip").isVisible() is False
    finally:
        shutdown_shell(engine)


def test_cancel_appears_only_while_a_search_is_running(tmp_path, monkeypatch):
    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    monkeypatch.delenv("SEMBLON_SEARCH_SYNC", raising=False)
    gate = threading.Event()
    app, engine, root, bridge = _shell(tmp_path, monkeypatch)

    def slow(self, media_id, x, y, w, h, **kwargs):
        gate.wait(3)
        return _hit()

    monkeypatch.setattr(Application, "remember_and_find_region", slow)
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        app.processEvents()
        assert _item(root, "cancelSearch").isVisible() is False
        bridge.findSimilar()
        app.processEvents()
        assert bridge.searchBusy is True
        assert _item(root, "cancelSearch").isVisible() is True
        assert _item(root, "searchThisArea").isVisible() is False
        assert _item(root, "focusLifecycle").property("text") == "Finding similar regions…"
        assert _item(root, "wholePhoto").property("actionEnabled") is False
        assert _item(root, "wholePhotoReason").property("text") == "A search is already running."
        assert _item(root, "askPhotoAction").property("actionEnabled") is False
        bridge.cancelSimilar()
        app.processEvents()
        assert bridge.searchBusy is False
        assert _item(root, "cancelSearch").isVisible() is False
        assert _item(root, "searchThisArea").property("actionEnabled") is True
    finally:
        gate.set()
        shutdown_shell(engine)
