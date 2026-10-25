"""Tiered still ingest. Library rows survive a failed face pass. Restarts skip done tiers."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path
from unittest.mock import patch

import numpy as np

from semblon.ingest import ingest
from semblon.scan_tiers import (
    TIER_DETAIL,
    TIER_LIBRARY,
    TIER_OBSERVE,
    TIER_SEMANTIC,
    header_geometry,
)
from semblon.store import SCHEMA_VERSION, connect, init_db


def _face():
    return [
        {
            "bbox": (0.0, 0.0, 10.0, 10.0),
            "det_score": 0.9,
            "face_w": 100,
            "face_h": 100,
            "dim": 4,
            "embedding": np.zeros(4, dtype=np.float32),
        }
    ]


def _run(folder: Path, store: Path, embed, **kwargs):
    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest.embed_bgr", side_effect=embed),
        patch("semblon.ingest.cv2.imread", return_value=image),
        patch("semblon.ingest.cv2.imdecode", return_value=image),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        return ingest(folder, store, workers=1, **kwargs)


def _folder(tmp_path: Path) -> tuple[Path, Path]:
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"\xff\xd8\xfffake-a")
    return folder, tmp_path / "s.sqlite"


def test_schema_has_work_items(tmp_path):
    conn = connect(tmp_path / "s.sqlite")
    init_db(conn)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "work_items" in tables
    version = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]
    assert version == SCHEMA_VERSION == "5"
    conn.close()


def test_failed_face_keeps_the_library_row_and_retries_once(tmp_path):
    folder, store = _folder(tmp_path)
    calls = {"n": 0}

    def embed(_app, _img):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("embed failed")
        return _face()

    first = _run(folder, store, embed)
    assert first["failed"] == 1
    assert first["new_media"] == 1
    assert "decode_ms" in first and "face_ms" in first and "dino_ms" in first
    conn = sqlite3.connect(str(store))
    mask = conn.execute("SELECT tier_done_mask FROM work_items").fetchone()[0]
    media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    obs = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    conn.close()
    assert media == 1 and obs == 0
    assert mask == TIER_LIBRARY

    second = _run(folder, store, embed)
    assert second["ok"] >= 1
    assert second["new_media"] == 0
    assert calls["n"] == 2
    conn = sqlite3.connect(str(store))
    mask = conn.execute("SELECT tier_done_mask FROM work_items").fetchone()[0]
    faces = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
    conn.close()
    assert faces == 1
    assert mask & TIER_OBSERVE


def test_restart_does_not_reembed_or_rehash_a_finished_file(tmp_path):
    folder, store = _folder(tmp_path)
    calls = {"n": 0}

    def embed(_app, _img):
        calls["n"] += 1
        return _face()

    _run(folder, store, embed)
    conn = sqlite3.connect(str(store))
    conn.execute("DELETE FROM work_items")
    conn.commit()
    conn.close()
    second = _run(folder, store, embed)
    assert calls["n"] == 1
    assert second["skipped_seen"] == 1
    assert second["faces"] == 0


def test_region_waits_until_the_semantic_tier(tmp_path):
    folder, store = _folder(tmp_path)
    calls = {"embed": 0, "region": 0}

    def embed(_app, _img):
        calls["embed"] += 1
        return _face()

    def index(_conn, **kwargs):
        calls["region"] += 1
        calls.setdefault("depths", []).append(kwargs.get("depth"))
        return {"region": 1, "scene": 1, "patch": 0, "ready": True, "jobs": 2}

    with (
        patch("semblon.region_encoder.probe_region_pack", return_value=(True, "")),
        patch("semblon.region_encoder.index_image_regions", side_effect=index),
    ):
        _run(folder, store, embed, observers="face")
        assert calls["region"] == 0
        _run(folder, store, embed, observers="face,region")
    assert calls["embed"] == 1
    assert calls["depths"] == ["frame", "detail"]
    conn = sqlite3.connect(str(store))
    mask = conn.execute("SELECT tier_done_mask FROM work_items").fetchone()[0]
    conn.close()
    assert mask & TIER_SEMANTIC and mask & TIER_DETAIL
    with (
        patch("semblon.region_encoder.probe_region_pack", return_value=(True, "")),
        patch("semblon.region_encoder.index_image_regions", side_effect=index),
    ):
        third = _run(folder, store, embed, observers="face,region")
    assert third["skipped_seen"] == 1
    assert calls["embed"] == 1
    assert calls["region"] == 2


def _mask(store: Path) -> int:
    conn = sqlite3.connect(str(store))
    try:
        return int(conn.execute("SELECT tier_done_mask FROM work_items").fetchone()[0])
    finally:
        conn.close()


def test_lite_pass_makes_the_photo_searchable_and_detail_resumes_later(tmp_path):
    folder, store = _folder(tmp_path)
    depths: list[str] = []

    def index(_conn, **kwargs):
        depths.append(kwargs["depth"])
        return {"region": 0, "scene": 1, "patch": 4, "ready": True, "jobs": 1}

    with (
        patch("semblon.region_encoder.probe_region_pack", return_value=(True, "")),
        patch("semblon.region_encoder.index_image_regions", side_effect=index),
    ):
        _run(folder, store, lambda *_a: _face(), observers="face,region-lite")
        assert depths == ["frame"]
        assert _mask(store) & TIER_SEMANTIC
        assert not _mask(store) & TIER_DETAIL
        _run(folder, store, lambda *_a: _face(), observers="face,region")
    assert depths == ["frame", "detail"]
    assert _mask(store) & TIER_DETAIL


def test_a_failed_encode_leaves_the_semantic_bit_open(tmp_path):
    folder, store = _folder(tmp_path)

    def index(_conn, **_kwargs):
        return {"region": 0, "scene": 0, "patch": 0, "ready": True, "jobs": 1, "note": "region encoder timed out"}

    with (
        patch("semblon.region_encoder.probe_region_pack", return_value=(True, "")),
        patch("semblon.region_encoder.index_image_regions", side_effect=index),
    ):
        _run(folder, store, lambda *_a: _face(), observers="face,region")
    assert not _mask(store) & TIER_SEMANTIC
    assert not _mask(store) & TIER_DETAIL


def test_library_tier_commits_a_file_before_reading_the_next(tmp_path):
    """A folder must not sit in RAM until every still has been hashed."""
    folder = tmp_path / "photos"
    folder.mkdir()
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        (folder / name).write_bytes(b"\xff\xd8\xff" + name.encode())
    store = tmp_path / "s.sqlite"
    order: list[tuple[str, str]] = []
    import semblon.ingest as ingest_mod

    real_read = ingest_mod._read_and_hash
    real_save = ingest_mod.save_work_item

    def read(path: Path):
        order.append(("read", Path(path).name))
        return real_read(path)

    def save(conn, **kwargs):
        order.append(("save", Path(kwargs["path"]).name))
        return real_save(conn, **kwargs)

    with (
        patch.object(ingest_mod, "_read_and_hash", side_effect=read),
        patch.object(ingest_mod, "save_work_item", side_effect=save),
    ):
        _run(folder, store, lambda *_args: _face())

    waiting = None
    for kind, name in order:
        if kind == "read":
            assert waiting is None, order
            waiting = name
        elif kind == "save" and name == waiting:
            waiting = None
    assert waiting is None
    assert [name for kind, name in order if kind == "read"] == ["a.jpg", "b.jpg", "c.jpg"]


def test_header_orientation_and_embedded_thumb():
    thumb = b"\xff\xd8\xff\xd9"
    tiff = bytearray(56 + len(thumb))
    tiff[0:2] = b"II"
    tiff[2:4] = struct.pack("<H", 42)
    tiff[4:8] = struct.pack("<I", 8)
    tiff[8:10] = struct.pack("<H", 1)
    struct.pack_into("<HHI", tiff, 10, 0x0112, 3, 1)
    struct.pack_into("<H", tiff, 18, 6)
    struct.pack_into("<I", tiff, 22, 26)
    tiff[26:28] = struct.pack("<H", 2)
    struct.pack_into("<HHI", tiff, 28, 0x0201, 4, 1)
    struct.pack_into("<I", tiff, 36, 56)
    struct.pack_into("<HHI", tiff, 40, 0x0202, 4, 1)
    struct.pack_into("<I", tiff, 48, len(thumb))
    struct.pack_into("<I", tiff, 52, 0)
    tiff[56:] = thumb
    payload = b"Exif\x00\x00" + bytes(tiff)
    sof = b"\xff\xc0" + struct.pack(">H", 11) + bytes([8, 0, 10, 0, 20, 1, 0x11, 0, 0])
    blob = b"\xff\xd8\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload + sof
    width, height, orientation, found = header_geometry(blob)
    assert orientation == 6
    assert (width, height) == (10, 20)
    assert found == thumb
