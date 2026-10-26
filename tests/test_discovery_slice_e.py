"""Slice E — OCR → Field + NanoDet BYO object search (not identity)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.native_shell.adapter import ArchiveAdapter
from semblon.object_pack import WEIGHT_NAME, probe_nanodet_status
from semblon.observers import NANODET_PROVIDER, OBJECT_PROVIDER, observe_bgr
from semblon.search import SearchError, search_object, search_text
from semblon.store import connect, init_db
from tests.test_cluster import _seed


def test_search_text_returns_media_ids_and_basis(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    img = np.ones((12, 12, 3), dtype=np.uint8)
    with patch("semblon.observers.ocr_image", return_value={"text": "HELLO SEMBLON", "score": 1.0}):
        observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("text",))
    conn.commit()
    conn.close()
    rec = search_text(store, "semblon")
    assert rec["status"] == "SUCCESS"
    assert rec["media_ids"] == ["m1"]
    assert rec["items"][0]["media_id"] == "m1"
    assert "Text in photos" in rec["similarity_basis"]
    assert "not a person" in rec["note"].lower()


def test_adapter_text_search_exposes_media_ids(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    with patch("semblon.observers.ocr_image", return_value={"text": "gate A", "score": 1.0}):
        observe_bgr(
            conn,
            observation_id="o1",
            run_id="r1",
            img=np.zeros((8, 8, 3), dtype=np.uint8),
            observers=("text",),
        )
    conn.commit()
    conn.close()

    class _App:
        def __init__(self, path: Path) -> None:
            self.store = path

        def archive_count(self) -> int:
            return 1

    result = ArchiveAdapter(_App(store)).search("text", "gate")
    assert result.state == "ready"
    assert result.data["media_ids"] == ["m1"]
    assert "not a person" in result.data["note"].lower()


def test_nanodet_probe_missing_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMBLON_OBJECT_PACK", str(tmp_path / "empty-pack"))
    ok, note = probe_nanodet_status()
    assert ok is False
    assert note is not None
    assert "missing" in note.lower() or "NanoDet" in note


def test_nanodet_probe_rejects_lfs_pointer(tmp_path, monkeypatch):
    root = tmp_path / "nanodet"
    root.mkdir()
    (root / WEIGHT_NAME).write_text("version https://git-lfs.github.com/spec/v1\n", encoding="utf-8")
    monkeypatch.setenv("SEMBLON_OBJECT_PACK", str(root))
    ok, note = probe_nanodet_status()
    assert ok is False
    assert note is not None
    assert "lfs" in note.lower() or "truncated" in note.lower()


def test_nanodet_probe_requires_pin_and_known_hash(tmp_path, monkeypatch):
    import hashlib

    from semblon import object_pack

    root = tmp_path / "nanodet"
    root.mkdir()
    blob = b"1" * 4096
    digest = hashlib.sha256(blob).hexdigest()
    (root / WEIGHT_NAME).write_bytes(blob)
    monkeypatch.setenv("SEMBLON_OBJECT_PACK", str(root))
    monkeypatch.setitem(object_pack.KNOWN_SHA256, WEIGHT_NAME, digest)
    ok, note = probe_nanodet_status()
    assert ok is False
    assert note is not None
    assert "pin" in note.lower()
    (root / "semblon-object-pack-pin.json").write_text(
        json.dumps({"sha256": digest}), encoding="utf-8"
    )
    ok2, note2 = probe_nanodet_status()
    assert ok2 is True
    assert note2 is None


def test_search_object_unavailable_without_pack(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    monkeypatch.setenv("SEMBLON_OBJECT_PACK", str(tmp_path / "no-pack"))
    rec = search_object(store, "dog")
    assert rec["status"] == "UNAVAILABLE"
    assert rec["count"] == 0
    assert "NanoDet" in (rec.get("reason") or "") or "pack" in (rec.get("reason") or "").lower()
    with pytest.raises(SearchError):
        search_object(store, "  ")


def test_search_object_matches_nanodet_labels_not_contours(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    # Contour-style row must not match object search.
    conn.execute(
        """INSERT INTO observation_items
           (item_id, observation_id, run_id, kind, provider, score, payload_json,
            bbox_x1, bbox_y1, bbox_x2, bbox_y2)
           VALUES ('i-contour','o1','r1','object',?,?,?,0,0,1,1)""",
        (
            OBJECT_PROVIDER,
            0.9,
            json.dumps({"class": "region", "label": "region"}),
        ),
    )
    conn.execute(
        """INSERT INTO observation_items
           (item_id, observation_id, run_id, kind, provider, score, payload_json,
            bbox_x1, bbox_y1, bbox_x2, bbox_y2)
           VALUES ('i-dog','o1','r1','object',?,?,?,1,2,3,4)""",
        (
            NANODET_PROVIDER,
            0.8,
            json.dumps({"class": "dog", "label": "dog", "class_id": 16, "source": "nanodet"}),
        ),
    )
    conn.commit()
    conn.close()
    with patch("semblon.object_pack.probe_nanodet_status", return_value=(True, None)):
        hit = search_object(store, "dog")
        miss = search_object(store, "bicycle")
        scoped = search_object(store, "dog", within_media_ids=["m2"])
    assert hit["status"] == "SUCCESS"
    assert hit["media_ids"] == ["m1"]
    assert hit["items"][0]["label"] == "dog"
    assert "not a person" in hit["items"][0]["why"]
    assert miss["status"] == "NO_RESULT"
    assert scoped["status"] == "UNAVAILABLE" or scoped["count"] == 0


def test_search_text_respects_field_scope(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    img = np.ones((12, 12, 3), dtype=np.uint8)
    with patch("semblon.observers.ocr_image", return_value={"text": "HELLO SEMBLON", "score": 1.0}):
        observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("text",))
    with patch("semblon.observers.ocr_image", return_value={"text": "OTHER TEXT", "score": 1.0}):
        observe_bgr(conn, observation_id="o2", run_id="r1", img=img, observers=("text",))
    conn.commit()
    conn.close()
    all_hits = search_text(store, "semblon")
    assert all_hits["media_ids"] == ["m1"]
    scoped_miss = search_text(store, "semblon", within_media_ids=["m2"])
    assert scoped_miss["count"] == 0
    assert scoped_miss["status"] in {"NO_RESULT", "UNAVAILABLE"}
    assert "Field" in scoped_miss.get("similarity_basis", "") or scoped_miss["count"] == 0


def test_observe_keeps_contours_separate_from_nanodet(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    monkeypatch.setenv("SEMBLON_OBJECT_PACK", str(tmp_path / "missing"))
    conn = connect(store)
    init_db(conn)
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[10:40, 10:40] = 255
    observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("object",))
    conn.commit()
    rows = conn.execute(
        "SELECT provider, payload_json FROM observation_items WHERE kind='object'"
    ).fetchall()
    conn.close()
    providers = {r["provider"] for r in rows}
    assert OBJECT_PROVIDER in providers
    assert NANODET_PROVIDER not in providers
    for r in rows:
        payload = json.loads(r["payload_json"])
        assert payload.get("class") == "region"



def test_search_object_finds_saved_human_name_without_nanodet(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO observation_items
           (item_id, observation_id, run_id, kind, provider, score, payload_json,
            bbox_x1, bbox_y1, bbox_x2, bbox_y2)
           VALUES ('i-named-toolbox','o1','r1','object','user_box',1.0,?,0,0,1,1)""",
        (json.dumps({"class": "user_region", "named": "my red toolbox", "identity": "not facekit"}),),
    )
    conn.commit()
    conn.close()
    with patch("semblon.object_pack.probe_nanodet_status", return_value=(False, "NanoDet pack missing")):
        rec = search_object(store, "toolbox")
    assert rec["status"] == "SUCCESS"
    assert rec["media_ids"] == ["m1"]
    assert rec["items"][0]["label"] == "my red toolbox"
    assert rec["items"][0]["match_basis"] == "Saved human region name"
    assert "human-supplied" in rec["items"][0]["why"]
    assert "not a person" in rec["items"][0]["why"]


