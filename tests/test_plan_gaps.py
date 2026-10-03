"""Plan-gap surfaces: canvas, Home sidebar, modality product, GPU product wiring."""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path
from unittest.mock import patch

from semblon.canvas import (
    CanvasWorkspace,
    face_evidence_tag,
    load_canvas,
    media_inspector_lines,
    overlay_boxes,
)
from semblon.home_ui import (
    HOME_NAV,
    HOME_OBSERVERS,
    format_library_lines,
    home_control_states,
    resolve_home_observers,
    resolve_home_prefer_gpu,
)
from semblon.jobs import JobEngine
from semblon.observers import (
    modality_product_settings_lines,
    optional_status,
    resolve_product_observers,
)


def _seed(store: Path) -> sqlite3.Connection:
    from semblon.store import init_db

    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/tmp/a.jpg','aaa',100,100,0,1)")
    conn.execute("INSERT INTO media VALUES ('m2','video','/tmp/b.mp4','bbb',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,cluster_id)
           VALUES ('f1','o1','r1',1,2,10,12,0.9,9,10,'80-119','ok',NULL)"""
    )
    conn.commit()
    return conn


# ── Gap 1: Canvas production renderer ─────────────────────────────────────


def test_overlay_boxes_omit_person_id():
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
                "person_id": "p1",
            }
        ],
        "items": [],
        "track_lane_by_face": {},
        "track_lane_by_item": {},
    }
    boxes = overlay_boxes(board, "m1")
    assert len(boxes) == 1
    assert "person_id" not in boxes[0]
    assert boxes[0]["tag"] == "clustered"
    assert face_evidence_tag({"face_id": "f0", "cluster_id": None, "bbox_x1": 0}) == "detected"
    assert face_evidence_tag({"cluster_id": "c1", "face_id": "f1"}) == "clustered"


def test_canvas_load_note_firewall(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    board = load_canvas(store, "r1")
    assert "never writes" in board["note"].lower() or "person_id" in board["note"]
    lines = media_inspector_lines(board, "m1")
    text = "\n".join(lines)
    assert "group" in text.lower() or "person" in text.lower()
    for box in overlay_boxes(board, "m1"):
        assert "person_id" not in box


def test_canvas_workspace_is_embeddable():
    import semblon.canvas as canvas_mod

    # Module source (not the headless stub) must expose embed API.
    src = inspect.getsource(canvas_mod)
    assert "class CanvasWorkspace" in src
    assert "on_select" in src
    assert "def reload" in src
    assert "def pack" in src
    assert "never writes" in (canvas_mod.CANVAS_NOTE or "").lower() or "person_id" in canvas_mod.CANVAS_NOTE


# ── Gap 2: Home sidebar shell ──────────────────────────────────────────────


def test_home_nav_matches_r3_ia():
    """Compact destinations remain library/people/activity — not a MAIN sidebar."""
    sections = {s: [i for i, _ in items] for s, items in HOME_NAV}
    assert sections["MAIN"] == ["library", "people", "activity"]
    assert "ASK" not in sections
    assert "LIBRARY" not in sections
    assert "PEOPLE" not in sections
    assert "ACTIVITY" not in sections


def test_home_shell_source_has_model_d_chrome():
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp)
    assert "WORKSPACE / INTELLIGENCE CANVAS" in src
    assert "INSPECTOR" in src
    assert "CanvasWorkspace" in src
    assert "JobEngine" in src
    assert "resolve_home_observers" in src
    assert "prefer_gpu" in src
    assert "_set_inspector" in src
    assert "_show_stage" in src
    assert "btn_discover" in src
    assert "_sidebar = None" in src
    assert "StageCapabilityCard" in inspect.getsource(home_ui.HomeApp._show_stage)


def test_library_lines_filter(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    photos = "\n".join(format_library_lines(store, source_type="folder"))
    videos = "\n".join(format_library_lines(store, source_type="video"))
    assert "a.jpg" in photos
    assert "b.mp4" not in photos
    assert "b.mp4" in videos


def test_home_controls_still_open_during_ingest():
    busy = home_control_states(job_running=True, resume_ready=False)
    # Canvas is not product chrome; live stays usable. Lens is a nav route, not a lock key.
    for name in ("review", "people", "search", "unknown", "activity", "settings", "live"):
        assert busy[name] == "normal"
    assert "canvas" not in busy
    assert "html" not in busy


# ── Gap 3: OCR/CLIP/pose productization ────────────────────────────────────


def test_resolve_product_observers_base_when_gate_off(monkeypatch):
    monkeypatch.setenv("SEMBLON_MODALITY_PRODUCT", "0")
    assert resolve_product_observers() == "face,color,object"
    assert HOME_OBSERVERS == "face,color,object"


def test_resolve_product_observers_appends_ready_only(monkeypatch):
    monkeypatch.delenv("SEMBLON_MODALITY_PRODUCT", raising=False)
    fake = {
        "ocr": True,
        "clip": False,
        "pose": True,
        "notes": {"clip": "unavailable: missing"},
        "identity": "facekit only",
        "note": "x",
    }
    with patch("semblon.observers.optional_status", return_value=fake):
        csv = resolve_product_observers()
    # OCR probe maps to observer token "text"
    assert csv == "face,color,object,text,pose"
    assert "clip" not in csv.split(",")


def test_modality_settings_lines_honesty(monkeypatch):
    monkeypatch.delenv("SEMBLON_MODALITY_PRODUCT", raising=False)
    lines = modality_product_settings_lines()
    text = "\n".join(lines)
    assert "optional ocr=" in text
    assert "never write" in text.lower() or "facekit" in text.lower()


def test_home_resolve_observers_matches_product():
    assert resolve_home_observers() == resolve_product_observers()


# ── Gap 4: GPU productization (wiring through JobEngine / Home) ────────────


def test_home_prefer_gpu_follows_product(monkeypatch):
    monkeypatch.setattr("semblon.engine.onnx_providers", lambda: ["CPUExecutionProvider"])
    assert resolve_home_prefer_gpu() is False
    monkeypatch.setattr(
        "semblon.engine.onnx_providers",
        lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    assert resolve_home_prefer_gpu() is True


def test_job_engine_passes_prefer_gpu(tmp_path, monkeypatch):
    saw = {}

    def fake_process(folder, **kwargs):
        saw.update(kwargs)
        return {"run_id": "r-gpu"}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    engine = JobEngine(tmp_path / "s.sqlite")
    engine.run_ingest(tmp_path / "photos", observers="face", prefer_gpu=True)
    assert saw.get("prefer_gpu") is True


def test_optional_status_still_honest():
    st = optional_status()
    assert st["identity"] == "facekit only"
    assert "notes" in st
