"""Optional observers. Extra modalities must not become people."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from semblon.canvas import overlay_boxes
from semblon.cluster import cluster_run
from semblon.home_ui import format_people_lines, format_search_lines, format_unknown_lines
from semblon.identify import identify_face
from semblon.observers import (
    CLIP_PACK,
    find_local_clip_weights,
    observe_bgr,
    optional_status,
    probe_clip_status,
    probe_ocr_status,
    probe_pose_status,
)
from semblon.review import name_cluster
from semblon.search import SearchError, search_similar
from semblon.store import connect, init_db
from tests.test_cluster import _seed, _vec
from tests.test_review import _clustered


def test_optional_status_pose_false_without_solutions():
    fake_mp = types.ModuleType("mediapipe")
    with patch.dict(sys.modules, {"mediapipe": fake_mp}):
        ok, note = probe_pose_status()
    assert ok is False
    assert note is not None
    assert "solutions" in note
    with patch("semblon.observers.probe_ocr_status", return_value=(False, "unavailable: mocked")):
        with patch("semblon.observers.probe_clip_status", return_value=(False, "unavailable: mocked")):
            with patch("semblon.observers.probe_pose_status", return_value=(False, "unavailable: mediapipe.solutions.pose missing")):
                st = optional_status()
    assert st["pose"] is False
    assert "solutions" in st["notes"]["pose"]
    assert st["identity"] == "facekit only"


def test_optional_status_ocr_false_without_tesseract_binary():
    with patch("semblon.observers.shutil.which", return_value=None):
        ok, note = probe_ocr_status()
    assert ok is False
    assert note is not None
    assert "tesseract" in note.lower()
    assert "PATH" in note


def test_optional_status_clip_false_without_weights(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENCLIP_CACHE_DIR", str(tmp_path / "clip-cache"))
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hf-hub"))
    fake_oc = types.ModuleType("open_clip")
    fake_pretrained = types.ModuleType("open_clip.pretrained")

    def _cfg(model, tag):
        assert model == "ViT-B-32"
        return {
            "url": "https://example.test/models/deadbeef/ViT-B-32.pt",
            "hf_hub": "timm/vit_base_patch32_clip_224.openai/",
        }

    fake_pretrained.get_pretrained_cfg = _cfg
    fake_oc.pretrained = fake_pretrained
    fake_torch = types.ModuleType("torch")
    with patch.dict(
        sys.modules,
        {"open_clip": fake_oc, "open_clip.pretrained": fake_pretrained, "torch": fake_torch},
    ):
        assert find_local_clip_weights() is None
        ok, note = probe_clip_status()
    assert ok is False
    assert note is not None
    assert "weights missing" in note
    assert "no download" in note


def test_optional_status_clip_true_when_url_cache_present(tmp_path, monkeypatch):
    cache = tmp_path / "clip-cache"
    cache.mkdir()
    weights = cache / "ViT-B-32.pt"
    weights.write_bytes(b"fake-weights")
    monkeypatch.setenv("OPENCLIP_CACHE_DIR", str(cache))
    fake_oc = types.ModuleType("open_clip")
    fake_pretrained = types.ModuleType("open_clip.pretrained")
    fake_pretrained.get_pretrained_cfg = MagicMock(
        return_value={"url": "https://example.test/deadbeef/ViT-B-32.pt", "hf_hub": "timm/x/"}
    )
    fake_oc.pretrained = fake_pretrained
    fake_torch = types.ModuleType("torch")
    with patch.dict(
        sys.modules,
        {"open_clip": fake_oc, "open_clip.pretrained": fake_pretrained, "torch": fake_torch},
    ):
        found = find_local_clip_weights()
        ok, note = probe_clip_status()
    assert found == weights
    assert ok is True
    assert note is None


def test_optional_status_mock_missing_apis_report_unavailable():
    with patch("semblon.observers.probe_ocr_status", return_value=(False, "unavailable: tesseract binary not on PATH")):
        with patch(
            "semblon.observers.probe_clip_status",
            return_value=(False, "unavailable: open_clip+torch present but ViT-B-32/openai weights missing (no download)"),
        ):
            with patch(
                "semblon.observers.probe_pose_status",
                return_value=(False, "unavailable: mediapipe.solutions.pose missing"),
            ):
                st = optional_status()
    assert st["ocr"] is False
    assert st["clip"] is False
    assert st["pose"] is False
    assert "tesseract" in st["notes"]["ocr"]
    assert "weights" in st["notes"]["clip"]
    assert "solutions" in st["notes"]["pose"]


def test_ocr_unavailable_is_a_stub_not_a_person(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    img = np.zeros((16, 16, 3), dtype=np.uint8)
    with patch("semblon.observers.ocr_image", return_value=None):
        observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("text",))
    conn.commit()
    row = conn.execute("SELECT kind, payload_json FROM observation_items WHERE kind='text'").fetchone()
    persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    conn.close()
    assert row is not None
    assert "unavailable" in row["payload_json"]
    assert persons == 0


def test_ocr_text_does_not_identify(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    conn = connect(store)
    init_db(conn)
    oid = conn.execute("SELECT observation_id FROM observations LIMIT 1").fetchone()[0]
    rid = conn.execute("SELECT run_id FROM observations LIMIT 1").fetchone()[0]
    img = np.ones((12, 12, 3), dtype=np.uint8)
    with patch("semblon.observers.ocr_image", return_value={"text": "HELLO", "score": 1.0}):
        observe_bgr(conn, observation_id=oid, run_id=rid, img=img, observers=("text",))
    conn.commit()
    n_text = conn.execute("SELECT COUNT(*) FROM observation_items WHERE kind='text'").fetchone()[0]
    n_face_emb = conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
    conn.close()
    assert n_text == 1
    assert n_face_emb == 0
    rec = identify_face(store, "r1", "f2")
    assert rec["decision"] in {"ACCEPT", "UNKNOWN"}


def test_clip_embedding_is_not_face_identity(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    blob = _vec(1.0, 0.0, 0.0, 0.0)
    fake = {"embedding": blob, "pack_id": CLIP_PACK, "dim": 4}
    with patch("semblon.observers.clip_embed", return_value=fake):
        observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("clip",))
    conn.commit()
    item = conn.execute("SELECT item_id FROM observation_items WHERE kind='clip'").fetchone()[0]
    modality = conn.execute("SELECT modality FROM embeddings WHERE item_id=?", (item,)).fetchone()[0]
    n_face = conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
    conn.close()
    assert modality == "clip"
    assert n_face == 0
    sim = search_similar(store, item)
    assert sim["modality"] == "clip"
    with pytest.raises(SearchError):
        search_similar(store, "f1")
    rec = cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = connect(store)
    persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    conn.close()
    assert rec["clusters"] >= 1
    assert persons == 0


def test_pose_landmarks_are_not_people(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    fake = {"landmarks": [{"i": 0, "x": 0.1, "y": 0.2, "z": 0.0, "v": 1.0}], "score": 1.0, "bbox": (1, 2, 8, 9)}
    with patch("semblon.observers.pose_landmarks", return_value=fake):
        observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("pose",))
    conn.commit()
    kind, payload = conn.execute("SELECT kind, payload_json FROM observation_items WHERE kind='pose'").fetchone()
    persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    conn.close()
    assert kind == "pose"
    assert "landmarks" in payload
    assert persons == 0


def test_overlay_boxes_skip_dual_write_faces():
    board = {
        "faces": [
            {
                "media_id": "m1",
                "face_id": "f1",
                "bbox_x1": 0,
                "bbox_y1": 0,
                "bbox_x2": 10,
                "bbox_y2": 10,
                "cluster_id": "c1",
                "person_id": None,
            }
        ],
        "items": [
            {
                "media_id": "m1",
                "kind": "face",
                "item_id": "i-face",
                "bbox_x1": 0,
                "bbox_y1": 0,
                "bbox_x2": 10,
                "bbox_y2": 10,
                "provider": "facekit",
            },
            {
                "media_id": "m1",
                "kind": "object",
                "item_id": "i-obj",
                "bbox_x1": 2,
                "bbox_y1": 2,
                "bbox_x2": 6,
                "bbox_y2": 6,
                "provider": "opencv-contour",
            },
        ],
    }
    boxes = overlay_boxes(board, "m1")
    kinds = [b["kind"] for b in boxes]
    assert kinds.count("face") == 1
    assert "object" in kinds


def test_home_list_formatters():
    people = format_people_lines({"items": [{"display_name": "Alice", "faces": 3}]})
    assert "Alice" in people[0]
    empty = format_people_lines({"items": []})
    assert "No named people" in empty[0]
    unk = format_unknown_lines({"counts": {"KNOWN": 1, "UNKNOWN": 4}}, "r1")
    assert "UNKNOWN=4" in unk[1]
    sim = format_search_lines(
        {
            "kind": "similar",
            "query": "abc",
            "modality": "appearance",
            "pack_id": "appearance/rgb8@1",
            "count": 1,
            "items": [{"score": 0.9, "kind": "appearance", "item_id": "x", "why": "same modality+pack only; not a person"}],
            "note": "Similarity is not identity.",
        }
    )
    assert "appearance" in sim[0]
    assert "not a person" in sim[2]
