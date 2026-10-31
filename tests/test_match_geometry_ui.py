"""Phase B: strip rows carry match_norm; Focus can read matchNormFor."""

from __future__ import annotations

from pathlib import Path

import pytest


def _store(tmp_path):
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id in ("m1", "m2"):
        path = tmp_path / f"{media_id}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 100, 80, 0, 1),
        )
    conn.commit()
    conn.close()
    return store


def test_publish_similar_result_keeps_six_tuple_geometry(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.adapter import Result
    from semblon.native_shell.host import build_shell, shutdown_shell

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(_store(tmp_path), app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.openFocus("m1")
        result = Result(
            "ready",
            "Similar (Similar look): 1 match.",
            {
                "basis": "region",
                "basis_label": "Similar look",
                "items": [
                    {
                        "media_id": "m2",
                        "score": 0.91,
                        "match_nx": 0.1,
                        "match_ny": 0.2,
                        "match_nw": 0.3,
                        "match_nh": 0.4,
                    }
                ],
            },
        )
        bridge._publish_similar_result(result)
        rows = bridge._similar._rows
        assert len(rows) == 1
        assert rows[0][0] == "m2"
        assert rows[0][2:] == (0.1, 0.2, 0.3, 0.4)
        assert bridge.matchNormFor("m2") == [0.1, 0.2, 0.3, 0.4]
        zoomed = []
        bridge.focusMatchZoomRequested.connect(lambda: zoomed.append(True))
        bridge.openDiscoveryHit("m2")
        assert bridge.matchX == pytest.approx(0.1)
        assert bridge.matchW == pytest.approx(0.3)
        assert zoomed == [True]
        assert bridge.matchNormFor("m2") == [0.1, 0.2, 0.3, 0.4]

        qml = Path("semblon/native_shell/qml/Viewer.qml").read_text(encoding="utf-8")
        assert "stripMatchBox" in qml
        assert "focusMatchBox" in qml
        assert "previewMatchBox" in qml
        # Zoom once on openDiscoveryHit via Connections — not on every similar refresh.
        assert "onFocusMatchZoomRequested" in qml
        assert "zoomToMatchIfNeeded" in qml
        assert "onSimilarChanged" not in qml
    finally:
        shutdown_shell(engine)


def test_keep_rename_delete_atomic(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(_store(tmp_path), app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        bridge._publish_similar(
            "ready",
            "ok",
            [("m2", 0.5, 0.1, 0.2, 0.3, 0.4)],
            basis="region",
            basis_label="Similar look",
        )
        assert bridge.keepDiscovery() == "Kept this find."
        assert bridge.keptCount == 1
        assert bridge._keeps_file().is_file()
        assert bridge.keptName(0)
        assert bridge.renameKept(0, "Mug find") is True
        assert bridge.keptName(0) == "Mug find"
        assert bridge.keptLabel(0).startswith("Mug find")
        assert bridge.renameKept(0, "   ") is False
        assert bridge.keptName(0) == "Mug find"
        assert bridge.deleteKept(0) is True
        assert bridge.keptCount == 0
        assert not bridge._keeps_file().exists()
        table = Path("semblon/native_shell/qml/Table.qml").read_text(encoding="utf-8")
        assert "renameKeptField" in table
        assert "(renamed)" not in table
    finally:
        shutdown_shell(engine)
