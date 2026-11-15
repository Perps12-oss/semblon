"""Turn-bound crop history + zero-prompt starter chips in the Synthesis Drawer."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_turn_history_and_chips_qml_contract():
    drawer = Path("semblon/native_shell/qml/SynthesisDrawer.qml").read_text(encoding="utf-8")
    assert "synthesisTurnList" in drawer
    assert "starterChips" in drawer
    assert "restoreSynthesisTurn" in drawer
    assert "chipDescribe" in drawer
    assert "chipTopMatch" in drawer
    assert "chipKeep" in drawer


def test_ask_freezes_crop_and_restore_snaps_back(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id, name, w, h in (("m1", "a.png", 100, 80), ("m2", "b.png", 200, 160)):
        path = tmp_path / name
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), name, w, h, 0, 1),
        )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge

    def fake_name(self, media_id, x, y, w, h):
        return {"understanding": f"Named {media_id}.", "confidence": 0.8}

    monkeypatch.setattr(
        bridge._jobs,
        "name_selection",
        fake_name.__get__(bridge._jobs, type(bridge._jobs)),
    )
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.10, 0.20, 0.30, 0.25)
        bridge.askAboutSelection("What is region A?")
        deadline = __import__("time").time() + 2
        while len(bridge.synthesisTurns) < 1 and __import__("time").time() < deadline:
            app.processEvents()
            __import__("time").sleep(0.02)
        assert len(bridge.synthesisTurns) == 1
        turn = bridge.synthesisTurns[0]
        assert turn["prompt"] == "What is region A?"
        assert turn["media_id"] == "m1"
        assert turn["region"][0] == pytest.approx(0.10)
        assert "Named m1" in turn["reply"]

        # Second turn on a different crop of the same photo.
        bridge.setRegion(0.50, 0.50, 0.20, 0.20)
        bridge.askAboutSelection("What is region B?")
        deadline = __import__("time").time() + 2
        while len(bridge.synthesisTurns) < 2 and __import__("time").time() < deadline:
            app.processEvents()
            __import__("time").sleep(0.02)
        assert len(bridge.synthesisTurns) == 2

        # Restore first turn — L-bracket snaps back.
        bridge.restoreSynthesisTurn(0)
        assert bridge.focusId == "m1"
        assert bridge.selectionOnFocus is True
        assert abs(bridge.selectionX - 0.10) < 1e-6
        assert abs(bridge.selectionW - 0.30) < 1e-6
        assert bridge.resultText == "What is region A?"
        assert "Named m1" in bridge.nameNote
    finally:
        shutdown_shell(engine)
