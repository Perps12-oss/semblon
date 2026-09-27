"""Visual regions: discovery is slow, hover is a lookup, identity stays shut."""

from __future__ import annotations

import inspect
import threading
from pathlib import Path

import numpy as np

from semblon.jobs import JobBusy, JobEngine
from semblon.product_surface import soft_inspector_for_item, soft_object_label
from semblon.store import connect, init_db
from semblon.visual.engine import analyse, capabilities
from semblon.visual.hover import HoverIndex, buffer_pixel, widget_point_to_native
from semblon.visual.model import VisualConfig, VisualRegion
from semblon.visual.naming import bind_label, split_proposals
from semblon.visual.persist import load_hover_rows, persist_analysis
from semblon.visual.protocol import FAILURE_CLASSES, sheet
from semblon.visual.render import display_runs


def _scene():
    h, w = 80, 120
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:] = (40, 90, 40)  # grass
    rgb[:30, :] = (120, 170, 220)  # sky
    person = np.zeros((h, w), dtype=bool)
    person[28:70, 40:78] = True
    hood = np.zeros((h, w), dtype=bool)
    hood[28:42, 46:72] = True
    hand = np.zeros((h, w), dtype=bool)
    hand[50:62, 70:84] = True
    rgb[person] = (180, 70, 60)
    rgb[hood] = (210, 170, 40)
    rgb[hand] = (230, 190, 160)
    return rgb, person, hood, hand


def _seed(path: Path):
    conn = connect(path)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',120,80,0,1)")
    conn.commit()
    conn.close()


def test_containment_keeps_nested_nms_drops_heavy_overlap():
    rgb, person, _hood, _hand = _scene()
    jacket = person.copy()
    jacket[28:32, :] = False  # still almost the person box
    base = dict(view_w=120, view_h=80)
    kept = analyse(
        rgb,
        config=VisualConfig(dedupe="containment", min_area_frac=0.001, display_min_px=1, contain_ratio=0.8),
        user_masks=[person, jacket],
        **base,
    )
    dropped = analyse(
        rgb,
        config=VisualConfig(dedupe="nms", nms_iou=0.5, min_area_frac=0.001, display_min_px=1),
        user_masks=[person, jacket],
        **base,
    )
    assert kept.diagnostics["stages"]["deduped"] > dropped.diagnostics["stages"]["deduped"]
    assert any(row.get("stage") == "dedupe" for row in dropped.diagnostics["removed"])


def test_owner_prefers_part_and_hover_does_not_rename():
    rgb, person, hood, _hand = _scene()
    calls = {"n": 0}

    def score(_rid, noun):
        calls["n"] += 1
        return {"hood": 0.9, "person": 0.4, "fabric": 0.2}.get(noun, 0.0)

    analysis = analyse(
        rgb,
        config=VisualConfig(min_area_frac=0.001, display_min_px=1, name_abs=0.28, name_margin=0.05),
        user_masks=[person, hood],
        nouns=["hood", "person", "fabric", "John"],
        score_fn=score,
    )
    hood_regions = [r for r in analysis.regions if r.label == "hood"]
    assert hood_regions, [((r.kind, r.label, r.fate), r.label_candidates) for r in analysis.regions]
    owner = analysis.region(int(analysis.owner[32, 55]))
    assert owner is not None and owner.label == "hood" and owner.kind == "part"
    index = HoverIndex(analysis.owner, analysis.regions)
    before = calls["n"]
    a = index.pointer(55, 32)
    b = index.pointer(56, 32)
    assert a.changed and a.label == "hood"
    assert not b.changed
    assert index.suppressed == 1
    assert calls["n"] == before


def test_abstain_and_proper_names():
    concepts, proper = split_proposals(["John", "hood", "Mary Ann"])
    assert "John" in proper and "hood" in concepts
    region = VisualRegion(region_id=1, bbox=(0, 0, 4, 4), area=16, kind="thing")

    def weak(_rid, noun):
        return 0.1

    bind_label(region, ["widget", "John"], weak, parent=None, config=VisualConfig())
    assert region.label is None
    assert "John" in region.proper_name_proposals


