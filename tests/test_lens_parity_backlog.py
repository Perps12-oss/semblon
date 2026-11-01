"""Post-2D Lens-parity Focus backlog: refine, escalate, adopt, pins, LOW_INFO."""

from __future__ import annotations

from pathlib import Path

import pytest

from semblon.native_shell.presentation import is_primary_safe_message


def test_viewer_and_hotspots_expose_parity_actions():
    viewer = Path("semblon/native_shell/qml/Viewer.qml").read_text(encoding="utf-8")
    hotspots = Path("semblon/native_shell/qml/Hotspots.qml").read_text(encoding="utf-8")
    for name in (
        "selectionBox",
        "lowInfoRecovery",
        "expandSelection",
        "lowInfoWhole",
        "lowInfoRedraw",
        "escalateWhole",
        "pinBar",
        "searchPinnedDots",
        "clearPinnedDots",
    ):
        assert f'objectName: "{name}"' in viewer, name
    assert "shell.commitSelectionPixels" in viewer
    assert "shell.adjustSelectionBox" in viewer
    assert "shell.expandSelection" in viewer
    assert "shell.searchWholeFocus" in viewer
    assert "shell.canEscalateWhole" in viewer
    assert "shell.lowInfoRecovery" in viewer
    assert "shell.searchPinnedDots" in viewer
    for name in ("dotSearchByLook", "dotPinToggle", "dotPin"):
        assert f'objectName: "{name}"' in hotspots, name
    assert "shell.adoptDotAsRegion" in hotspots
    assert "shell.togglePinnedDot" in hotspots
    assert "shell.pinnedDotIds" in hotspots
    for literal in (
        "Search this area by look",
        "Add to combined find",
        "Remove from combined find",
        "Expand selection",
        "Search this whole photo",
        "Find every pinned clue",
    ):
        assert literal in viewer or literal in hotspots


def test_combined_find_messages_are_primary_safe():
    for line in (
        "Pin at most four dots for a combined find.",
        "Pin at least two dots, then search the combination.",
        "Combined find needs a face with a thing, or two areas.",
        "Similar (Combined find): nothing close enough.",
        "Similar (Combined find): 2 photos with every pinned clue.",
        "Selected from a dot.",
    ):
        assert is_primary_safe_message(line), line


def _png(path: Path) -> None:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)


def _shell(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id, name in (("m1", "a.png"), ("m2", "b.png"), ("m3", "c.png")):
        path = tmp_path / name
        _png(path)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 100, 80, 0, 1),
        )
    conn.commit()
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")

    def _hit(media_id: str):
        return {
            "region": {},
            "similar": {
                "status": "SUCCESS",
                "items": [
                    {
                        "media_id": media_id,
                        "score": 0.5,
                        "match_norm": [0.1, 0.2, 0.3, 0.4],
                    }
                ],
                "similarity_basis": "Similar look",
                "engine": "dinov2-patch",
            },
            "persons": 0,
            "wrote_embedding": False,
        }

    monkeypatch.setattr(
        Application,
        "remember_and_find_region",
        lambda self, media_id, x, y, w, h, **kwargs: _hit("m2"),
    )
    bridge.openFocus("m1")
    return app, engine, bridge


