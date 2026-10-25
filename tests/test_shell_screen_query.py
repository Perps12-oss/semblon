from __future__ import annotations

import pytest


def _png(path):
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)


def _store(tmp_path):
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id, name in (("m1", "a.png"), ("m2", "b.png")):
        path = tmp_path / name
        _png(path)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 100, 80, 0, 1),
        )
    conn.commit()
    conn.close()
    return store


def test_start_screen_query_populates_similar_strip(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    import semblon.native_shell.screen_query_overlay as overlay
    import semblon.native_shell.bridge as shell_bridge
    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell

    monkeypatch.setattr(shell_bridge.sys, "platform", "win32")

    def fake_screen(self, x, y, w, h, **kwargs):
        assert (x, y, w, h) == (10, 20, 30, 40)
        assert kwargs.get("selection_kind") == "region"
        return {
            "source": "screen",
            "lines": ["Lens", "Selected area · 30×40", "Text: watch."],
            "observations": [
                {
                    "kind": "text",
                    "provider": "ocr",
                    "payload": {"text": "watch", "role": "ocr"},
                }
            ],
            "similar": {
                "status": "SUCCESS",
                "reason": "Matching region in your archive.",
                "count": 1,
                "items": [{"media_id": "m2", "score": 0.91, "match_norm": [0.1, 0.2, 0.3, 0.4]}],
                "similarity_basis": "Similar look",
                "engine": "dinov2-patch",
            },
        }

    monkeypatch.setattr(Application, "query_screen", fake_screen)
    store = _store(tmp_path)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    monkeypatch.setattr(overlay, "select_screen_region", lambda parent=None: _assert_selecting(bridge))
    try:
        bridge.startScreenQuery()
        app.processEvents()
        assert bridge.similarState == "ready"
        assert bridge.similarCount == 1
        assert bridge.similarId(0) == "m2"
        assert bridge.selectionNote == "Text: watch."
        assert bridge.screenQueryState == "idle"
    finally:
        shutdown_shell(engine)


def test_start_screen_query_uses_promoted_observations_for_understanding(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    import semblon.native_shell.bridge as shell_bridge
    import semblon.native_shell.screen_query_overlay as overlay
    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell

    monkeypatch.setattr(shell_bridge.sys, "platform", "win32")
    monkeypatch.setattr(overlay, "select_screen_region", lambda parent=None: (10, 20, 30, 40))

    def fake_screen(self, x, y, w, h, **kwargs):
        return {
            "source": "screen",
            "lines": ["Lens", "Selected area · 30×40"],
            "observations": [
                {
                    "kind": "text",
                    "provider": "ocr",
                    "payload": {"text": "watch strap", "role": "ocr"},
                }
            ],
            "similar": {
                "status": "SUCCESS",
                "reason": "Matching region in your archive.",
                "count": 1,
                "items": [{"media_id": "m2", "score": 0.91, "match_norm": [0.1, 0.2, 0.3, 0.4]}],
                "similarity_basis": "Similar look",
                "engine": "dinov2-patch",
            },
        }

    monkeypatch.setattr(Application, "query_screen", fake_screen)
    store = _store(tmp_path)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.startScreenQuery()
        app.processEvents()
        assert bridge.similarState == "ready"
        assert bridge.selectionNote == "Text: watch."
    finally:
        shutdown_shell(engine)


def _assert_selecting(bridge):
    assert bridge.screenQueryState == "selecting"
    assert bridge.screenQueryInProgress is True
    return (10, 20, 30, 40)


def test_start_screen_query_text_priority_mode(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    import semblon.native_shell.bridge as shell_bridge
    import semblon.native_shell.screen_query_overlay as overlay
    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell

    monkeypatch.setattr(shell_bridge.sys, "platform", "win32")
    monkeypatch.setattr(overlay, "select_screen_region", lambda parent=None: (1, 2, 30, 20))

    seen = {}

    def fake_screen(self, x, y, w, h, **kwargs):
        seen["selection_kind"] = kwargs.get("selection_kind")
        return {
            "source": "screen",
            "lines": ["Lens", "Selected area · 30×20", "Text: label."],
            "similar": {
                "status": "SUCCESS",
                "reason": "Found text.",
                "count": 1,
                "items": [{"media_id": "m2", "score": 0.8}],
                "similarity_basis": "Text in the selection",
                "engine": "ocr",
            },
        }

    monkeypatch.setattr(Application, "query_screen", fake_screen)
    store = _store(tmp_path)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        assert bridge.screenQueryMode == "visual"
        bridge.toggleScreenQueryMode()
        assert bridge.screenQueryMode == "text_priority"
        assert "text first" in bridge.screenQueryModeLabel.lower()
        bridge.startScreenQuery()
        app.processEvents()
        assert seen["selection_kind"] == "text_priority"
        assert bridge.similarState == "ready"
    finally:
        shutdown_shell(engine)


def test_start_screen_query_reports_unavailable_runtime(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    import semblon.native_shell.bridge as shell_bridge
    import semblon.native_shell.screen_query_overlay as overlay
    from semblon.native_shell.host import build_shell, shutdown_shell

    monkeypatch.setattr(shell_bridge.sys, "platform", "win32")

    def _raise_unavailable(parent=None):
        raise overlay.ScreenSelectionUnavailable("Picking on screen is only available on Windows.")

    monkeypatch.setattr(overlay, "select_screen_region", _raise_unavailable)
    store = _store(tmp_path)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.startScreenQuery()
        app.processEvents()
        assert bridge.similarState == "unavailable"
        assert bridge.similarNote
        assert bridge.screenQueryState == "idle"
        assert bridge.installSuggestionVisible is False
    finally:
        shutdown_shell(engine)

