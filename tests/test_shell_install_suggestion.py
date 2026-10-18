from __future__ import annotations

import time

import pytest


def _png(path):
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)


def _store(tmp_path):
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    photo = tmp_path / "a.png"
    _png(photo)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h1", 100, 80, 0, 1),
    )
    conn.commit()
    conn.close()
    return store


def test_region_model_install_suggestion_retries_search(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")
    from PySide6.QtWidgets import QApplication, QMessageBox

    from semblon.application import Application
    from semblon.native_shell.adapter import Result
    from semblon.native_shell.host import build_shell, shutdown_shell

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        return {
            "region": {},
            "similar": {
                "status": "UNAVAILABLE",
                "reason": "Region encoder is missing.",
                "error_id": "region.NO_PACK",
                "items": [],
                "similarity_basis": "Similar look",
                "engine": "dinov2-patch",
            },
            "persons": 0,
            "wrote_embedding": False,
        }

    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)
    store = _store(tmp_path)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.1, 0.3, 0.3)
        bridge.findSimilar()
        app.processEvents()
        assert bridge.similarState == "unavailable"
        assert bridge.installSuggestionVisible is True
        assert "region model" in bridge.installSuggestionLabel.lower()

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )
        monkeypatch.setattr(
            bridge._adapter,  # noqa: SLF001 - test seam
            "install_region_pack",
            lambda: Result("ready", "Region model installed. Similar look will retry now."),
        )
        retried = {"count": 0}
        monkeypatch.setattr(bridge, "findSimilar", lambda: retried.__setitem__("count", retried["count"] + 1))
        bridge.installSuggestedModel()
        deadline = time.time() + 3
        while time.time() < deadline:
            app.processEvents()
            thread = bridge._install_thread  # noqa: SLF001 - test seam
            if thread is None or not thread.isRunning():
                break
            time.sleep(0.02)
        app.processEvents()
        assert retried["count"] == 1
    finally:
        shutdown_shell(engine)

