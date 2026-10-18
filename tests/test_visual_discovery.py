"""Region retrieval: pack isolation, floors, identity firewall, continuity."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from semblon.observers import APPEARANCE_DIM, APPEARANCE_PACK, color_histogram, observe_bgr
from semblon.region_encoder import (
    COLOUR_SCORE_FLOOR,
    MODALITY_REGION,
    MODALITY_SCENE,
    REGION_SCORE_FLOOR,
    pack_id_for,
    probe_region_pack,
)
from semblon.region_search import remember_and_find, search_vector
from semblon.search import non_face_item_for_media, search_similar_media
from semblon.store import connect, init_db


def _run(conn) -> None:
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "emulated"),
    )


def _media(conn, media_id: str, path: str) -> None:
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        (media_id, "folder", path, media_id, 64, 64, 0, 1),
    )
    conn.execute(
        "INSERT INTO observations VALUES (?,?,?,?,?)",
        (f"o-{media_id}", media_id, None, None, "r1"),
    )


def _vec(fill: float, dim: int = 4) -> bytes:
    arr = np.full(dim, fill, dtype=np.float32)
    arr = arr / np.linalg.norm(arr)
    return arr.tobytes()


def _put_embedding(conn, *, item: str, obs: str, modality: str, pack: str, blob: bytes, bbox=None):
    x1 = y1 = x2 = y2 = None
    if bbox:
        x1, y1, x2, y2 = bbox
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
           bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (item, obs, "r1", "clip", "test", x1, y1, x2, y2, 1.0, "{}"),
    )
    conn.execute(
        """INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
           VALUES (?,?,?,?,?,?)""",
        (item + "-e", item, modality, pack, len(blob) // 4, blob),
    )


def test_region_query_ignores_scene_and_other_packs(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    _media(conn, "m1", "/a.jpg")
    _media(conn, "m2", "/b.jpg")
    pack = "region/dinov2-vits14@1/abc/cls"
    blob = _vec(1.0)
    _put_embedding(conn, item="scene", obs="o-m2", modality=MODALITY_SCENE, pack=pack, blob=blob)
    _put_embedding(conn, item="other", obs="o-m2", modality=MODALITY_REGION, pack="region/other", blob=blob)
    _put_embedding(conn, item="hit", obs="o-m2", modality=MODALITY_REGION, pack=pack, blob=blob)
    conn.commit()
    conn.close()
    rec = search_vector(
        store,
        blob=blob,
        modality=MODALITY_REGION,
        pack_id=pack,
        dim=4,
        exclude_media_id="m1",
        min_score=0.99,
    )
    assert rec["status"] == "SUCCESS"
    assert [item["item_id"] for item in rec["items"]] == ["hit"]


def test_source_exclusion_dedupe_and_floor(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    _media(conn, "src", "/a.jpg")
    _media(conn, "dup", "/b.jpg")
    _media(conn, "weak", "/c.jpg")
    pack = "region/test@1"
    strong = _vec(1.0)
    weak = np.zeros(4, dtype=np.float32)
    weak[0] = 1.0
    weak = (weak / np.linalg.norm(weak)).tobytes()
    _put_embedding(conn, item="self", obs="o-src", modality=MODALITY_REGION, pack=pack, blob=strong)
    _put_embedding(conn, item="dup-a", obs="o-dup", modality=MODALITY_REGION, pack=pack, blob=strong)
    _put_embedding(conn, item="dup-b", obs="o-dup", modality=MODALITY_REGION, pack=pack, blob=strong)
    _put_embedding(conn, item="weak", obs="o-weak", modality=MODALITY_REGION, pack=pack, blob=weak)
    conn.commit()
    conn.close()
    rec = search_vector(
        store,
        blob=strong,
        modality=MODALITY_REGION,
        pack_id=pack,
        dim=4,
        exclude_media_id="src",
        min_score=0.9,
    )
    ids = [item["media_id"] for item in rec["items"]]
    assert ids == ["dup"]
    assert "src" not in ids
    assert "weak" not in ids


def test_whole_image_picks_scene_not_lowest_uuid(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    _media(conn, "m1", "/a.jpg")
    _media(conn, "m2", "/b.jpg")
    colour = color_histogram(np.zeros((8, 8, 3), dtype=np.uint8))
    scene = _vec(0.2, dim=4)
    # UUID order would prefer the colour row if item ids sort that way.
    _put_embedding(
        conn, item="000-colour", obs="o-m1", modality="appearance", pack=APPEARANCE_PACK, blob=colour
    )
    _put_embedding(conn, item="zzz-scene", obs="o-m1", modality=MODALITY_SCENE, pack="region/scene", blob=scene)
    other = _vec(0.2, dim=4)
    _put_embedding(conn, item="scene-2", obs="o-m2", modality=MODALITY_SCENE, pack="region/scene", blob=other)
    conn.commit()
    conn.close()
    assert non_face_item_for_media(store, "m1") == "zzz-scene"
    rec = search_similar_media(store, "m1", limit=5)
    assert rec["modality"] == MODALITY_SCENE
    assert rec["similarity_basis"] == "Similar look"
    assert all(item["media_id"] != "m1" for item in rec["items"])


def test_colour_fallback_when_model_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "semblon.region_encoder.probe_region_pack",
        lambda root=None: (False, "unavailable: region encoder missing"),
    )
    monkeypatch.setattr(
        "semblon.region_search.probe_region_pack",
        lambda root=None: (False, "unavailable: region encoder missing"),
    )
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    green = np.zeros((32, 32, 3), dtype=np.uint8)
    green[:, :] = (0, 220, 0)
    other = np.zeros((32, 32, 3), dtype=np.uint8)
    other[:, :] = (0, 210, 0)
    other[0, 0] = (1, 210, 0)
    _media(conn, "m1", "/a.jpg")
    _media(conn, "m2", "/b.jpg")
    observe_bgr(conn, observation_id="o-m1", run_id="r1", img=green, observers=("color",))
    observe_bgr(conn, observation_id="o-m2", run_id="r1", img=other, observers=("color",))
    conn.commit()
    conn.close()
    photo = tmp_path / "a.jpg"
    import cv2

    cv2.imwrite(str(photo), green)
    before = connect(store).execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    rec = remember_and_find(store, media_id="m1", image_path=photo, x=0, y=0, w=16, h=16)
    conn = connect(store)
    persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    face_rows = conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
    conn.close()
    similar = rec["similar"]
    assert similar["similarity_basis"] == "Colour only"
    assert similar["modality"] == "appearance"
    assert similar["engine"] == "color-hist"
    assert persons == before == 0
    assert face_rows == 0
    assert rec["wrote_embedding"] is False
    assert COLOUR_SCORE_FLOOR > 0
    if similar["status"] == "SUCCESS":
        assert all(item["media_id"] != "m1" for item in similar["items"])


def test_text_overlap_does_not_use_colour(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "semblon.region_search.probe_region_pack",
        lambda root=None: (False, "missing"),
    )
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    _media(conn, "m1", "/a.jpg")
    _media(conn, "m2", "/b.jpg")
    for media, obs in (("m1", "o-m1"), ("m2", "o-m2")):
        conn.execute(
            """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
               bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f"t-{media}",
                obs,
                "r1",
                "text",
                "tesseract",
                0,
                0,
                40,
                20,
                1,
                json.dumps({"text": "NORTH", "contract_status": "SUCCESS"}),
            ),
        )
    conn.commit()
    conn.close()
    photo = tmp_path / "a.jpg"
    import cv2

    cv2.imwrite(str(photo), np.full((64, 64, 3), 255, dtype=np.uint8))
    rec = remember_and_find(
        store,
        media_id="m1",
        image_path=photo,
        x=2,
        y=2,
        w=20,
        h=10,
        selection_kind="text",
    )
    similar = rec["similar"]
    assert similar["similarity_basis"] == "Text in the selection"
    assert similar["modality"] == "text"
    assert similar["engine"] == "ocr"
    assert any(item["media_id"] == "m2" for item in similar["items"])
    assert all(item["media_id"] != "m1" for item in similar["items"])


