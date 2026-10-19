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


def _wait_install(app, bridge):
    deadline = time.time() + 3
    while time.time() < deadline:
        app.processEvents()
        thread = bridge._install_thread  # noqa: SLF001 - test seam
        if thread is None or not thread.isRunning():
            break
        time.sleep(0.02)
    app.processEvents()


def _screen_shell(tmp_path, monkeypatch, providers):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")
    from PySide6.QtWidgets import QApplication

    import semblon.native_shell.bridge as shell_bridge
    import semblon.native_shell.screen_query_overlay as overlay
    from semblon.application import Application
    from semblon.native_shell.host import build_shell

    monkeypatch.setattr(shell_bridge.sys, "platform", "win32")
    calls = {"screen": [], "overlay": 0}

    def fake_screen(self, x, y, w, h, **kwargs):
        calls["screen"].append((x, y, w, h, kwargs.get("selection_kind")))
        return {
            "source": "screen",
            "lines": ["Lens", "Selected area · 30×40"],
            "optional_providers": providers,
            "similar": {
                "status": "SUCCESS",
                "reason": "Merged selection matches from the local library.",
                "count": 1,
                "items": [{"media_id": "m2", "score": 0.8, "match_norm": [0.1, 0.2, 0.3, 0.4]}],
                "similarity_basis": "Similar look",
                "engine": "selection",
                "channels": [
                    {
                        "door": "object",
                        "status": "UNAVAILABLE",
                        "error_id": "object.PACK_MISSING",
                    }
                ]
                if any(row.get("id") == "object" and row.get("ready") is False for row in providers)
                else [],
            },
        }

    monkeypatch.setattr(Application, "query_screen", fake_screen)
    store = _store(tmp_path)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge

    def _select(parent=None):
        calls["overlay"] += 1
        assert bridge.screenQueryState == "selecting"
        return (10, 20, 30, 40)

    monkeypatch.setattr(overlay, "select_screen_region", _select)
    return app, engine, bridge, calls


def test_object_model_install_retries_the_same_screen_rect(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from semblon.native_shell.adapter import Result
    from semblon.native_shell.host import shutdown_shell

    providers = [
        {"id": "object", "ready": False, "state": "MISSING"},
        {"id": "vlm", "ready": False, "state": "MISSING"},
    ]
    app, engine, bridge, calls = _screen_shell(tmp_path, monkeypatch, providers)
    try:
        bridge.startScreenQuery()
        app.processEvents()
        assert bridge.similarState == "ready"
        assert bridge.installSuggestionVisible is True
        assert bridge.installSuggestionLabel == "Install object model"
        assert calls["overlay"] == 1
        assert calls["screen"] == [(10, 20, 30, 40, "region")]
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        installed = {"object": 0}

        def _install():
            installed["object"] += 1
            return Result("ready", "Object model installed. This search will run again.")

        monkeypatch.setattr(bridge._adapter, "install_object_pack", _install)  # noqa: SLF001 - test seam
        bridge.installSuggestedModel()
        _wait_install(app, bridge)
        assert installed["object"] == 1
        assert calls["overlay"] == 1
        assert calls["screen"] == [(10, 20, 30, 40, "region"), (10, 20, 30, 40, "region")]
        assert bridge.screenQueryState == "idle"
    finally:
        shutdown_shell(engine)


def test_description_install_retries_the_same_screen_rect(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from semblon.native_shell.adapter import Result
    from semblon.native_shell.host import shutdown_shell

    providers = [
        {"id": "object", "ready": True, "state": "AVAILABLE"},
        {"id": "vlm", "ready": False, "state": "MISSING"},
    ]
    app, engine, bridge, calls = _screen_shell(tmp_path, monkeypatch, providers)
    try:
        bridge.startScreenQuery()
        app.processEvents()
        assert bridge.installSuggestionVisible is True
        assert bridge.installSuggestionLabel == "Install description model"
        monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
        installed = {"vlm": 0}

        def _install():
            installed["vlm"] += 1
            return Result("ready", "Description model installed. This search will run again.")

        monkeypatch.setattr(bridge._adapter, "install_vlm", _install)  # noqa: SLF001 - test seam
        bridge.installSuggestedModel()
        _wait_install(app, bridge)
        assert installed["vlm"] == 1
        assert calls["overlay"] == 1
        assert len(calls["screen"]) == 2
        assert calls["screen"][0][:4] == calls["screen"][1][:4] == (10, 20, 30, 40)
    finally:
        shutdown_shell(engine)

