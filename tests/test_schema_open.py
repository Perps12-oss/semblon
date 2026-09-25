"""The previously open schema list. Failures stay visible. Identity stays untouched."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from semblon.ann_index import build_index
from semblon.circuits import reset_circuits
from semblon.lens import describe_pixels, query_image, query_screen
from semblon.model_install import InstallError, install_model
from semblon.privacy import WindowRect
from semblon.runtime_contract import failure_disguised_as_empty
from semblon.search import search_similar
from semblon.selection import format_query_lines, widget_drag_to_image
from semblon.store import connect, init_db


@pytest.fixture(autouse=True)
def _clean_circuits():
    reset_circuits()
    yield
    reset_circuits()


def _seed(path: Path):
    conn = connect(path)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',100,100,0,1)")
    conn.execute("INSERT INTO media VALUES ('m2','folder','/b.jpg','bbb',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',NULL,NULL,'r1')")
    return conn


def _clear(monkeypatch):
    for key in (
        "SEMBLON_SIGLIP_ONNX",
        "SEMBLON_SAM2_CHECKPOINT",
        "SEMBLON_SAM2_CONFIG",
        "SEMBLON_TRANSLATION_MODEL",
        "SEMBLON_VLM_MODEL",
        "SEMBLON_VLM",
        "SEMBLON_LKG_PACK",
    ):
        monkeypatch.delenv(key, raising=False)
    reset_circuits()


def _row(report, capability):
    found = [row for row in report.results if row.capability_id == capability]
    assert len(found) == 1
    assert failure_disguised_as_empty(found[0]) is False
    return found[0]


def test_drag_maps_into_image_pixels_and_lines_do_not_hide_failure():
    rect = widget_drag_to_image(0, 0, 50, 25, view_w=100, view_h=50, image_w=200, image_h=100)
    assert rect == {"x": 0, "y": 0, "w": 100, "h": 50}
    assert widget_drag_to_image(5, 5, 5, 9, view_w=10, view_h=10, image_w=10, image_h=10) is None
    image = np.zeros((20, 20, 3), dtype=np.uint8)
    report = query_image(image, x=0, y=0, w=10, h=10, capabilities=("barcode",))
    lines = format_query_lines(report)
    assert any("ran, nothing matched" in line or "did not run" in line or "Nothing" in line for line in lines)
    assert "No matches nearby." not in "\n".join(lines)


def test_privacy_filter_refuses_the_semblon_window(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setattr("semblon.lens.sys.platform", "win32")
    report = query_screen(
        10,
        10,
        20,
        20,
        capabilities=("barcode",),
        blocked=(WindowRect("Semblon", 0, 0, 100, 100),),
    )
    capture = _row(report, "screen_capture")
    assert capture.status == "UNAVAILABLE"
    assert capture.error_id == "screen_capture.PRIVACY"
    assert _row(report, "barcode").error_id == "barcode.NO_CAPTURE"


def test_atomic_install_rejects_a_bad_checksum_and_keeps_the_old_file(tmp_path):
    source = tmp_path / "new.bin"
    source.write_bytes(b"new-model")
    dest = tmp_path / "models" / "siglip.onnx"
    dest.parent.mkdir()
    dest.write_bytes(b"previous")
    with pytest.raises(InstallError):
        install_model(source, dest, expected_sha256="0" * 64)
    assert dest.read_bytes() == b"previous"
    assert not dest.with_name(dest.name + ".partial").exists()
    published = install_model(source, dest)
    assert Path(published["path"]).read_bytes() == b"new-model"
    assert published["state"] == "AVAILABLE"


def test_siglip_onnx_session_runs(monkeypatch, tmp_path):
    _clear(monkeypatch)
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper

    node = helper.make_node("ReduceMean", ["input"], ["output"], axes=[2, 3], keepdims=0)
    graph = helper.make_graph(
        [node],
        "tiny",
        [helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 3, 8, 8])],
        [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 3])],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    path = tmp_path / "tiny.onnx"
    onnx.save(model, path)
    monkeypatch.setenv("SEMBLON_SIGLIP_ONNX", str(path))
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    report = query_image(image, capabilities=("visual_embedding",))
    row = _row(report, "visual_embedding")
    assert row.status == "SUCCESS"
    assert row.items[0].label == "siglip"
    assert report.embeddings["visual_embedding"]


def test_sam2_mask_is_recorded_when_the_predictor_returns_one(monkeypatch, tmp_path):
    _clear(monkeypatch)
    checkpoint = tmp_path / "sam2.pt"
    checkpoint.write_bytes(b"checkpoint")
    monkeypatch.setenv("SEMBLON_SAM2_CHECKPOINT", str(checkpoint))

    def fake(_image, _checkpoint):
        return np.ones((6, 6), dtype=bool)

    monkeypatch.setattr("semblon.lens._sam2_predict", fake)
    report = query_image(np.zeros((6, 6, 3), dtype=np.uint8), capabilities=("grounding",))
    row = _row(report, "grounding")
    assert row.status == "SUCCESS"
    assert row.items[0].method == "SAM2"
    assert row.items[0].mask
    assert "RECTANGULAR" not in (row.items[0].mask or "")


def test_dictionary_translation_runs(monkeypatch, tmp_path):
    _clear(monkeypatch)
    model = tmp_path / "en-de.json"
    model.write_text(json.dumps({"from": "en", "to": "de", "map": {"box": "Karton"}}), encoding="utf-8")
    monkeypatch.setenv("SEMBLON_TRANSLATION_MODEL", str(model))
    report = query_image(
        np.zeros((8, 8, 3), dtype=np.uint8),
        capabilities=("translation",),
    )
    # No OCR in this request, so translation receives no source and does not invent one.
    assert _row(report, "translation").status == "UNAVAILABLE"
    from semblon.lens import translate_text

    hit = translate_text("box")
    assert hit.status == "SUCCESS"
    assert hit.items[0].label == "Karton"
    miss = translate_text("zzzz")
    assert miss.status == "NO_RESULT"


def test_pixel_describer_is_a_real_structured_description(monkeypatch, tmp_path):
    _clear(monkeypatch)
    marker = tmp_path / "vlm.txt"
    marker.write_text("pixel-describer\n", encoding="utf-8")
    monkeypatch.setenv("SEMBLON_VLM_MODEL", str(marker))
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[:, :] = (0, 0, 255)
    report = query_image(image, capabilities=("vlm",))
    row = _row(report, "vlm")
    assert row.status == "SUCCESS"
    assert row.items[0].detail == "pixel-describer"
    assert row.items[0].label == describe_pixels(image)["summary"]
    assert "person" not in row.items[0].label.lower()


def test_pack_matches_a_barcode_and_a_missing_pack_does_not(monkeypatch, tmp_path):
    _clear(monkeypatch)
    import cv2

    raw = cv2.QRCodeEncoder_create().encode("SEMBLON-QR")
    big = cv2.resize(raw, (250, 250), interpolation=cv2.INTER_NEAREST)
    image = cv2.cvtColor(big, cv2.COLOR_GRAY2BGR)
    bare = query_image(image, capabilities=("product",))
    assert _row(bare, "product").status == "UNAVAILABLE"
    pack = tmp_path / "pack.json"
    pack.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "id": "p1",
                        "kind": "product",
                        "label": "Sample carton",
                        "provenance": "local pack",
                        "match": {"barcode": "SEMBLON-QR"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SEMBLON_LKG_PACK", str(pack))
    found = query_image(image, capabilities=("product",))
    row = _row(found, "product")
    assert row.status == "SUCCESS"
    assert row.items[0].label == "Sample carton"


def test_derived_index_is_used_and_faces_stay_out(tmp_path):
    from semblon.observers import observe_bgr

    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("color",))
    img2 = np.full((8, 8, 3), 255, dtype=np.uint8)
    observe_bgr(conn, observation_id="o2", run_id="r1", img=img2, observers=("color",))
    conn.commit()
    item = conn.execute("SELECT item_id FROM observation_items WHERE kind='appearance'").fetchone()[0]
    conn.close()
    built = build_index(store)
    assert built["count"] == 2
    rec = search_similar(store, item)
    assert rec["status"] == "SUCCESS"
    assert rec["fallback"] is None
    assert rec["provider_state"] == "READY"
    assert "authoritative" in rec["reason"] or "derived index" in rec["reason"]
    demanded = search_similar(store, item, require_index=True)
    assert demanded["status"] == "SUCCESS"


def test_circuit_opens_after_repeated_provider_errors(monkeypatch):
    _clear(monkeypatch)
    from semblon.lens import _run

    def crash(_image):
        return _run("barcode", "AVAILABLE", {"crash": "detector"})

    monkeypatch.setattr("semblon.lens.read_symbology", crash)
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    for _ in range(3):
        row = _row(query_image(image, capabilities=("barcode",)), "barcode")
        assert row.status == "ERROR"
    paused = _row(query_image(image, capabilities=("barcode",)), "barcode")
    assert paused.error_id == "barcode.CIRCUIT_OPEN"
    assert paused.status == "UNAVAILABLE"
    assert paused.items == ()


def test_ingest_ocr_circuit_skips_the_provider(monkeypatch, tmp_path):
    from semblon.observers import observe_bgr

    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    calls = {"n": 0}

    def boom(_img):
        calls["n"] += 1
        return {"error": "Boom", "note": "Boom"}

    monkeypatch.setattr("semblon.observers.ocr_image", boom)
    img = np.zeros((8, 8, 3), dtype=np.uint8)
    for _ in range(3):
        observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("text",))
    assert calls["n"] == 3
    observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("text",))
    assert calls["n"] == 3
    last = json.loads(
        conn.execute(
            "SELECT payload_json FROM observation_items WHERE kind='text' ORDER BY rowid DESC"
        ).fetchone()[0]
    )
    assert last["error_id"] == "ocr.CIRCUIT_OPEN"
    assert last["contract_status"] == "UNAVAILABLE"
    assert last["status"] == "unavailable"
