"""Discovery slice D: unified Focus results chrome with distinct basis labels."""

from __future__ import annotations

import pytest

from semblon.application import Application
from semblon.native_shell.adapter import ArchiveAdapter
from semblon.native_shell.presentation import is_primary_safe_message


def test_unified_basis_messages_are_allowlisted():
    for line in (
        "Similar (Colour only): 2 colour histogram matches.",
        "Similar (Colour only): no colour histogram matches.",
        "Similar (Same face): 3 matches.",
        "Similar (Similar look): 3 matches.",
        "Similar (Text in the selection): 1 match.",
        "Similar (Unknown region): 1 match.",
    ):
        assert is_primary_safe_message(line)


def test_adapter_region_and_whole_share_chrome_with_distinct_labels(tmp_path):
    store = tmp_path / "s.sqlite"
    from semblon.store import init_db
    import sqlite3

    conn = sqlite3.connect(str(store))
    init_db(conn)
    conn.close()
    adapter = ArchiveAdapter(Application(store))

    whole = adapter.similar_media("missing")
    assert whole.state == "unavailable"
    assert whole.data["basis"] == "whole"
    assert whole.data["basis_label"] == "Colour only"
    assert "colour" in whole.message.lower()
    assert whole.data["engine"] == "color-hist"

    region = adapter.similar_region(
        {
            "similar": {
                "status": "SUCCESS",
                "items": [{"media_id": "m2", "score": 0.9}],
            }
        }
    )
    assert region.state == "ready"
    assert region.data["basis"] == "region"
    assert region.data["basis_label"] == "Colour only"
    assert "colour histogram" in region.message.lower()
    assert "face" not in region.message.lower()
    assert region.data["items"][0]["media_id"] == "m2"

    face = adapter.similar_faces("")
    assert face.state == "unavailable"
    assert face.data["basis"] == "face"
    assert face.data["basis_label"] == "Same face"
    assert face.data["engine"] == "face-embed"
    assert "colour" not in face.message.lower()


def test_bridge_publishes_basis_for_region_and_whole(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        return {
            "region": {},
            "similar": {
                "status": "SUCCESS",
                "items": [{"media_id": "m2", "score": 0.88}],
            },
            "persons": 0,
        }

    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)

    photo = tmp_path / "a.png"
    photo.write_bytes(b"x")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h1", 40, 20, 3, 1),
    )
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m2", "folder", str(photo), "h2", 40, 20, 3, 1),
    )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openFocus("m1")
    bridge.setRegion(0.1, 0.1, 0.4, 0.4)
    bridge.findSimilar()
    assert bridge.similarState == "ready"
    assert bridge.similarBasis == "region"
    assert bridge.similarBasisLabel == "Colour only"
    assert "colour histogram" in bridge.similarNote.lower()
    assert "face" not in bridge.similarNote.lower()
    assert bridge.similarCount == 1

    bridge.findSimilarWhole()
    assert bridge.similarBasis == "whole"
    assert bridge.similarBasisLabel == "Colour only"
    assert "colour only" in bridge.similarNote.lower()
    shutdown_shell(engine)
