"""Focus presents one primary action, a results tray, and a visible running search."""

from __future__ import annotations

import threading
import time

import pytest


def _hit(media_id: str, *, phase: str = "refined"):
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
            "search_phase": phase,
            "understanding": "Unlabelled region.",
        },
        "persons": 0,
        "wrote_embedding": False,
    }


def _store(tmp_path):
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id in ("m1", "m2", "m3"):
        path = tmp_path / f"{media_id}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 100, 80, 0, 1),
        )
    conn.commit()
    conn.close()
    return store


def test_focus_chrome_names_the_primary_action_and_keeps_the_doors():
    from pathlib import Path

    qml = Path("semblon/native_shell/qml/Shell.qml").read_text(encoding="utf-8")
    assert 'text: "Find similar"' in qml
    assert 'text: "Describe this area"' in qml
    assert 'text: "Find this person"' in qml
    assert 'text: "Search the whole photo"' in qml
    assert 'text: "Find duplicates"' in qml
    assert 'objectName: "focusTray"' in qml
    assert 'objectName: "focusSearchSpinner"' in qml
    assert 'objectName: "focusSearchStatus"' in qml
    assert 'objectName: "focusDetailsToggle"' in qml
    assert 'objectName: "similarStripWheel"' in qml
    assert "focusDetailsOpen = true" not in qml
    assert 'text: "Similar region"' not in qml
    assert "shellApi.cancelSimilar()" in qml
    assert "shellApi.findSimilar()" in qml
    assert "shellApi.findSimilarFaces()" in qml
    assert "shellApi.findSimilarWhole()" in qml
    assert "shellApi.scanDuplicates()" in qml


def test_strip_keeps_the_hits_the_search_returned():
    pytest.importorskip("PySide6")
    from semblon.native_shell.model import SimilarStripModel

    model = SimilarStripModel()
    rows = [(f"m{i}", 0.5, 0.1, 0.1, 0.2, 0.2) for i in range(10)]
    model.set_rows(rows)
    assert model.rowCount() == 10
    assert model.media_id(9) == "m9"


def _shell(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("SEMBLON_SEARCH_SYNC", raising=False)
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(_store(tmp_path), app=app)
    root = engine.rootObjects()[0]
    root.setWidth(1440)
    root.setHeight(900)
    app.processEvents()
    return app, engine, engine._semblon_bridge, root


def _wait_idle(app, bridge, timeout=3.0):
    deadline = time.time() + timeout
    while bridge.searchBusy and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    app.processEvents()


def test_details_stay_closed_and_the_photo_keeps_the_width(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    from semblon.native_shell.host import shutdown_shell

    app, engine, bridge, root = _shell(tmp_path, monkeypatch)
    try:
        bridge.openFocus("m1")
        app.processEvents()
        assert root.property("focusDetailsOpen") is False
        details = root.findChild(QObject, "focusDetails")
        assert details is not None
        assert details.property("visible") is False
        photo = root.findChild(QObject, "photoViewport")
        layer = root.findChild(QObject, "focusLayer")
        assert photo is not None and layer is not None
        before = float(photo.property("width"))
        assert before > float(layer.property("width")) - 160
        root.setProperty("focusDetailsOpen", True)
        app.processEvents()
        assert details.property("visible") is True
        assert abs(float(photo.property("width")) - before) < 2
        tray = root.findChild(QObject, "focusTray")
        strip = root.findChild(QObject, "similarStrip")
        assert tray is not None and strip is not None
        assert float(strip.property("width")) > 600
        person = root.findChild(QObject, "sameFaceDoor")
        assert person is not None
        assert person.property("visible") is False
        assert root.findChild(QObject, "wholePhoto") is not None
        assert root.findChild(QObject, "duplicatesDoor") is not None
        assert root.findChild(QObject, "focusSearchSpinner") is not None
    finally:
        shutdown_shell(engine)


def test_a_running_search_shows_a_spinner_until_it_finishes(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    gate = threading.Event()
    app, engine, bridge, root = _shell(tmp_path, monkeypatch)

    def slow(self, media_id, x, y, w, h, **kwargs):
        on_first = kwargs.get("on_first")
        if on_first is not None:
            on_first(_hit("m2", phase="first"))
        gate.wait(3)
        return _hit("m2", phase="refined")

    monkeypatch.setattr(Application, "remember_and_find_region", slow)
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        bridge.findSimilar()
        deadline = time.time() + 2
        while "refining" not in bridge.similarNote and time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        app.processEvents()
        assert bridge.searchBusy is True
        spinner = root.findChild(QObject, "focusSearchSpinner")
        mark = root.findChild(QObject, "focusSearchMark")
        assert spinner is not None and mark is not None
        assert spinner.property("visible") is True or mark.property("visible") is True
        if not bridge.reducedMotion:
            assert spinner.property("running") is True
        status = root.findChild(QObject, "focusSearchStatus")
        assert "Finding similar" in status.property("text")
        assert float(status.property("width")) > 80
        badge = root.findChild(QObject, "searchPhaseBadge")
        assert badge.property("visible") is False
        gate.set()
        _wait_idle(app, bridge)
        assert bridge.searchBusy is False
        assert bridge.similarId(0) == "m2"
        assert spinner.property("running") is False
        assert "1 match" in status.property("text")
        assert float(status.property("width")) > 80
        assert badge.property("visible") is True
    finally:
        gate.set()
        shutdown_shell(engine)


def test_cancel_drops_the_spinner_and_ignores_the_late_result(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    release = threading.Event()
    started = threading.Event()
    app, engine, bridge, root = _shell(tmp_path, monkeypatch)

    def slow(self, media_id, x, y, w, h, **kwargs):
        started.set()
        release.wait(3)
        return _hit("m2")

    monkeypatch.setattr(Application, "remember_and_find_region", slow)
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        bridge.findSimilar()
        assert started.wait(2)
        app.processEvents()
        spinner = root.findChild(QObject, "focusSearchSpinner")
        assert bridge.searchBusy is True
        assert spinner.property("visible") is True or root.findChild(QObject, "focusSearchMark").property("visible")
        bridge.cancelSimilar()
        app.processEvents()
        assert bridge.searchBusy is False
        assert bridge.similarCount == 0
        assert "cancelled" in bridge.similarNote
        assert spinner.property("running") is False
        release.set()
        deadline = time.time() + 2
        while time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        assert bridge.similarCount == 0
        assert "cancelled" in bridge.similarNote
        assert spinner.property("running") is False
    finally:
        release.set()
        shutdown_shell(engine)


def test_a_newer_search_replaces_the_strip(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    release = threading.Event()
    started = threading.Event()
    app, engine, bridge, root = _shell(tmp_path, monkeypatch)
    calls = {"n": 0}

    def paced(self, media_id, x, y, w, h, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            started.set()
            release.wait(3)
            return _hit("m2")
        return _hit("m3")

    monkeypatch.setattr(Application, "remember_and_find_region", paced)
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        bridge.findSimilar()
        assert started.wait(2)
        bridge.findSimilar()
        release.set()
        _wait_idle(app, bridge)
        assert bridge.similarId(0) == "m3"
        spinner = root.findChild(QObject, "focusSearchSpinner")
        assert spinner.property("running") is False
        status = root.findChild(QObject, "focusSearchStatus")
        assert "1 match" in status.property("text")
        assert float(status.property("width")) > 80
    finally:
        release.set()
        shutdown_shell(engine)