def test_display_area_hides_speck_when_zoomed_out():
    rgb = np.zeros((100, 100, 3), dtype=np.uint8)
    rgb[:] = 20
    speck = np.zeros((100, 100), dtype=bool)
    speck[50:52, 50:52] = True
    big = np.zeros((100, 100), dtype=bool)
    big[10:90, 10:90] = True
    far = analyse(
        rgb,
        config=VisualConfig(min_area_frac=0.0001, display_min_px=500),
        user_masks=[big, speck],
        view_w=100,
        view_h=100,
    )
    assert all(r.area > 10 for r in far.regions)
    near = analyse(
        rgb,
        config=VisualConfig(min_area_frac=0.0001, display_min_px=1),
        user_masks=[big, speck],
        view_w=400,
        view_h=400,
    )
    assert any(r.area <= 10 for r in near.regions)


def test_coordinates_letterbox_and_zoom():
    # 200x100 image in a square view is letterboxed top and bottom.
    assert widget_point_to_native(2, 2, view_w=200, view_h=200, image_w=200, image_h=100) is None
    hit = widget_point_to_native(100, 100, view_w=200, view_h=200, image_w=200, image_h=100, zoom=1)
    assert hit == (100, 50)
    zoomed = widget_point_to_native(100, 100, view_w=200, view_h=200, image_w=200, image_h=100, zoom=2)
    assert zoomed == (100, 50)
    dpi = widget_point_to_native(200, 200, view_w=200, view_h=200, image_w=200, image_h=100, dpi_scale=2)
    assert dpi == (100, 50)


def test_persist_does_not_create_a_person(tmp_path):
    rgb, person, hood, _hand = _scene()
    analysis = analyse(
        rgb,
        config=VisualConfig(min_area_frac=0.001, display_min_px=1),
        user_masks=[person, hood],
        nouns=["hood", "person"],
        score_fn=lambda _i, noun: 0.8 if noun == "hood" else 0.2,
    )
    store = tmp_path / "s.sqlite"
    _seed(store)
    conn = connect(store)
    conn.execute("INSERT INTO persons VALUES ('p1','Ada','active','r1')")
    conn.commit()
    conn.close()
    rec = persist_analysis(store, analysis, media_id="m1", run_id="r1")
    assert rec["persons"] == 1
    again = persist_analysis(store, analysis, media_id="m1", run_id="r1")
    assert again["items"] == rec["items"]
    loaded = load_hover_rows(store, media_id="m1", run_id="r1")
    assert len(loaded) == rec["items"]
    conn = connect(store)
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0] == 0
    kinds = {row[0] for row in conn.execute("SELECT kind FROM relationships")}
    conn.close()
    assert kinds <= {"contains", "overlaps"}


def test_sam2_is_not_ready_without_weights():
    caps = capabilities()
    assert caps["visual.discovery.sam2"]["state"] in {"UNAVAILABLE", "PARTIAL"}
    assert caps["visual.hover"]["state"] == "READY"
    assert caps["visual.naming.siglip"]["state"] == "UNAVAILABLE"


def test_pointer_outside_is_unassigned():
    owner = np.zeros((4, 4), dtype=np.uint16)
    owner[1, 1] = 3
    index = HoverIndex(owner, [])
    assert index.pointer(1, 1).region_id == 3
    assert index.pointer(-1, 0).region_id == 0
    assert index.lookups == 2


def test_colour_does_not_invent_a_name():
    rgb, *_ = _scene()
    analysis = analyse(rgb, config=VisualConfig(min_area_frac=0.001, display_min_px=1))
    assert all(region.label is None for region in analysis.regions)
    assert any(region.kind == "stuff" for region in analysis.regions)


def test_fabric_under_a_named_parent_is_not_the_hover_piece():
    rgb, person, hood, _hand = _scene()

    def score(region, noun, parent):
        if region.area < 500:
            return {"fabric": 0.93, "hood": 0.2}.get(noun, 0.0)
        return {"person": 0.9, "fabric": 0.1}.get(noun, 0.0)

    analysis = analyse(
        rgb,
        config=VisualConfig(min_area_frac=0.001, display_min_px=1, name_margin=0.05),
        user_masks=[person, hood],
        nouns=["fabric", "hood", "person"],
        score_fn=score,
    )
    owner = analysis.region(int(analysis.owner[32, 55]))
    assert owner is None or owner.label != "fabric"
    assert any(
        row.get("stage") == "slice" and row.get("kind") == "part"
        for row in analysis.diagnostics["removed"]
    )


