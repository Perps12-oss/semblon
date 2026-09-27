"""Open-vocabulary visual understanding tests + coordinate/hover negatives."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest
import threading

from semblon.geometry import contain_rect, widget_point_to_image
from semblon.pixel_index import build_pixel_index
from semblon.semantic_visual import LocalSemanticVisualProvider, describe_region_appearance
from semblon.visual_analyze import analyze_and_cache, analyze_image, hover_lookup
from semblon.visual_cache import load_analysis
from semblon.visual_segment import (
    SaliencePolicy,
    VisualSegment,
    apply_salience,
    bbox_iou,
    new_segment_id,
)


def _scene(kind: str, size: int = 240) -> np.ndarray:
    """Synthetic BGR scenes with distinct colour structure (no real photos needed)."""
    img = np.zeros((size, size, 3), dtype=np.uint8)
    if kind == "portrait":
        img[:] = (40, 40, 40)
        img[30:90, 80:160] = (90, 140, 200)  # skin-ish
        img[90:200, 60:180] = (60, 50, 140)  # clothing
    elif kind == "group":
        img[:] = (30, 30, 30)
        for i, x in enumerate((40, 100, 160)):
            img[50:100, x : x + 40] = (80 + i * 20, 130, 190)
            img[100:180, x - 10 : x + 50] = (50, 40, 120 + i * 10)
    elif kind == "pet":
        img[:] = (180, 200, 160)  # grass
        img[100:180, 70:170] = (40, 90, 140)  # brown animal
        img[160:175, 90:110] = (20, 20, 200)  # collar-ish
    elif kind == "street":
        img[:100, :] = (210, 180, 120)  # sky-ish
        img[100:, :] = (50, 50, 50)  # road
        img[120:170, 40:120] = (40, 40, 200)  # car
    elif kind == "interior":
        img[:] = (90, 90, 90)
        img[140:, :] = (60, 80, 110)  # floor warm
        img[80:140, 40:120] = (40, 70, 160)  # furniture
    elif kind == "kitchen":
        img[:] = (200, 200, 200)
        img[60:100, 40:100] = (40, 40, 220)  # cup
        img[110:160, 80:180] = (40, 180, 40)  # greens/food
    elif kind == "landscape":
        img[:90, :] = (220, 190, 100)
        img[90:150, :] = (60, 140, 40)
        img[150:, :] = (40, 90, 40)
    elif kind == "forest":
        img[:] = (30, 80, 20)
        img[20:160, 40:70] = (20, 50, 10)
        img[20:180, 140:180] = (25, 55, 15)
    elif kind == "urban":
        img[:80, :] = (180, 160, 100)
        img[80:, :] = (70, 70, 70)
        img[40:160, 30:90] = (90, 90, 100)
        img[50:170, 130:190] = (100, 95, 95)
    elif kind == "product":
        img[:] = (240, 240, 240)
        img[60:180, 70:170] = (40, 40, 40)
        img[90:120, 90:150] = (0, 180, 255)
    elif kind == "screenshot":
        img[:] = (50, 50, 50)
        img[20:40, 20:220] = (200, 200, 200)
        img[60:200, 30:210] = (80, 60, 40)
    elif kind == "clutter":
        rng = np.random.default_rng(0)
        img = rng.integers(0, 255, size=(size, size, 3), dtype=np.uint8)
        img[40:100, 40:100] = (40, 200, 40)
        img[120:200, 120:200] = (200, 40, 40)
    elif kind == "unusual":
        img[:] = (20, 20, 60)
        # Magenta odd object
        img[80:160, 80:160] = (200, 40, 200)
    elif kind == "reflection":
        img[:120, :] = (40, 100, 30)
        img[120:, :] = (80, 60, 30)
        img[140:200, 40:200] = (90, 70, 40)
        # Bright water strip
        img[150:190, 50:190] = (160, 120, 40)
    elif kind == "overlap":
        img[:] = (30, 30, 30)
        img[40:160, 40:160] = (40, 140, 40)
        img[80:180, 80:180] = (40, 40, 180)
    else:
        img[:] = (128, 128, 128)
    return img


CORPUS_KINDS = (
    "portrait",
    "group",
    "pet",
    "street",
    "interior",
    "kitchen",
    "landscape",
    "forest",
    "urban",
    "product",
    "screenshot",
    "clutter",
    "unusual",
    "reflection",
    "overlap",
)


def test_describe_region_is_image_dependent():
    green = np.zeros((40, 40, 3), dtype=np.uint8)
    green[:, :] = (40, 180, 40)
    blue = np.zeros((40, 40, 3), dtype=np.uint8)
    blue[:, :] = (180, 80, 20)
    g_label, _ = describe_region_appearance(green, cy_frac=0.7, area_frac=0.1, aspect=1.0)
    b_label, _ = describe_region_appearance(blue, cy_frac=0.7, area_frac=0.1, aspect=1.0)
    assert g_label != b_label


def test_different_images_produce_different_concept_sets():
    prov = LocalSemanticVisualProvider(max_regions=16)
    inventories = []
    for kind in ("portrait", "pet", "street", "kitchen", "forest"):
        concepts = prov.discover_concepts(_scene(kind))
        labels = frozenset(c["label"].lower() for c in concepts)
        inventories.append(labels)
        assert labels, f"{kind} produced empty inventory"
    # Not all inventories identical — open-vocab requirement.
    assert len(set(inventories)) >= 3


def test_analyze_builds_pixel_index_and_hover(tmp_path):
    img = _scene("landscape", 180)
    store = tmp_path / "store.sqlite"
    store.write_bytes(b"")  # path only; cache uses parent dir
    rec = analyze_and_cache(store, media_id="m1", image=img)
    assert rec["segments"]
    index = rec["index"]
    assert index.coverage_frac() > 0
    # Sample hover through widget transform at fit scale.
    scale = 0.5
    ox, oy = 10.0, 8.0
    # Pick a covered pixel.
    ys, xs = np.where(index.map > 0)
    assert len(xs) > 0
    ix, iy = int(xs[len(xs) // 2]), int(ys[len(ys) // 2])
    wx = ox + ix * scale
    wy = oy + iy * scale
    t0 = time.perf_counter()
    seg = hover_lookup(index, widget_x=wx, widget_y=wy, ox=ox, oy=oy, scale=scale)
    hover_ms = (time.perf_counter() - t0) * 1000
    assert seg is not None
    assert hover_ms < 5.0  # effectively instantaneous
    # Cache hit on reopen.
    t1 = time.perf_counter()
    again = load_analysis(store, "m1")
    cache_ms = (time.perf_counter() - t1) * 1000
    assert again is not None
    assert again["meta"]["n_segments"] == len(rec["segments"])
    assert cache_ms < 500


def test_salience_rejects_tiny_and_huge():
    segs = [
        VisualSegment(
            segment_id=new_segment_id(),
            observation_id=None,
            media_id="m",
            frame_id=None,
            label="dust",
            label_type="region",
            confidence=0.9,
            bbox=(0, 0, 2, 2),
        ),
        VisualSegment(
            segment_id=new_segment_id(),
            observation_id=None,
            media_id="m",
            frame_id=None,
            label="whole",
            label_type="region",
            confidence=0.9,
            bbox=(0, 0, 100, 100),
        ),
        VisualSegment(
            segment_id=new_segment_id(),
            observation_id=None,
            media_id="m",
            frame_id=None,
            label="tree",
            label_type="concept",
            confidence=0.7,
            bbox=(10, 10, 40, 50),
        ),
    ]
    out = apply_salience(segs, image_w=100, image_h=100, policy=SaliencePolicy())
    labels = {s.label for s in out}
    assert "dust" not in labels
    assert "whole" not in labels
    assert "tree" in labels


def test_widget_point_transforms_zoom_pan_aspects():
    # Landscape fit
    box = contain_rect(view_w=400, view_h=200, image_w=200, image_h=100)
    assert box["w"] > 0
    # Canvas-style ox/oy/scale at 100%
    pt = widget_point_to_image(10, 10, ox=10, oy=10, scale=1.0, image_w=100, image_h=80)
    assert pt == (0, 0)
    # Zoomed in (scale 2)
    pt2 = widget_point_to_image(50, 30, ox=10, oy=10, scale=2.0, image_w=100, image_h=80)
    assert pt2 == (20, 10)
    # Outside image
    assert (
        widget_point_to_image(0, 0, ox=10, oy=10, scale=1.0, image_w=100, image_h=80)
        is None
    )
    # Portrait
    pt3 = widget_point_to_image(20, 40, ox=5, oy=5, scale=0.5, image_w=80, image_h=160)
    assert pt3 == (30, 70)
    # Square
    pt4 = widget_point_to_image(15, 15, ox=0, oy=0, scale=1.0, image_w=50, image_h=50)
    assert pt4 == (15, 15)


def test_negative_empty_and_corrupt_images():
    empty = np.zeros((64, 64, 3), dtype=np.uint8)
    rec = analyze_image(empty, media_id="empty")
    assert isinstance(rec["segments"], list)
    # Very dark / very bright
    dark = np.zeros((120, 120, 3), dtype=np.uint8)
    bright = np.full((120, 120, 3), 255, dtype=np.uint8)
    assert analyze_image(dark, media_id="d")["metrics"]["n_segments"] >= 0
    assert analyze_image(bright, media_id="b")["metrics"]["n_segments"] >= 0
    # Low res / high res
    low = _scene("pet", 48)
    high = _scene("pet", 512)
    assert analyze_image(low, media_id="lo")["segments"] is not None
    assert analyze_image(high, media_id="hi")["metrics"]["analysis_s"] < 30


def test_overlapping_and_nested_pixel_map():
    segs = [
        VisualSegment(
            segment_id="parent",
            observation_id=None,
            media_id="m",
            frame_id=None,
            label="person",
            label_type="concept",
            confidence=0.8,
            bbox=(0, 0, 80, 80),
        ),
        VisualSegment(
            segment_id="child",
            observation_id=None,
            media_id="m",
            frame_id=None,
            label="hood",
            label_type="concept",
            confidence=0.9,
            bbox=(10, 10, 40, 40),
            parent_segment_id="parent",
        ),
    ]
    idx = build_pixel_index(segs, height=100, width=100)
    # Child wins in overlap
    assert idx.lookup(20, 20).segment_id == "child"
    # Parent outside child
    assert idx.lookup(70, 70).segment_id == "parent"
    assert bbox_iou(segs[0].bbox, segs[1].bbox) > 0


def test_job_engine_visual_slot(tmp_path, monkeypatch):
    from semblon.jobs import JobBusy, JobEngine

    engine = JobEngine(tmp_path / "s.sqlite")
    img = _scene("product", 100)
    started = threading.Event()
    release = threading.Event()
    done = {"n": 0}

    def slow_analyze_and_cache(*args, **kwargs):
        started.set()
        if not release.wait(5):
            raise RuntimeError("gate timeout")
        return {
            "segments": [],
            "index": None,
            "masks": {},
            "metrics": {"cache_hit": False},
            "provider": "local_opencv",
            "model_id": "local-opencv",
            "model_version": "1",
        }

    monkeypatch.setattr(
        "semblon.visual_analyze.analyze_and_cache", slow_analyze_and_cache
    )

    def on_done(res):
        done["n"] += 1
        done["status"] = res.status

    engine.submit_visual_analyze(media_id="m", image=img, on_done=on_done)
    assert started.wait(2)
    with pytest.raises(JobBusy):
        engine.submit_visual_analyze(media_id="m2", image=img)
    release.set()
    deadline = time.monotonic() + 5
    while engine.visual_busy and time.monotonic() < deadline:
        time.sleep(0.02)
    assert done["n"] == 1
    assert done["status"] == "completed"


def test_corpus_fifteen_images_distinct_labels(tmp_path):
    """Acceptance: radically different images → different useful concept sets."""
    store = tmp_path / "store.sqlite"
    store.write_bytes(b"")
    label_sets = []
    metrics_rows = []
    for kind in CORPUS_KINDS:
        img = _scene(kind, 200)
        rec = analyze_and_cache(store, media_id=f"media-{kind}", image=img)
        labels = frozenset(s.label.lower() for s in rec["segments"])
        label_sets.append(labels)
        metrics_rows.append(
            {
                "kind": kind,
                "n": len(rec["segments"]),
                "labels": sorted(labels),
                "coverage": rec["metrics"].get("coverage_frac"),
                "analysis_s": rec["metrics"].get("analysis_s"),
            }
        )
    unique = len(set(label_sets))
    assert unique >= 8, f"inventories too similar across corpus: {metrics_rows}"
    # Persist eval artifact for the deliverable report.
    out = Path(tmp_path) / "corpus_eval.json"
    import json

    out.write_text(json.dumps(metrics_rows, indent=2), encoding="utf-8")
    assert out.is_file()


def test_provider_protocol_methods_exist():
    p = LocalSemanticVisualProvider()
    img = _scene("reflection", 120)
    assert isinstance(p.discover_regions(img), list)
    assert isinstance(p.discover_concepts(img), list)
    assert isinstance(p.segment_concept(img, "water"), list)
    assert p.refine_from_point(img, 60, 60) is not None
    assert p.refine_from_box(img, (20, 20, 80, 80)) is not None