def test_face_path_is_not_region_embedding(tmp_path, monkeypatch):
    called = {"faces": 0}

    def _faces(store, face_id, **kwargs):
        called["faces"] += 1
        return {
            "status": "NO_RESULT",
            "items": [],
            "similarity_basis": "Same face",
            "modality": "face",
        }

    monkeypatch.setattr("semblon.search.search_similar_faces", _faces)
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    conn.commit()
    conn.close()
    from semblon.application import Application
    from semblon.native_shell.adapter import ArchiveAdapter

    adapter = ArchiveAdapter(Application(store))
    result = adapter.similar_faces("face-1")
    assert called["faces"] == 1
    assert result.data["basis"] == "face"
    assert result.data["basis_label"] == "Same face"
    assert result.data["engine"] == "face-embed"


def test_incremental_region_index_reopens(tmp_path):
    ready, _note = probe_region_pack()
    if not ready:
        pytest.skip("region pack not installed")
    import cv2

    from semblon.region_encoder import KNOWN_SHA256, WEIGHT_NAME

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    image = np.full((96, 96, 3), 240, dtype=np.uint8)
    cv2.rectangle(image, (20, 30), (70, 80), (20, 30, 200), -1)
    cv2.circle(image, (30, 40), 6, (0, 220, 220), -1)
    _media(conn, "m1", str(tmp_path / "a.png"))
    observe_bgr(conn, observation_id="o-m1", run_id="r1", img=image, observers=("region",))
    conn.commit()
    conn.close()
    conn = connect(store)
    rows = conn.execute(
        "SELECT modality, pack_id, embedding_dim FROM embeddings WHERE modality IN ('region', 'scene')"
    ).fetchall()
    persons = conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
    conn.close()
    assert rows
    assert persons == 0
    pack = pack_id_for(KNOWN_SHA256[WEIGHT_NAME])
    assert pack.startswith("region/dinov2-vits14@")
    assert {row[0] for row in rows} >= {"region", "scene"}
    assert all(row[1] == pack for row in rows)
    assert all(row[2] == 384 for row in rows)
    # Close and reopen: vectors are still the stored bytes.
    conn = connect(store)
    again = conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='region'").fetchone()[0]
    conn.close()
    assert again >= 1


