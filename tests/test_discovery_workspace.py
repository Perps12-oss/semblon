"""Focus workspace: selection stays visible, search does not block, states stay distinct."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import numpy as np
import pytest


def _visual_child(item, name):
    if item is None:
        return None
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = _visual_child(child, name)
        if found is not None:
            return found
    return None


def _png(path):
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)


def _store(tmp_path):
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id, name in (("m1", "a.png"), ("m2", "b.png"), ("m3", "c.png")):
        path = tmp_path / name
        _png(path)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 100, 80, 0, 1),
        )
    conn.commit()
    return store, conn


def _hit(media_id: str):
    return {
        "region": {},
        "similar": {
            "status": "SUCCESS",
            "items": [
                {
                    "media_id": media_id,
                    "score": 0.5,
                    "match_norm": [0.1, 0.2, 0.3, 0.4],
                }
            ],
            "similarity_basis": "Similar look",
            "engine": "dinov2-patch",
            "understanding": "Unlabelled region.",
        },
        "persons": 0,
        "wrote_embedding": False,
    }


def _shell(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell

    store, conn = _store(tmp_path)
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    monkeypatch.setattr(Application, "remember_and_find_region", lambda self, media_id, x, y, w, h, **kwargs: _hit("m2"))
    bridge.openFocus("m1")
    bridge.setRegion(0.1, 0.2, 0.3, 0.25)
    return app, engine, bridge


def test_selection_survives_restore_and_states_are_distinct(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    from semblon.native_shell.host import shutdown_shell

    _app, engine, bridge = _shell(tmp_path, monkeypatch)
    try:
        assert bridge.selectionOnFocus is True
        assert abs(bridge.selectionW - 0.3) < 1e-6
        assert bridge.indexState == "unindexed"
        assert "not indexed" in bridge.indexNote
        bridge.findSimilar()
        from PySide6.QtCore import QEventLoop, QTimer

        loop = QEventLoop()
        QTimer.singleShot(100, loop.quit)
        loop.exec()
        assert bridge.similarState == "ready"
        assert bridge.similarCaution.startswith("A match is a similar region")
        assert "proof" in bridge.similarCaution
        root = engine.rootObjects()[0]
        outline = root.findChild(QObject, "selectionOutline")
        assert outline is not None
        assert outline.property("color").alpha() == 0
        shade = root.findChild(QObject, "selectionShade")
        assert shade is not None
        assert shade.property("visible") is True
        assert root.findChild(QObject, "searchThisArea") is not None
        assert root.findChild(QObject, "cancelSearch") is not None
        assert root.findChild(QObject, "indexNote") is not None
        assert root.findChild(QObject, "matchHonesty") is not None
        strip = root.findChild(QObject, "similarStrip")
        assert strip is not None
        assert int(strip.property("count") or 0) == 1
        # List delegates are visual children of the strip, not QObject::findChild hits.
        box = _visual_child(strip.property("contentItem"), "similarMatchBox")
        assert box is not None
        assert box.isVisible()
        assert box.width() > 2
        bridge.openDiscoveryHit("m2")
        assert bridge.focusId == "m2"
        assert bridge.selectionOnFocus is False
        assert bridge.matchW > 0
        assert bridge.keepDiscovery() == "Kept this find."
        assert bridge.resultText == "Kept this find."
        bridge.openFocus("m1")
        bridge.openKept(0)
        assert bridge.focusId == "m1"
        assert bridge.selectionOnFocus is True
        assert abs(bridge.selectionH - 0.25) < 1e-6
        kept = json.loads((tmp_path / "s.discoveries.json").read_text(encoding="utf-8"))
        assert kept[0]["region"][2] == pytest.approx(0.3)
    finally:
        shutdown_shell(engine)


def test_search_can_be_cancelled_before_it_finishes(tmp_path, monkeypatch):
    import threading

    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    monkeypatch.delenv("SEMBLON_SEARCH_SYNC", raising=False)
    gate = threading.Event()
    app, engine, bridge = _shell(tmp_path, monkeypatch)

    def slow(self, media_id, x, y, w, h, **kwargs):
        gate.wait(2)
        return _hit("m2")

    monkeypatch.setattr(Application, "remember_and_find_region", slow)
    try:
        bridge.findSimilar()
        assert bridge.similarState == "loading"
        assert bridge.searchBusy is True
        bridge.cancelSimilar()
        assert bridge.searchBusy is False
        assert bridge.similarState == "empty"
        assert "cancelled" in bridge.similarNote
        gate.set()
        deadline = time.time() + 2
        while time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        assert bridge.similarCount == 0
        assert bridge.similarState == "empty"
    finally:
        gate.set()
        shutdown_shell(engine)


def test_a_newer_search_replaces_a_slower_one(tmp_path, monkeypatch):
    import threading

    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    monkeypatch.delenv("SEMBLON_SEARCH_SYNC", raising=False)
    started = threading.Event()
    release = threading.Event()
    app, engine, bridge = _shell(tmp_path, monkeypatch)
    calls = {"n": 0}

    def paced(self, media_id, x, y, w, h, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            started.set()
            release.wait(2)
            return _hit("m2")
        return _hit("m3")

    monkeypatch.setattr(Application, "remember_and_find_region", paced)
    try:
        bridge.findSimilar()
        assert started.wait(2)
        bridge.findSimilar()
        release.set()
        deadline = time.time() + 3
        while bridge.searchBusy and time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
        assert bridge.similarId(0) == "m3"
    finally:
        release.set()
        shutdown_shell(engine)


def test_indexing_progress_names_photos_already_added(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    app, engine, bridge = _shell(tmp_path, monkeypatch)
    try:
        bridge._job_active = True
        bridge._on_worker_progress(
            SimpleNamespace(stage="ingest", kind="progress", current=2, total=9)
        )
        app.processEvents()
        assert "2/9" in bridge.jobLabel
        assert "already added" in bridge.jobLabel
    finally:
        shutdown_shell(engine)


def test_coarse_index_is_not_called_ready(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell
    from semblon.store import connect

    _app, engine, bridge = _shell(tmp_path, monkeypatch)
    try:
        blob = np.float32(1.0).tobytes()
        conn = connect(tmp_path / "s.sqlite")
        conn.execute(
            """INSERT INTO runs(run_id, started_at, software_version, pack_id,
               embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("r1", "t", "0.0.1", "pack-a", 1, "l2", "{}", "{}", "x64", "emulated"),
        )
        conn.execute(
            "INSERT INTO observations VALUES (?,?,?,?,?)",
            ("o-m1", "m1", None, None, "r1"),
        )
        conn.execute(
            """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
               bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("i1", "o-m1", "r1", "clip", "test", 0, 0, 4, 4, 1, "{}"),
        )
        conn.execute(
            """INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
               VALUES (?,?,?,?,?,?)""",
            ("e1", "i1", "region", "region/test", 1, blob),
        )
        conn.commit()
        conn.close()
        bridge._refresh_index_note()
        assert bridge.indexState == "fallback"
        assert "coarse index" in bridge.indexNote
    finally:
        shutdown_shell(engine)


def test_zoom_resets_on_the_next_photo_and_edges_resize(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    from semblon.native_shell.host import shutdown_shell

    _app, engine, bridge = _shell(tmp_path, monkeypatch)
    try:
        root = engine.rootObjects()[0]
        view = root.findChild(QObject, "photoView")
        assert view is not None
        assert root.findChild(QObject, "photoPinch") is not None
        assert root.findChild(QObject, "photoWheel") is not None
        assert root.findChild(QObject, "regionDrag") is not None
        _app.processEvents()
        assert float(view.property("width")) > 1
        view.zoomAt(30, 30, 2)
        assert float(view.property("scale")) == pytest.approx(2)
        bridge.focusNext()
        _app.processEvents()
        assert bridge.focusId == "m2"
        assert float(view.property("scale")) == pytest.approx(1)
        assert float(view.property("x")) == pytest.approx(0)
        grown = [float(part) for part in bridge.adjustSelectionBox(
            10, 20, 100, 40, "r", 25, 0, 0, 0, 400, 300
        ).split(",")]
        assert grown[2] == pytest.approx(125)
        assert grown[3] == pytest.approx(40)
    finally:
        shutdown_shell(engine)