def test_search_object_does_not_promote_generic_user_region_names(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO observation_items
           (item_id, observation_id, run_id, kind, provider, score, payload_json,
            bbox_x1, bbox_y1, bbox_x2, bbox_y2)
           VALUES ('i-generic-region','o1','r1','object','user_box',1.0,?,0,0,1,1)""",
        (json.dumps({"class": "user_region", "named": "region"}),),
    )
    conn.commit()
    conn.close()
    with patch("semblon.object_pack.probe_nanodet_status", return_value=(False, "NanoDet pack missing")):
        rec = search_object(store, "region")
    assert rec["status"] == "UNAVAILABLE"
    assert rec["count"] == 0


def test_search_object_preserves_detector_label_search_when_ready(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO observation_items
           (item_id, observation_id, run_id, kind, provider, score, payload_json,
            bbox_x1, bbox_y1, bbox_x2, bbox_y2)
           VALUES ('i-dog','o1','r1','object',?,?,?,0,0,1,1)""",
        (NANODET_PROVIDER, 0.8, json.dumps({"class": "dog", "label": "dog", "class_id": 16})),
    )
    conn.commit()
    conn.close()
    with patch("semblon.object_pack.probe_nanodet_status", return_value=(True, None)):
        rec = search_object(store, "dog")
    assert rec["status"] == "SUCCESS"
    assert rec["items"][0]["label"] == "dog"
    assert rec["items"][0]["match_basis"] == "COCO object detection (NanoDet)"
