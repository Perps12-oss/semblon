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
                "text": "TOTAL $12.00",
                "color": "#2e8b57",
                "nx": 0.1,
                "ny": 0.2,
                "nw": 0.4,
                "nh": 0.1,
            }
        ]
        bridge.focusChanged.emit()
        assert bridge.focusTextBoxes[0]["text"] == "TOTAL $12.00"
        bridge.selectTextBox("txt-1")
        assert bridge.selectionOnFocus is True
        assert abs(bridge.selectionX - 0.1) < 1e-6
        assert bridge.selectedText == "TOTAL $12.00"
        assert "TOTAL" in bridge.selectionNote
        note = bridge.ensureTextOverlay()
        assert "text regions ready" in note
    finally:
        shutdown_shell(engine)


def test_overlay_boxes_use_ocr_payload_text_not_provider():
    from semblon.canvas_data import overlay_boxes

    boxes = overlay_boxes(
        {
            "faces": [],
            "items": [
                {
                    "media_id": "m1",
                    "item_id": "w1",
                    "kind": "text",
                    "provider": "tesseract",
                    "bbox_x1": 1,
                    "bbox_y1": 2,
                    "bbox_x2": 10,
                    "bbox_y2": 20,
                    "payload": {"text": "TOTAL", "identity": "not facekit"},
                }
            ],
            "track_lane_by_face": {},
            "track_lane_by_item": {},
        },
        "m1",
    )
    assert len(boxes) == 1
    assert boxes[0]["tag"] == "TOTAL"
    assert boxes[0]["text"] == "TOTAL"


def test_ensure_text_overlay_creates_run_and_observation(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.category_backfill import ItemResult, ProviderProbe
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

    monkeypatch.setattr(
        "semblon.observers.probe_ocr_status",
        lambda: (True, None),
    )
    monkeypatch.setattr(
        "semblon.category_backfill.probe_category",
        lambda _c: ProviderProbe(True, "tesseract", "1", ""),
    )

    def fake_words(conn, img, *, media_id, observation_id, run_id, probe):
        # Must see real FK parents created by ensureTextOverlay.
        assert conn.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone()
        assert conn.execute(
            "SELECT 1 FROM observations WHERE observation_id=?", (observation_id,)
        ).fetchone()
        from semblon.observers import OCR_PROVIDER, persist_item

        persist_item(
            conn,
            observation_id=observation_id,
            run_id=run_id,
            kind="text",
            provider=OCR_PROVIDER,
            payload={"text": "TOTAL", "identity": "not facekit", "role": "word"},
            bbox=(10, 10, 80, 40),
            score=0.9,
        )
        return ItemResult("completed", "text")

    monkeypatch.setattr("semblon.category_backfill.process_words", fake_words)
    monkeypatch.setattr("cv2.imread", lambda _p: __import__("numpy").zeros((40, 80, 3), dtype="uint8"))

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.openFocus("m1")
        note = bridge.ensureTextOverlay()
        assert "text regions ready" in note
        assert any(b.get("kind") == "text" for b in bridge._focus_boxes)
        assert any(b.get("text") == "TOTAL" or b.get("tag") == "TOTAL" for b in bridge._focus_boxes)
    finally:
        shutdown_shell(engine)
