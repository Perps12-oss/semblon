"""Local visual discovery: understanding, kept finds, match box, patch index."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from semblon.region_search import describe_selection
from semblon.selection import click_adopts_box, point_box
from semblon.store import connect, init_db


def _run(conn) -> None:
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "emulated"),
    )


def _media(conn, media_id: str) -> None:
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        (media_id, "folder", f"/{media_id}.jpg", media_id, 80, 60, 0, 1),
    )
    conn.execute(
        "INSERT INTO observations VALUES (?,?,?,?,?)",
        (f"o-{media_id}", media_id, None, None, "r1"),
    )


def test_selection_understanding_is_not_a_person_name(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    _media(conn, "m1")
    conn.execute(
        """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
           det_score, face_w, face_h, size_band, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("f1", "o-m1", "r1", 4, 4, 30, 30, 0.9, 26, 26, "small", "ok"),
    )
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
           bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "obj",
            "o-m1",
            "r1",
            "object",
            "opencv-zoo-nanodet",
            40,
            4,
            70,
            30,
            0.8,
            json.dumps({"label": "cup", "class": "cup", "source": "nanodet"}),
        ),
    )
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
           bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "txt",
            "o-m1",
            "r1",
            "text",
            "tesseract",
            4,
            40,
            40,
            55,
            1,
            json.dumps({"text": "NORTH"}),
        ),
    )
    conn.commit()
    conn.close()
    assert describe_selection(store, "m1", 6, 6, 10, 10) == "Face in the selection. Not a named person."
    assert describe_selection(store, "m1", 45, 8, 12, 12) == "Object: cup."
    conn = connect(store)
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
           bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "drawn",
            "o-m1",
            "r1",
            "object",
            "user_box",
            80,
            60,
            96,
            76,
            1,
            json.dumps({"class": "user_region"}),
        ),
    )
    conn.commit()
    conn.close()
    assert describe_selection(store, "m1", 82, 62, 8, 8) == "Unlabelled region."
    assert describe_selection(store, "m1", 6, 42, 20, 10) == "Text: NORTH."
    plain = describe_selection(store, "m1", 70, 40, 8, 8)
    assert plain == "Unlabelled region."
    crop = np.zeros((8, 8, 3), np.uint8)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("semblon.visual.naming_local.name_crop_bgr", lambda _crop: "Looks like a tree.")
    try:
        assert describe_selection(store, "m1", 70, 40, 8, 8, crop=crop) == "Looks like a tree."
        assert describe_selection(store, "m1", 6, 6, 10, 10, crop=crop) == (
            "Face in the selection. Not a named person."
        )
    finally:
        monkeypatch.undo()
    conn = connect(store)
    assert conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0] == 0
    conn.close()


def test_click_adopts_a_detector_box_and_not_a_contour():
    assert click_adopts_box("face") is True
    assert click_adopts_box("text") is True
    assert click_adopts_box("object", "nanodet") is True
    assert click_adopts_box("object", "contour") is False
    assert click_adopts_box("object", "") is False
    box = point_box(50, 40, 100, 80)
    assert box == (34, 24, 32, 32)
    assert point_box(10, 8, 50, 40) == (0, 0, 32, 32)


def test_absent_namer_stays_unlabelled(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    _media(conn, "m1")
    conn.commit()
    conn.close()
    monkeypatch.setattr("semblon.visual.naming_local.name_crop_bgr", lambda _crop: None)
    crop = np.zeros((8, 8, 3), np.uint8)
    assert describe_selection(store, "m1", 4, 4, 8, 8, crop=crop) == "Unlabelled region."


def test_keep_discovery_and_match_overlay(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id, name in (("m1", "a.png"), ("m2", "b.png")):
        path = tmp_path / name
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"x" * 16
        )
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 100, 80, 0, 1),
        )
    conn.commit()
    conn.close()

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        return {
            "region": {},
            "similar": {
                "status": "SUCCESS",
                "items": [
                    {
                        "media_id": "m2",
                        "score": 0.91,
                        "match_norm": [0.2, 0.3, 0.25, 0.2],
                    }
                ],
                "similarity_basis": "Similar look",
                "engine": "dinov2-patch",
                "modality": "region_patch",
                "understanding": "Unlabelled region.",
            },
            "persons": 0,
            "wrote_embedding": False,
        }

    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.1, 0.3, 0.3)
        bridge.findSimilar()
        assert bridge.selectionNote == "Unlabelled region."
        assert bridge.similarCount == 1
        assert bridge.matchW == 0.0
        bridge.openDiscoveryHit("m2")
        assert bridge.focusId == "m2"
        assert bridge.similarCount == 1
        assert abs(bridge.matchX - 0.2) < 1e-6
        assert abs(bridge.matchW - 0.25) < 1e-6
        assert bridge.canBackDiscovery is True
        assert bridge.keepDiscovery() == "Kept this find."
        assert bridge.keptCount == 1
        assert "Unlabelled" in bridge.keptLabel(0)
        kept = json.loads((tmp_path / "s.discoveries.json").read_text(encoding="utf-8"))
        assert kept[0]["query_media_id"] == "m1"
        assert kept[0]["items"][0]["media_id"] == "m2"
        bridge.openFocus("m1")
        bridge.openKept(0)
        assert bridge.focusId == "m1"
        assert bridge.similarCount == 1
        bridge.backToDiscovery()
    finally:
        shutdown_shell(engine)


def test_patch_index_covers_more_than_proposals(tmp_path):
    from semblon.region_encoder import MODALITY_PATCH, probe_region_pack

    ready, _note = probe_region_pack()
    if not ready:
        pytest.skip("region pack not installed")
    import cv2

    from semblon.observers import observe_bgr

    image = np.full((140, 180, 3), 30, dtype=np.uint8)
    cv2.rectangle(image, (8, 8), (36, 40), (20, 180, 40), -1)
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    _media(conn, "m1")
    observe_bgr(conn, observation_id="o-m1", run_id="r1", img=image, observers=("region",))
    conn.commit()
    patches = conn.execute(
        "SELECT COUNT(*) FROM embeddings WHERE modality=?",
        (MODALITY_PATCH,),
    ).fetchone()[0]
    faces = conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
    corner = conn.execute(
        """SELECT COUNT(*) FROM observation_items i
           JOIN embeddings e ON e.item_id = i.item_id
           WHERE e.modality=? AND i.bbox_x1 < 20 AND i.bbox_y1 < 20""",
        (MODALITY_PATCH,),
    ).fetchone()[0]
    conn.close()
    assert patches > 6
    assert corner >= 1
    assert faces == 0
