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
    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell

    monkeypatch.setattr(overlay, "select_screen_region", lambda parent=None: (10, 20, 30, 40))

    def fake_screen(self, x, y, w, h, **kwargs):
        assert (x, y, w, h) == (10, 20, 30, 40)
        return {
            "source": "screen",
            "lines": ["Lens", "Selected area · 30×40", "Text: watch."],
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
        assert bridge.similarCount == 1
        assert bridge.similarId(0) == "m2"
        assert bridge.selectionNote == "Text: watch."
    finally:
        shutdown_shell(engine)


def test_start_screen_query_reports_unavailable_runtime(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    import semblon.native_shell.screen_query_overlay as overlay
    from semblon.native_shell.host import build_shell, shutdown_shell

    def _raise_unavailable(parent=None):
        raise overlay.ScreenSelectionUnavailable("Screen query is only available on Windows.")

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
        assert bridge.installSuggestionVisible is False
    finally:
        shutdown_shell(engine)

