"""Select Text mode — OCR overlays + ask-about-selected-text chip."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_ocr_select_text_qml_contract():
    viewer = Path("semblon/native_shell/qml/Viewer.qml").read_text(encoding="utf-8")
    drawer = Path("semblon/native_shell/qml/SynthesisDrawer.qml").read_text(encoding="utf-8")
    assert "textSelectOn" in viewer
    assert "textOverlay" in viewer
    assert "selectTextMode" in viewer
    assert "selectTextBox" in viewer
    assert "ensureTextOverlay" in viewer
    assert "chipAskText" in drawer
    assert "selectedText" in drawer


def test_select_text_box_snaps_sticky_crop(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    path = tmp_path / "receipt.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(path), "receipt.png", 200, 100, 0, 1),
    )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.openFocus("m1")
        bridge._focus_boxes = [
            {
                "id": "txt-1",
                "kind": "text",
                "source": "tesseract",
                "snap": True,
                "tag": "TOTAL $12.00",
                "color": "#2e8b57",
                "nx": 0.1,
                "ny": 0.2,
                "nw": 0.4,
                "nh": 0.1,
            }
        ]
        bridge.focusChanged.emit()
        assert bridge.focusTextBoxes[0]["tag"] == "TOTAL $12.00"
        bridge.selectTextBox("txt-1")
        assert bridge.selectionOnFocus is True
        assert abs(bridge.selectionX - 0.1) < 1e-6
        assert bridge.selectedText == "TOTAL $12.00"
        assert "TOTAL" in bridge.selectionNote
        note = bridge.ensureTextOverlay()
        assert "text regions ready" in note
    finally:
        shutdown_shell(engine)
