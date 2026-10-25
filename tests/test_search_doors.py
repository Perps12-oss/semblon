"""Focus doors stay distinct: similar region, same face, duplicates, whole photo."""

from __future__ import annotations

import re

import pytest

from semblon.native_shell.presentation import is_primary_safe_message


def test_focus_shortcuts_name_each_door():
    from pathlib import Path

    qml = Path("semblon/native_shell/qml/Viewer.qml").read_text(encoding="utf-8")
    for name in (
        "similarAction",
        "refineSameLook",
        "refineSameKind",
        "refineWord",
        "sameFaceDoor",
        "duplicatesDoor",
        "wholePhoto",
        "searchPhaseBadge",
        "nameConfidence",
    ):
        assert f'objectName: "{name}"' in qml
    assert 'label: "Find the picked area elsewhere"' in qml
    assert 'label: "Same look"' in qml
    assert 'label: "Same kind"' in qml
    assert "shell.setRefineMode" in qml
    assert "shell.setRefineModifier" in qml
    from semblon.native_shell.bridge import _PHASE_LABELS

    assert _PHASE_LABELS["checked"] == "Checked the matches"
    for key in ("S", "W", "F", "Ctrl+D"):
        assert f'sequence: "{key}"' in qml
    assert "shell.findSimilar" in qml
    assert "shell.scanDuplicates" in qml


def _store(tmp_path):
    import cv2
    import numpy as np

    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id, colour in (("m1", (40, 90, 180)), ("m2", (40, 160, 70))):
        path = tmp_path / f"{media_id}.png"
        image = np.zeros((80, 100, 3), np.uint8)
        image[:, :] = colour
        assert cv2.imwrite(str(path), image)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 100, 80, 0, 1),
        )
    conn.commit()
    conn.close()
    return store


def _settle(app, frames=20):
    import time

    for _ in range(frames):
        app.processEvents()
        time.sleep(0.03)


def test_doors_confidence_badge_and_timing(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        on_first = kwargs.get("on_first")
        if on_first is not None:
            on_first(
                {
                    "region": {},
                    "similar": {
                        "status": "SUCCESS",
                        "items": [
                            {
                                "media_id": "m2",
                                "score": 0.4,
                                "match_norm": [0.1, 0.2, 0.3, 0.4],
                            }
                        ],
                        "similarity_basis": "Similar look",
                        "engine": "dinov2-patch",
                        "search_phase": "first",
                    },
                    "persons": 0,
                    "wrote_embedding": False,
                }
            )
        return {
            "region": {},
            "similar": {
                "status": "SUCCESS",
                "items": [
                    {
                        "media_id": "m2",
                        "score": 0.8,
                        "match_norm": [0.1, 0.2, 0.3, 0.4],
                    }
                ],
                "similarity_basis": "Similar look",
                "engine": "dinov2-patch",
                "search_phase": "refined",
                "understanding": "Unlabelled region.",
            },
            "persons": 0,
            "wrote_embedding": False,
        }

    def fake_name(self, media_id, x, y, w, h, **kwargs):
        return {
            "status": "SUCCESS",
            "understanding": "Looks like a tree.",
            "confidence": 0.81,
            "persons": 0,
            "entity": False,
            "wrote_embedding": False,
        }

    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)
    monkeypatch.setattr(Application, "name_selection", fake_name)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(_store(tmp_path), app=app)
    bridge = engine._semblon_bridge
    root = engine.rootObjects()[0]
    try:
        root.setWidth(1100)
        root.setHeight(720)
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        _settle(app)
        assert root.findChild(QObject, "similarAction") is not None
        assert root.findChild(QObject, "sameFaceDoor") is not None
        assert root.findChild(QObject, "duplicatesDoor") is not None
        assert root.findChild(QObject, "wholePhoto") is not None
        bridge.findSimilar()
        _settle(app)
        assert bridge.searchDoorLabel == "Similar region"
        assert bridge.similarPhaseLabel == "Refined"
        assert bridge.similarId(0) == "m2"
        assert re.fullmatch(r"First look \d+ ms\. Refined \d+ ms\.", bridge.searchTimingLabel)
        assert is_primary_safe_message(bridge.searchTimingLabel)
        first = int(bridge.searchTimingLabel.split()[2])
        refined = int(bridge.searchTimingLabel.split()[5])
        assert refined >= first
        badge = root.findChild(QObject, "searchPhaseBadge")
        assert badge is not None
        assert badge.property("visible") is True
        bridge.nameSelection()
        _settle(app)
        assert bridge.nameNote == "Looks like a tree."
        assert bridge.nameConfidenceLabel == "Confidence 81%."
        assert is_primary_safe_message(bridge.nameConfidenceLabel)
        chip = root.findChild(QObject, "nameConfidence")
        assert chip is not None
        assert chip.property("visible") is True
        door = root.findChild(QObject, "searchDoorLabel")
        assert door is not None
        assert door.property("text") == "Similar region"
        for _ in range(6):
            app.processEvents()
        shot = root.grabWindow()
        assert shot.width() > 0
        out = tmp_path / "search-doors.png"
        assert shot.save(str(out))
        bridge.scanDuplicates()
        assert bridge.searchDoorLabel == "Duplicates"
        assert bridge.resultText.startswith("Duplicates:")
        assert is_primary_safe_message(bridge.resultText)
        assert bridge.similarId(0) == "m2"
        assert bridge.similarCount == 1
        bridge.findSimilarFaces()
        assert bridge.searchDoorLabel == "Same face"
        assert "face" in bridge.similarNote.lower()
        bridge.findSimilarWhole()
        assert bridge.searchDoorLabel == "Whole photo"
    finally:
        shutdown_shell(engine)
