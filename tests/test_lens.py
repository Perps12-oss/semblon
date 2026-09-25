"""Lens query: missing providers are not empty matches. Identity is untouched."""

from __future__ import annotations

import numpy as np
import pytest

from semblon.lens import (
    persist_successes,
    query_image,
    query_screen,
    validate_vlm_payload,
)
from semblon.runtime_contract import failure_disguised_as_empty
from semblon.store import connect, init_db


def _qr() -> np.ndarray:
    import cv2

    raw = cv2.QRCodeEncoder_create().encode("SEMBLON-QR")
    big = cv2.resize(raw, (250, 250), interpolation=cv2.INTER_NEAREST)
    return cv2.cvtColor(big, cv2.COLOR_GRAY2BGR)


def _by_id(report, capability_id: str):
    rows = [row for row in report.results if row.capability_id == capability_id]
    assert len(rows) == 1
    return rows[0]


def _assert_honest(report):
    for row in report.results:
        assert failure_disguised_as_empty(row) is False
        if row.status == "SUCCESS":
            assert row.items


def _clear_model_env(monkeypatch):
    for key in (
        "SEMBLON_SIGLIP_ONNX",
        "SEMBLON_SIGLIP_SHA256",
        "SEMBLON_SAM2_CHECKPOINT",
        "SEMBLON_SAM2_SHA256",
        "SEMBLON_TRANSLATION_MODEL",
        "SEMBLON_VLM_MODEL",
        "SEMBLON_VLM",
    ):
        monkeypatch.delenv(key, raising=False)


def test_qr_is_a_hit_and_missing_models_do_not_match(monkeypatch):
    _clear_model_env(monkeypatch)
    report = query_image(_qr())
    _assert_honest(report)
    barcode = _by_id(report, "barcode")
    assert barcode.status == "SUCCESS"
    assert barcode.items[0].label == "SEMBLON-QR"
    assert barcode.items[0].detail == "qr"
    embed = _by_id(report, "visual_embedding")
    assert embed.status == "UNAVAILABLE"
    assert embed.status != "NO_RESULT"
    translated = _by_id(report, "translation")
    assert translated.status == "UNAVAILABLE"
    described = _by_id(report, "vlm")
    assert described.status == "UNAVAILABLE"
    grounded = _by_id(report, "grounding")
    assert grounded.status == "SUCCESS"
    assert grounded.provider_state == "DEGRADED"
    assert grounded.fallback == "RECTANGULAR_CROP"
    assert grounded.items[0].mask is None


def test_blank_barcode_ran_and_found_nothing(monkeypatch):
    _clear_model_env(monkeypatch)
    blank = np.zeros((80, 80, 3), dtype=np.uint8)
    report = query_image(blank, capabilities=("barcode",))
    row = _by_id(report, "barcode")
    assert row.status == "NO_RESULT"
    assert row.provider_state == "READY"
    assert row.items == ()


def test_selection_outside_the_frame_does_not_search(monkeypatch):
    _clear_model_env(monkeypatch)
    image = _qr()
    report = query_image(image, x=10_000, y=10_000, w=20, h=20, capabilities=("barcode", "ocr"))
    _assert_honest(report)
    assert report.region["translated"] is True
    for row in report.results:
        assert row.status == "UNAVAILABLE"
        assert row.error_id.endswith(".NO_REGION")
        assert row.status != "NO_RESULT"


def test_signed_selection_is_clipped_at_the_frame(monkeypatch):
    _clear_model_env(monkeypatch)
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    report = query_image(image, x=-4, y=-3, w=8, h=7, capabilities=("barcode",))
    assert report.region["translated"] is True
    assert report.results[0].status == "NO_RESULT"


def test_screen_capture_off_windows_does_not_search(monkeypatch):
    _clear_model_env(monkeypatch)
    monkeypatch.setattr("semblon.lens.sys.platform", "linux")
    report = query_screen(0, 0, 40, 40, capabilities=("barcode", "visual_embedding"))
    _assert_honest(report)
    capture = _by_id(report, "screen_capture")
    assert capture.status == "UNAVAILABLE"
    assert capture.model_state == "UNSUPPORTED_RUNTIME"
    barcode = _by_id(report, "barcode")
    assert barcode.status == "UNAVAILABLE"
    assert barcode.error_id == "barcode.NO_CAPTURE"
    assert barcode.status != "NO_RESULT"


def test_empty_screen_region_is_not_a_full_desktop_grab(monkeypatch):
    monkeypatch.setattr("semblon.lens.sys.platform", "win32")
    report = query_screen(0, 0, 0, 10, capabilities=("barcode",))
    capture = _by_id(report, "screen_capture")
    assert capture.status == "UNAVAILABLE"
    assert capture.error_id == "screen_capture.NO_REGION"
    assert _by_id(report, "barcode").error_id == "barcode.NO_CAPTURE"


def test_invalid_vlm_output_is_rejected(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    model = tmp_path / "vlm.bin"
    model.write_bytes(b"not-a-real-model")
    monkeypatch.setenv("SEMBLON_VLM_MODEL", str(model))
    report = query_image(
        np.zeros((8, 8, 3), dtype=np.uint8),
        capabilities=("vlm",),
        vlm_generate=lambda: {"summary": "", "concepts": []},
    )
    row = _by_id(report, "vlm")
    assert row.status == "ERROR"
    assert row.status != "NO_RESULT"
    assert row.items == ()
    assert validate_vlm_payload({"summary": "a box", "concepts": ["box"]}) is None
    assert validate_vlm_payload({"summary": "a box", "concepts": ["box"], "person": "Mara"})


def test_valid_vlm_is_a_description_not_a_name(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    model = tmp_path / "vlm.bin"
    model.write_bytes(b"local")
    monkeypatch.setenv("SEMBLON_VLM_MODEL", str(model))
    report = query_image(
        np.zeros((8, 8, 3), dtype=np.uint8),
        capabilities=("vlm",),
        vlm_generate=lambda: {"summary": "a cardboard box", "concepts": ["box"]},
    )
    row = _by_id(report, "vlm")
    assert row.status == "SUCCESS"
    assert row.items[0].label == "a cardboard box"


def test_corrupt_siglip_file_is_not_an_empty_embedding(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    model = tmp_path / "siglip.onnx"
    model.write_bytes(b"corrupt")
    monkeypatch.setenv("SEMBLON_SIGLIP_ONNX", str(model))
    report = query_image(np.zeros((8, 8, 3), dtype=np.uint8), capabilities=("visual_embedding",))
    row = _by_id(report, "visual_embedding")
    assert row.status == "ERROR"
    assert row.provider_state == "FAILED"
    assert row.items == ()


def test_hits_persist_without_becoming_people(monkeypatch, tmp_path):
    _clear_model_env(monkeypatch)
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    report = query_image(_qr(), capabilities=("barcode", "grounding", "visual_embedding", "vlm"))
    counts = persist_successes(conn, observation_id="o1", run_id="r1", report=report)
    conn.commit()
    persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    faces = conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
    kinds = {
        row[0]
        for row in conn.execute("SELECT kind FROM observation_items").fetchall()
    }
    conn.close()
    assert counts["object"] >= 1
    assert persons == 0
    assert faces == 0
    assert "face" not in kinds


def test_checksum_mismatch_is_corrupt(monkeypatch, tmp_path):
    from semblon.lens import model_state_for_path

    file = tmp_path / "m.bin"
    file.write_bytes(b"abc")
    assert model_state_for_path(file, expected_sha256="0" * 64) == "CORRUPT"
    assert model_state_for_path(None) == "MISSING"
    assert model_state_for_path(file) == "AVAILABLE"
