"""P3 — single-buffer digest/decode and source-changed retry."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
import pytest

from semblon.source_integrity import (
    SOURCE_CHANGED_MESSAGE,
    SOURCE_CHANGED_OUTCOME,
    SourceChanged,
    decode_bgr_buffer,
    load_source_bgr,
    read_source_buffer,
)
from semblon.ingest import _decode_bgr
from semblon.category_backfill import decode_image
from semblon.store import connect, init_db


def _write_png(path: Path, color=(0, 128, 255)) -> bytes:
    img = np.zeros((16, 16, 3), dtype=np.uint8)
    img[:, :] = color
    ok, buf = cv2.imencode(".png", img)
    assert ok
    data = buf.tobytes()
    path.write_bytes(data)
    return data


def test_read_and_decode_use_same_buffer(tmp_path):
    path = tmp_path / "a.png"
    data = _write_png(path)
    buf = read_source_buffer(path)
    assert buf.digest == hashlib.sha256(data).hexdigest()
    assert buf.data == data
    img = decode_bgr_buffer(buf.data)
    assert img is not None
    assert img.shape[0] == 16


def test_decode_bgr_never_falls_back_to_imread(tmp_path):
    path = tmp_path / "bad.bin"
    path.write_bytes(b"not-an-image")
    with patch("semblon.source_integrity.cv2.imread") as imread:
        with patch("semblon.ingest.cv2.imread") as imread2:
            assert _decode_bgr(b"not-an-image", path) is None
            assert _decode_bgr(None, path) is None
            imread.assert_not_called()
            imread2.assert_not_called()


def test_load_source_bgr_detects_changed_bytes(tmp_path):
    path = tmp_path / "a.png"
    data = _write_png(path, (1, 2, 3))
    digest = hashlib.sha256(data).hexdigest()
    img, buf = load_source_bgr(path, expected_sha256=digest)
    assert img is not None
    assert buf.digest == digest
    path.write_bytes(_write_png(tmp_path / "b.png", (9, 9, 9)))
    # overwrite a.png with different pixels
    _write_png(path, (200, 10, 10))
    with pytest.raises(SourceChanged, match="will retry"):
        load_source_bgr(path, expected_sha256=digest)


def test_decode_image_reports_source_changed_token(tmp_path):
    path = tmp_path / "a.png"
    data = _write_png(path)
    digest = hashlib.sha256(data).hexdigest()
    assert decode_image(path, expected_sha256=digest) is not None
    _write_png(path, (40, 40, 40))
    assert decode_image(path, expected_sha256=digest) == "source_changed"


def test_category_backfill_records_source_changed(tmp_path, monkeypatch):
    from semblon import category_backfill as backfill
    from semblon.category_backfill import (
        CATEGORY_PEOPLE,
        STATE_FAILED,
        ProviderProbe,
        run_category_backfill,
    )

    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    path = folder / "a.png"
    data = _write_png(path)
    digest = hashlib.sha256(data).hexdigest()
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r1','t','1','pack',2,'l2','{}','{}','x64','native')"""
    )
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(path), digest, 16, 16, 1, len(data)),
    )
    conn.commit()
    conn.close()

    # Change file after library digest was recorded.
    _write_png(path, (7, 7, 7))

    monkeypatch.setattr(
        backfill,
        "probe_category",
        lambda category: ProviderProbe(True, "yunet_sface", "v1", ""),
    )
    monkeypatch.setattr(backfill, "people_detect", lambda img: [])
    run_category_backfill(store, CATEGORY_PEOPLE)
    conn = connect(store)
    try:
        row = conn.execute(
            "SELECT state, outcome, last_error FROM category_coverage WHERE media_id='m1'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == STATE_FAILED
    assert row[1] == SOURCE_CHANGED_OUTCOME
    assert row[2] == SOURCE_CHANGED_MESSAGE


def test_ui_copy_prefers_source_changed_message():
    from semblon.progress import KIND_PROGRESS, STAGE_INGEST, make_event
    from semblon.ui_copy import headline

    ev = make_event(
        STAGE_INGEST,
        KIND_PROGRESS,
        outcome=SOURCE_CHANGED_OUTCOME,
        message=SOURCE_CHANGED_MESSAGE,
        current=1,
        total=2,
    )
    # In-progress headlines append an ellipsis by design.
    assert headline(ev).startswith(SOURCE_CHANGED_MESSAGE)
