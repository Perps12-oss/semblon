"""SAM 2 spatial discovery: capability states, nesting, and hover isolation.

Live weights are not required. A package import is never SAM2_READY.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pytest

from semblon.pixel_index import build_pixel_index
from semblon.sam2_runtime import (
    SAM2_AVAILABLE,
    SAM2_LOAD_FAILURE,
    SAM2_NOT_CONFIGURED,
    SAM2_NOT_INSTALLED,
    SAM2_READY,
    SAM2_WEIGHTS_MISSING,
    Sam2Session,
    Sam2Status,
    probe_sam2,
    reset_session_for_tests,
)
from semblon.semantic_visual import LocalSemanticVisualProvider
from semblon.visual_analyze import analyze_and_cache, analyze_image, hover_lookup
from semblon.visual_segment import (
    VisualSegment,
    apply_salience,
    link_segment_lattice,
    nested_relation,
    new_segment_id,
)


@pytest.fixture(autouse=True)
def _reset_sam2(monkeypatch):
    reset_session_for_tests()
    monkeypatch.delenv("SEMBLON_SAM2_CHECKPOINT", raising=False)
    monkeypatch.delenv("SEMBLON_SAM2_CONFIG", raising=False)
    monkeypatch.delenv("SEMBLON_SAM2_SHA256", raising=False)
    yield
    reset_session_for_tests()


def _status(**kwargs) -> Sam2Status:
    base = dict(state=SAM2_NOT_CONFIGURED, detail="", package_version="test")
    base.update(kwargs)
    return Sam2Status(**base)


def test_missing_package_is_not_ready(monkeypatch):
    monkeypatch.setattr("semblon.sam2_runtime.sam2_importable", lambda: False)
    status = probe_sam2(attempt_load=True)
    assert status.state == SAM2_NOT_INSTALLED
    assert status.ready is False


def test_package_without_checkpoint_is_not_configured(monkeypatch):
    monkeypatch.setattr("semblon.sam2_runtime.sam2_importable", lambda: True)
    status = probe_sam2(attempt_load=True)
    assert status.state == SAM2_NOT_CONFIGURED
    assert status.state != SAM2_READY


def test_missing_checkpoint_file(monkeypatch, tmp_path):
    monkeypatch.setattr("semblon.sam2_runtime.sam2_importable", lambda: True)
    missing = tmp_path / "sam2.1_hiera_small.pt"
    monkeypatch.setenv("SEMBLON_SAM2_CHECKPOINT", str(missing))
    status = probe_sam2()
    assert status.state == SAM2_WEIGHTS_MISSING
    assert status.ready is False


def test_invalid_checkpoint_is_load_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("semblon.sam2_runtime.sam2_importable", lambda: True)
    bad = tmp_path / "sam2.1_hiera_small.pt"
    bad.write_bytes(b"not a checkpoint")
    monkeypatch.setenv("SEMBLON_SAM2_CHECKPOINT", str(bad))
    status = probe_sam2(attempt_load=True)
    assert status.state == SAM2_LOAD_FAILURE
    assert status.ready is False


def test_weights_present_without_load_is_available_not_ready(monkeypatch, tmp_path):
    monkeypatch.setattr("semblon.sam2_runtime.sam2_importable", lambda: True)
    ckpt = tmp_path / "sam2.1_hiera_small.pt"
    ckpt.write_bytes(b"x" * 2048)
    monkeypatch.setenv("SEMBLON_SAM2_CHECKPOINT", str(ckpt))
    status = probe_sam2(attempt_load=False)
    assert status.state == SAM2_AVAILABLE
    assert status.ready is False


def test_successful_initialization(monkeypatch, tmp_path):
    monkeypatch.setattr("semblon.sam2_runtime.sam2_importable", lambda: True)
    ckpt = tmp_path / "sam2.1_hiera_small.pt"
    ckpt.write_bytes(b"x" * 2048)
    monkeypatch.setenv("SEMBLON_SAM2_CHECKPOINT", str(ckpt))

    def builder(config, checkpoint, device):
        assert "sam2.1_hiera_s" in config
        assert device in {"cpu", "cuda"}
        return object(), object(), object()

    status = probe_sam2(attempt_load=True, builder=builder)
    assert status.state == SAM2_READY
    assert status.ready is True


def test_provider_load_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("semblon.sam2_runtime.sam2_importable", lambda: True)
    ckpt = tmp_path / "sam2.1_hiera_small.pt"
    ckpt.write_bytes(b"x" * 2048)
    monkeypatch.setenv("SEMBLON_SAM2_CHECKPOINT", str(ckpt))

    def builder(config, checkpoint, device):
        raise RuntimeError("bad weights")

    status = probe_sam2(attempt_load=True, builder=builder)
    assert status.state == SAM2_LOAD_FAILURE
    assert "bad weights" in status.detail


def test_nested_part_is_retained_and_contained():
    person = VisualSegment(
        segment_id="person",
        observation_id=None,
        media_id="m",
        frame_id=None,
        label="region",
        label_type="unknown",
        confidence=0.8,
        bbox=(10, 10, 90, 90),
    )
    hood = VisualSegment(
        segment_id="hood",
        observation_id=None,
        media_id="m",
        frame_id=None,
        label="region",
        label_type="unknown",
        confidence=0.7,
        bbox=(20, 12, 50, 35),
    )
    hand = VisualSegment(
        segment_id="hand",
        observation_id=None,
        media_id="m",
        frame_id=None,
        label="region",
        label_type="unknown",
        confidence=0.66,
        bbox=(60, 55, 82, 78),
    )
    assert nested_relation(hood.bbox, person.bbox) == "a_in_b"
    kept = apply_salience(
        [person, hood, hand], image_w=100, image_h=100
    )
    ids = {seg.segment_id for seg in kept}
    assert {"person", "hood", "hand"} <= ids
    lattice = link_segment_lattice(kept)
    parents = {child: parent for child, parent in lattice["contains"]}
    assert parents["hood"] == "person"
    assert parents["hand"] == "person"
    parent_mask = np.zeros((100, 100), np.uint8)
    parent_mask[10:90, 10:90] = 255
    hood_mask = np.zeros((100, 100), np.uint8)
    hood_mask[12:35, 20:50] = 255
    index = build_pixel_index(
        kept,
        height=100,
        width=100,
        masks={"person": parent_mask, "hood": hood_mask, "hand": np.zeros((100, 100), np.uint8)},
    )
    assert index.lookup(30, 20).segment_id == "hood"
    assert index.lookup(70, 70).segment_id == "person"


def test_hover_lookup_does_not_call_sam2(monkeypatch):
    calls = []

    def boom(*_args, **_kwargs):
        calls.append("generate")
        raise AssertionError("hover must not run SAM 2")

    monkeypatch.setattr("semblon.sam2_runtime.generate_regions", boom)
    monkeypatch.setattr("semblon.sam2_runtime.predict_point", boom)
    seg = VisualSegment(
        segment_id=new_segment_id(),
        observation_id=None,
        media_id="m",
        frame_id=None,
        label="region",
        label_type="unknown",
        confidence=0.5,
        bbox=(0, 0, 10, 10),
    )
    index = build_pixel_index([seg], height=20, width=20)
    t0 = time.perf_counter()
    found = hover_lookup(index, widget_x=2, widget_y=2, ox=0, oy=0, scale=1)
    elapsed = time.perf_counter() - t0
    assert found is seg
    assert calls == []
    assert elapsed < 0.05


def test_analysis_does_not_mutate_store_or_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "semblon.sam2_runtime.provider_for_discovery",
        lambda: (LocalSemanticVisualProvider(), _status()),
    )
    store = tmp_path / "store.sqlite"
    store.write_bytes(b"identity-bytes-must-stay")
    image = np.full((64, 64, 3), 40, np.uint8)
    image[16:48, 16:48] = (20, 140, 20)
    before = store.read_bytes()
    analyze_and_cache(store, media_id="m1", image=image, provider=LocalSemanticVisualProvider())
    assert store.read_bytes() == before


def test_reanalysis_replaces_cache(tmp_path):
    store = tmp_path / "store.sqlite"
    store.write_bytes(b"")
    image = np.zeros((80, 80, 3), np.uint8)
    image[:, :40] = (180, 40, 40)
    provider = LocalSemanticVisualProvider()
    first = analyze_and_cache(store, media_id="m", image=image, provider=provider)
    created = first["metrics"].get("analysis_s")
    assert first["metrics"]["cache_hit"] is False
    time.sleep(0.02)
    second = analyze_and_cache(
        store, media_id="m", image=image, provider=provider, force=True
    )
    assert second["metrics"]["cache_hit"] is False
    assert second["metrics"]["analysis_s"] >= 0
    cached = analyze_and_cache(store, media_id="m", image=image, provider=provider)
    assert cached["metrics"]["cache_hit"] is True
    assert created is not None


def test_cancel_visual_job(tmp_path, monkeypatch):
    from semblon.jobs import JobEngine

    engine = JobEngine(tmp_path / "s.sqlite")

    class Slow(LocalSemanticVisualProvider):
        def discover_regions(self, image):
            engine.cancel_visual()
            return []

    monkeypatch.setattr(
        "semblon.sam2_runtime.provider_for_discovery",
        lambda: (Slow(), _status()),
    )
    done = {}

    def on_done(result):
        done["status"] = result.status

    engine.submit_visual_analyze(
        media_id="m", image=np.zeros((32, 32, 3), np.uint8), on_done=on_done
    )
    deadline = time.monotonic() + 5
    while "status" not in done and time.monotonic() < deadline:
        time.sleep(0.02)
    assert done.get("status") == "cancelled"


def test_generate_regions_keeps_nested_mask(monkeypatch):
    from semblon.sam2_runtime import generate_regions

    class Generator:
        def generate(self, rgb):
            h, w = rgb.shape[:2]
            parent = np.zeros((h, w), dtype=bool)
            parent[5:95, 5:95] = True
            child = np.zeros((h, w), dtype=bool)
            child[10:30, 10:40] = True
            return [
                {"segmentation": parent, "predicted_iou": 0.91, "stability_score": 0.95},
                {"segmentation": child, "predicted_iou": 0.84, "stability_score": 0.93},
            ]

    session = Sam2Session(
        model=object(),
        generator=Generator(),
        predictor=object(),
        device="cpu",
        checkpoint="local",
        config="configs/sam2.1/sam2.1_hiera_s.yaml",
        package_version="1.0",
        runtime={"execution": "emulated", "process_arch": "x64", "device": "cpu"},
    )
    monkeypatch.setattr(
        "semblon.sam2_runtime.probe_sam2",
        lambda **kwargs: Sam2Status(state=SAM2_READY, detail="test"),
    )
    monkeypatch.setattr("semblon.sam2_runtime.ensure_session", lambda **kwargs: session)
    image = np.zeros((100, 100, 3), np.uint8)
    regions, stats = generate_regions(image)
    assert stats["n_raw"] == 2
    assert stats["n_nested_retained"] == 1
    assert len(regions) == 2
    assert all(reg["label"] == "region" for reg in regions)
    assert all(reg["payload"]["naming"] == "pending" for reg in regions)


def test_naming_can_abstain(monkeypatch):
    monkeypatch.setattr(
        "semblon.sam2_runtime.provider_for_discovery",
        lambda: (LocalSemanticVisualProvider(), _status()),
    )

    class Unnamed(LocalSemanticVisualProvider):
        info = LocalSemanticVisualProvider.info

        def discover_regions(self, image):
            return [
                {
                    "bbox": (10.0, 10.0, 40.0, 40.0),
                    "label": "region",
                    "label_type": "unknown",
                    "confidence": 0.8,
                    "mask": None,
                    "source_provider": "sam2",
                    "payload": {"naming": "pending"},
                }
            ]

        def discover_concepts(self, image, *, regions=None):
            return []

    Unnamed.info = type(LocalSemanticVisualProvider.info)(
        name="sam2", model_id="sam2.1_hiera_small", model_version="1"
    )
    image = np.full((80, 80, 3), 30, np.uint8)
    rec = analyze_image(image, media_id="m", provider=Unnamed())
    assert rec["metrics"]["names_proposed"] >= 1
    assert rec["metrics"]["readiness"] == "L4"
    named = [seg for seg in rec["segments"] if seg.source_provider == "sam2"]
    assert named
    for seg in named:
        assert seg.payload.get("namer") == "appearance"
        assert seg.payload.get("naming") in {"bind", "abstain"}
        assert "hood" not in seg.label.lower()


@pytest.fixture(scope="module")
def tk_root():
    pytest.importorskip("tkinter")
    import tkinter as tk

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"tkinter could not start: {exc}")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_canvas_hover_never_infers_and_job_runs(tk_root, tmp_path, monkeypatch):
    import inspect

    from semblon.canvas import CanvasWorkspace

    calls = []
    monkeypatch.setattr(
        "semblon.sam2_runtime.generate_regions",
        lambda *a, **k: calls.append("generate") or (_ for _ in ()).throw(AssertionError("hover")),
    )
    monkeypatch.setattr(
        "semblon.sam2_runtime.predict_point",
        lambda *a, **k: calls.append("point"),
    )
    monkeypatch.setattr(
        "semblon.sam2_runtime.provider_for_discovery",
        lambda: (LocalSemanticVisualProvider(), _status()),
    )
    monkeypatch.setattr("semblon.semantic_visual._clip_image_concepts", lambda *a, **k: [])
    monkeypatch.setattr("semblon.semantic_visual._vlm_image_concepts", lambda *a, **k: [])
    store = tmp_path / "store.sqlite"
    store.write_bytes(b"")
    image_path = tmp_path / "photo.png"
    import cv2

    cv2.imwrite(str(image_path), np.full((120, 160, 3), (40, 90, 140), np.uint8))
    ws = CanvasWorkspace(tk_root, enable_visual=True)
    ws.pack()
    media = {"media_id": "photo-1", "path": str(image_path), "source_type": "folder"}
    ws.board = {"media": [media], "faces": [], "items": [], "_store": str(store)}
    ws._media = [media]
    state = {"shown": False}

    def _open():
        if state["shown"]:
            return
        state["shown"] = True
        ws.show_media(media)

    def _pump():
        if ws._visual_index is not None:
            ws.preview.event_generate("<Motion>", x=40, y=40)
            state["hovered"] = True
            tk_root.quit()
            return
        tk_root.after(40, _pump)

    tk_root.after(0, _open)
    tk_root.after(40, _pump)
    tk_root.after(20000, tk_root.quit)
    tk_root.mainloop()
    assert ws._visual_index is not None
    motion = inspect.getsource(ws._on_motion)
    assert "generate_regions" not in motion
    assert "discover_regions" not in motion
    assert "predict_point" not in motion
    assert "generate" not in calls
    assert "point" not in calls
    assert state.get("hovered") is True
    assert ws.status.get()