def test_open_discovery_hit_keeps_query_context(tmp_path, monkeypatch):
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
        path.write_bytes(b"x")
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 40, 40, 0, 1),
        )
    conn.commit()
    conn.close()

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        return {
            "region": {},
            "similar": {
                "status": "SUCCESS",
                "items": [{"media_id": "m2", "score": 0.91}],
                "similarity_basis": "Similar look",
                "engine": "dinov2-vits14",
                "modality": "region",
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
        bridge.setRegion(0.1, 0.1, 0.4, 0.4)
        bridge.findSimilar()
        assert bridge.similarBasisLabel == "Similar look"
        assert bridge.similarCount == 1
        bridge.openDiscoveryHit("m2")
        assert bridge.focusId == "m2"
        assert bridge.similarCount == 1
        assert bridge.similarId(0) == "m2"
        assert bridge.similarBasisLabel == "Similar look"
        assert bridge.scopeKind != "day"
        assert bridge.canBackDiscovery is True
        bridge.backToDiscovery()
        assert bridge.focusId == "m1"
        assert bridge.similarBasisLabel == "Similar look"
        assert bridge.similarCount == 1
    finally:
        shutdown_shell(engine)


def test_letterbox_keeps_full_crop():
    from semblon.region_encoder import INPUT_SIZE, letterbox_bgr

    image = np.zeros((20, 80, 3), dtype=np.uint8)
    image[:, :] = (0, 0, 255)
    canvas = letterbox_bgr(image)
    assert canvas.shape == (INPUT_SIZE, INPUT_SIZE, 3)
    # The red strip is inside the canvas, not cropped away.
    assert int(canvas[:, :, 2].max()) > 200