def test_face_projection_wins_its_pixels_and_is_not_an_enrolment():
    rgb, person, _hood, _hand = _scene()
    analysis = analyse(
        rgb,
        config=VisualConfig(min_area_frac=0.001, display_min_px=1),
        user_masks=[person],
        face_boxes=[(48, 30, 16, 16)],
    )
    owner = analysis.region(int(analysis.owner[34, 52]))
    assert owner is not None and owner.kind == "face" and owner.method == "face_projection"
    assert owner.label is None


def test_user_proper_name_is_not_a_person(tmp_path):
    rgb, person, _hood, _hand = _scene()
    analysis = analyse(
        rgb,
        config=VisualConfig(min_area_frac=0.001, display_min_px=1),
        user_regions=[{"mask": person, "label": "John"}],
    )
    held = [region for region in analysis.regions if region.method == "user"]
    assert held and held[0].label is None and "John" in held[0].proper_name_proposals
    store = tmp_path / "s.sqlite"
    _seed(store)
    rec = persist_analysis(store, analysis, media_id="m1", run_id="r1")
    assert rec["persons"] == 0


def test_cancel_does_not_return_a_map():
    rgb = np.zeros((24, 24, 3), dtype=np.uint8)
    analysis = analyse(rgb, cancel=lambda: True)
    assert analysis.level == 0 and analysis.regions == []


def test_orientation_and_display_runs():
    assert buffer_pixel(1, 0, 2, 2, 6) == (0, 0)
    assert buffer_pixel(0, 0, 2, 2, 1) == (0, 0)
    rects = display_runs({"1": [[0, 2]]}, scale=2, ox=4, oy=6)
    assert rects == [(4.0, 8.0, 8.0, 10.0)]


def test_hover_module_does_not_import_a_model():
    import semblon.visual.hover as hover

    src = inspect.getsource(hover).lower()
    assert "sam2" not in src and "siglip" not in src and "embed" not in src


def test_unnamed_chip_stays_blank():
    item = {
        "provider": "visual.region",
        "payload": {"class": "visual_region", "selected_label": None, "kind": "part"},
    }
    assert soft_object_label(item) == ""
    text = "\n".join(soft_inspector_for_item(item))
    assert "Unknown" not in text
    assert "not a person identity" in text


def test_visual_job_finishes_without_a_person(tmp_path):
    rgb, _person, _hood, _hand = _scene()
    store = tmp_path / "s.sqlite"
    _seed(store)
    engine = JobEngine(store)
    done = threading.Event()
    box: dict = {}

    def on_done(result):
        box["result"] = result
        done.set()

    engine.submit_visual(media_id="m1", image=rgb, run_id="r1", on_done=on_done)
    assert done.wait(8)
    assert box["result"].status == "completed"
    assert box["result"].rec["persons"] == 0
    assert engine.busy is False
    assert engine.ingest_busy is False


def test_visual_job_holds_the_single_door(tmp_path, monkeypatch):
    started = threading.Event()
    release = threading.Event()

    def slow(image, **kwargs):
        started.set()
        release.wait(2)
        return analyse(image, **kwargs)

    monkeypatch.setattr("semblon.visual.engine.analyse", slow)
    store = tmp_path / "s.sqlite"
    _seed(store)
    engine = JobEngine(store)
    rgb, *_ = _scene()
    engine.submit_visual(media_id="m1", image=rgb, run_id="r1")
    assert started.wait(2)
    try:
        try:
            engine.submit_visual(media_id="m1", image=rgb, run_id="r1")
            raised = False
        except JobBusy:
            raised = True
        assert raised
        assert engine.ingest_busy is False
    finally:
        release.set()


def test_protocol_sheet_is_blank():
    rows = sheet(["a.jpg", "b.jpg"])
    assert len(rows) == 2 and rows[0]["meaningful"] is None
    assert "NAMING" in FAILURE_CLASSES and "PROVIDER" in FAILURE_CLASSES