def test_expand_and_commit_refine_the_selection(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    _app, engine, bridge = _shell(tmp_path, monkeypatch)
    try:
        bridge.setRegion(0.20, 0.20, 0.20, 0.20)
        bridge.findSimilar()
        assert bridge.similarState == "ready"
        assert bridge.selectionOnFocus is True
        before = (bridge.selectionX, bridge.selectionY, bridge.selectionW, bridge.selectionH)
        bridge.expandSelection()
        assert bridge.selectionW > before[2]
        assert bridge.selectionH > before[3]
        assert bridge.selectionX < before[0]
        assert bridge.selectionY < before[1]
        bridge.commitSelectionPixels(10, 10, 40, 30, 100, 80)
        assert abs(bridge.selectionX - 0.10) < 1e-6
        assert abs(bridge.selectionW - 0.40) < 1e-6
        assert bridge.similarState == "ready"
    finally:
        shutdown_shell(engine)


def test_low_info_and_escalate_flags(tmp_path, monkeypatch):
    from semblon.native_shell.adapter import Result
    from semblon.native_shell.host import shutdown_shell

    _app, engine, bridge = _shell(tmp_path, monkeypatch)
    try:
        bridge.setRegion(0.1, 0.1, 0.2, 0.2)
        bridge._publish_similar_result(
            Result(
                "empty",
                "Similar (Colour only): pick a more detailed area.",
                {
                    "basis": "region",
                    "basis_label": "Colour only",
                    "low_info": True,
                    "error_id": "region.LOW_INFO",
                    "items": [],
                },
            )
        )
        assert bridge.lowInfoRecovery is True
        assert bridge.canEscalateWhole is False
        bridge.openDiscoveryHit("m2")
        assert bridge.focusId == "m2"
        assert bridge.selectionOnFocus is False
        assert bridge.canEscalateWhole is True
        bridge.searchWholeFocus()
        # Whole search may be unavailable without embeddings; flag just must clear low-info.
        assert bridge.lowInfoRecovery is False
    finally:
        shutdown_shell(engine)


def test_adopt_dot_and_pinned_combined_find(tmp_path, monkeypatch):
    from semblon.native_shell.adapter import Result
    from semblon.native_shell.host import shutdown_shell

    _app, engine, bridge = _shell(tmp_path, monkeypatch)
    try:
        bridge._focus_boxes = [
            {
                "id": "face-1",
                "kind": "face",
                "source": "face",
                "snap": True,
                "tag": "",
                "nx": 0.1,
                "ny": 0.1,
                "nw": 0.2,
                "nh": 0.25,
            },
            {
                "id": "obj-1",
                "kind": "object",
                "source": "nanodet",
                "snap": True,
                "tag": "Mug",
                "nx": 0.5,
                "ny": 0.4,
                "nw": 0.2,
                "nh": 0.2,
            },
        ]
        bridge.adoptDotAsRegion("obj-1")
        assert bridge.selectionOnFocus is True
        assert abs(bridge.selectionX - 0.5) < 1e-6
        assert bridge.selectionNote == "Selected from a dot."
        assert bridge.similarState == "ready"

        bridge.togglePinnedDot("face-1")
        bridge.togglePinnedDot("obj-1")
        assert bridge.pinnedDotCount == 2
        assert bridge.isDotPinned("face-1") is True

        def fake_faces(_fid):
            return Result(
                "ready",
                "Similar (Same face): 2 matches.",
                {
                    "basis": "face",
                    "basis_label": "Same face",
                    "items": [
                        {"media_id": "m2", "score": 0.9, "match_nx": 0, "match_ny": 0, "match_nw": 0.1, "match_nh": 0.1},
                        {"media_id": "m3", "score": 0.8, "match_nx": 0, "match_ny": 0, "match_nw": 0.1, "match_nh": 0.1},
                    ],
                },
            )

        monkeypatch.setattr(bridge._adapter, "similar_faces", fake_faces)
        bridge.searchPinnedDots()
        assert bridge.similarBasisLabel == "Combined find"
        assert bridge.similarState == "ready"
        assert bridge.similarCount == 1
        assert bridge.similarId(0) == "m2"

        bridge.togglePinnedDot("face-1")
        assert bridge.pinnedDotCount == 1
        bridge.clearPinnedDots()
        assert bridge.pinnedDotCount == 0
    finally:
        shutdown_shell(engine)


def test_pin_guards(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    _app, engine, bridge = _shell(tmp_path, monkeypatch)
    try:
        bridge.searchPinnedDots()
        assert "at least two" in bridge.resultText
        for i in range(4):
            bridge.togglePinnedDot(f"d{i}")
        assert bridge.pinnedDotCount == 4
        bridge.togglePinnedDot("d4")
        assert bridge.pinnedDotCount == 4
        assert "four" in bridge.resultText
    finally:
        shutdown_shell(engine)
