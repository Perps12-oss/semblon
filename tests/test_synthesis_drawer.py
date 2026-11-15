"""Contextual Synthesis Drawer + sticky L-bracket crop (result-to-canvas follow-on)."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_synthesis_drawer_qml_contract():
    viewer = Path("semblon/native_shell/qml/Viewer.qml").read_text(encoding="utf-8")
    drawer = Path("semblon/native_shell/qml/SynthesisDrawer.qml").read_text(encoding="utf-8")
    qmldir = Path("semblon/native_shell/qml/qmldir").read_text(encoding="utf-8")
    assert "SynthesisDrawer 1.0 SynthesisDrawer.qml" in qmldir
    assert "synthesisDrawerHost" in viewer
    assert "cropScrim" in viewer
    assert "drawerOpen" in viewer
    assert "askAboutSelection" in viewer
    assert "liveCropThumb" in drawer
    assert "composerInput" in drawer
    assert "drawerMatchStrip" in drawer
    assert "drawerStripMatchBox" in drawer
    assert "activeFocusOnTab" in drawer
    assert "Accessible.onPressAction" in drawer
    assert "reasoningAccordion" in drawer


def test_media_badge_and_ask_about_selection(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    path = tmp_path / "circuit.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(path), "circuit.png", 1920, 1080, 0, 1),
    )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.openFocus("m1")
        badge = bridge.mediaBadgeFor("m1")
        assert "1920×1080" in badge
        assert "circuit.png" in badge
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        called = {"n": 0}

        def fake_name(self, media_id, x, y, w, h):
            called["n"] += 1
            return {"understanding": "A connector.", "confidence": 0.7}

        monkeypatch.setattr(bridge._jobs, "name_selection", fake_name.__get__(bridge._jobs, type(bridge._jobs)))
        monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")
        bridge.askAboutSelection("What is this connector?")
        assert bridge.resultText == "What is this connector?"
        deadline = __import__("time").time() + 2
        while called["n"] == 0 and __import__("time").time() < deadline:
            app.processEvents()
            __import__("time").sleep(0.02)
        assert called["n"] == 1
    finally:
        shutdown_shell(engine)


def test_drawer_opens_with_sticky_selection(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id, name in (("m1", "a.png"), ("m2", "b.png")):
        path = tmp_path / name
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), name, 100, 80, 0, 1),
        )
    conn.commit()
    conn.close()

    def hit(self, media_id, x, y, w, h, **kwargs):
        return {
            "region": {},
            "similar": {
                "status": "SUCCESS",
                "items": [
                    {
                        "media_id": "m2",
                        "score": 0.94,
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

    monkeypatch.setattr(Application, "remember_and_find_region", hit)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        bridge.findSimilar()
        from PySide6.QtCore import QEventLoop, QTimer

        loop = QEventLoop()
        QTimer.singleShot(120, loop.quit)
        loop.exec()
        assert bridge.selectionOnFocus is True
        assert bridge.similarState == "ready"
        for _ in range(10):
            app.processEvents()
        root = engine.rootObjects()[0]
        host = root.findChild(QObject, "synthesisDrawerHost")
        assert host is not None
        # Drawer should want to open with sticky selection + ready strip.
        assert host.property("open") is True
        assert root.findChild(QObject, "cropScrim") is not None
        assert root.findChild(QObject, "liveCropThumb") is not None
    finally:
        shutdown_shell(engine)
