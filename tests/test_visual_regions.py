"""Visual regions: discovery is slow, hover is a lookup, identity stays shut."""

from __future__ import annotations

import inspect
import threading
from pathlib import Path

import numpy as np

from semblon.jobs import JobBusy, JobEngine
from semblon.product_surface import soft_inspector_for_item, soft_object_label
from semblon.store import connect, init_db
from semblon.visual.discovery import Sam2AmgDiscovery, clear_sam2_runtime, mark_sam2_failed, sam2_capability
from semblon.visual.engine import analyse, capabilities
from semblon.visual.hover import (
    HoverIndex,
    buffer_pixel,
    canvas_point_to_native,
    owner_from_stored,
    widget_point_to_native,
)
from semblon.visual.masks import MaskCand
from semblon.visual.model import VisualConfig, VisualRegion
from semblon.visual.naming import bind_label, split_proposals
from semblon.visual.naming_local import gated_similarity
from semblon.visual.persist import load_hover_rows, persist_analysis, should_submit_visual
from semblon.visual.protocol import FAILURE_CLASSES, sheet
from semblon.visual.render import display_runs, mask_png


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


def _bind_scene(store: Path, rgb, media_id: str = "m1") -> None:
    """Point media_id at a real file. The job decodes it; callers do not pass arrays."""
    import cv2

    photo = store.parent / f"{media_id}.png"
    frame = np.ascontiguousarray(np.asarray(rgb)[:, :, :3][:, :, ::-1])
    assert cv2.imwrite(str(photo), frame)
    conn = connect(store)
    conn.execute(
        "UPDATE media SET path=?, width=?, height=? WHERE media_id=?",
        (str(photo), int(rgb.shape[1]), int(rgb.shape[0]), media_id),
    )
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
    analysis = analyse(
        rgb,
        config=VisualConfig(min_area_frac=0.001, display_min_px=1),
        allow_local_naming=False,
    )
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


def test_saved_human_region_name_is_reused_by_surface():
    # user_region.name_user_region persists this field. The surface must not
    # discard that memory and fall back to a generic label.
    named_region = {
        "provider": "user_box",
        "kind": "object",
        "payload": {"class": "user_region", "named": "my red toolbox"},
    }
    assert soft_object_label(named_region) == "my red toolbox"

    named_visual = {
        "provider": "visual.region",
        "payload": {"class": "visual_region", "selected_label": None, "named": "garden gate"},
    }
    assert soft_object_label(named_visual) == "garden gate"


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

    _bind_scene(store, rgb)
    engine.submit_visual(media_id="m1", run_id="r1", on_done=on_done)
    assert done.wait(8)
    assert box["result"].status == "completed"
    assert box["result"].rec["persons"] == 0
    assert engine.busy is False
    assert engine.ingest_busy is False


def test_rss_kb_is_absent_without_resource(monkeypatch):
    import builtins
    import sys

    from semblon.jobs import _process_rss_kb

    real_import = builtins.__import__

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "resource":
            raise ModuleNotFoundError("No module named 'resource'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.delitem(sys.modules, "resource", raising=False)
    monkeypatch.setattr(builtins, "__import__", blocked)
    assert _process_rss_kb() is None


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
    _bind_scene(store, rgb)
    engine.submit_visual(media_id="m1", run_id="r1")
    assert started.wait(2)
    try:
        try:
            engine.submit_visual(media_id="m1", run_id="r1")
            raised = False
        except JobBusy:
            raised = True
        assert raised
        assert engine.ingest_busy is False
    finally:
        release.set()


def test_protocol_sheet_is_blank():
    from semblon.visual.protocol import session_header

    rows = sheet(["a.jpg", "b.jpg"])
    assert len(rows) == 2
    row = rows[0]
    assert row["image"] == "a.jpg"
    assert row["proposed"] is None and row["highlight_matched"] is None
    assert row["failure_class"] == "" and row["scene"] == ""
    assert row["label_correct"] is None and row["analysis_time"] is None
    assert set(FAILURE_CLASSES) == {"DISCOVERY", "LATTICE", "SLICE", "RENDERER", "NAMING"}
    header = session_header()
    assert header["home_launched"] is None and header["windows_version"] is None


def test_stored_rows_rebuild_the_owner_map():
    rgb, person, hood, hand = _scene()
    def score(region, noun, parent=None):
        x, _y, w, h = region.bbox
        if noun == "hood" and h < 20 and x < 70:
            return 0.92
        if noun == "hand" and x >= 68:
            return 0.9
        if noun == "person" and w > 30 and h > 30:
            return 0.85
        return 0.04

    analysis = analyse(
        rgb,
        config=VisualConfig(min_area_frac=0.001, display_min_px=1, name_margin=0.05),
        user_masks=[person, hood, hand],
        nouns=["hood", "hand", "person", "fabric"],
        score_fn=score,
        allow_local_naming=False,
    )
    items = [
        {"region_id": region.region_id, "kind": region.kind, "rows": analysis.rows[region.region_id]}
        for region in analysis.regions
    ]
    rebuilt = owner_from_stored(analysis.height, analysis.width, items)
    assert np.array_equal(rebuilt, analysis.owner)
    piece = analysis.region(int(rebuilt[35, 55]))
    assert piece is not None and piece.label == "hood" and piece.kind == "part"
    hand_piece = analysis.region(int(rebuilt[55, 80]))
    assert hand_piece is not None and hand_piece.label == "hand"
    assert hand_piece.label != "fabric"


def test_open_photo_gate_and_reloaded_pointer(tmp_path):
    assert should_submit_visual(busy=True, items=[], media_id="m1", run_id="r1") is False
    assert should_submit_visual(busy=False, items=[], media_id="m1", run_id=None) is False
    assert should_submit_visual(busy=False, items=[], media_id="m1", run_id="r1") is True
    stored = [{"media_id": "m1", "provider": "visual.region"}]
    assert should_submit_visual(busy=False, items=stored, media_id="m1", run_id="r1") is False

    rgb, person, hood, _hand = _scene()
    store = tmp_path / "s.sqlite"
    _seed(store)
    engine = JobEngine(store)
    done = threading.Event()
    box: dict = {}

    def score(region, noun, parent=None):
        return 0.05

    _bind_scene(store, rgb)
    engine.submit_visual(
        media_id="m1",
        run_id="r1",
        score_fn=score,
        view_w=rgb.shape[1],
        view_h=rgb.shape[0],
        on_done=lambda result: (box.__setitem__("result", result), done.set()),
    )
    assert done.wait(8)
    assert box["result"].status == "completed"
    assert box["result"].rec["persons"] == 0
    loaded = load_hover_rows(store, media_id="m1", run_id="r1")
    assert loaded
    owner = owner_from_stored(rgb.shape[0], rgb.shape[1], loaded)
    ys, xs = np.nonzero(owner)
    assert len(ys)
    region_id = int(owner[int(ys[0]), int(xs[0])])
    assert any(int(row["region_id"]) == region_id for row in loaded)
    native = canvas_point_to_native(55, 35, ox=0, oy=0, scale=1, width=rgb.shape[1], height=rgb.shape[0])
    assert native == (55, 35)
    assert canvas_point_to_native(-1, 0, ox=10, oy=0, scale=1, width=20, height=20) is None
    again = load_hover_rows(store, media_id="m1", run_id="r1")
    assert len(again) == len(loaded)
    assert should_submit_visual(
        busy=False,
        items=[{"media_id": "m1", "provider": "visual.region"}],
        media_id="m1",
        run_id="r1",
    ) is False


def test_weak_similarity_abstains():
    assert gated_similarity(0.21, 0.20) == 0.0
    assert gated_similarity(0.40, 0.20) == 0.40
    region = VisualRegion(region_id=1, bbox=(0, 0, 4, 4), area=16, kind="thing")

    def weak(_region, noun, parent=None, context=None):
        return gated_similarity(0.22 if noun == "water" else 0.1, 0.21)

    bind_label(region, ["water", "grass"], weak, parent=None, config=VisualConfig())
    assert region.label is None


def test_sam2_failure_is_not_ready(tmp_path, monkeypatch):
    import sys
    import types

    clear_sam2_runtime()
    weight = tmp_path / "sam2.1_hiera_tiny.pt"
    weight.write_bytes(b"not-a-checkpoint")
    monkeypatch.setenv("SEMBLON_SAM2_WEIGHTS", str(weight))
    try:
        monkeypatch.setitem(sys.modules, "sam2", None)
        assert sam2_capability()["state"] == "UNAVAILABLE"
        monkeypatch.setitem(sys.modules, "sam2", types.ModuleType("sam2"))
        assert sam2_capability()["state"] == "READY"
        mark_sam2_failed("RuntimeError: bad checkpoint", str(weight))
        failed = sam2_capability()
        assert failed["state"] == "FAILED"
        assert "bad checkpoint" in failed["note"]
    finally:
        monkeypatch.delenv("SEMBLON_SAM2_WEIGHTS", raising=False)
        clear_sam2_runtime()
    assert sam2_capability()["state"] != "READY"


def test_sam2_proposed_count_is_kept_through_containment(monkeypatch):
    clear_sam2_runtime()

    def ready():
        return {"state": "READY", "note": "test", "weights": "w", "params": {"box_nms_thresh": 0.95}}

    def fake_discover(self, rgb, config):
        _h, w = rgb.shape[:2]
        person = np.zeros(rgb.shape[:2], dtype=bool)
        person[10:70, 10:70] = True
        hood = np.zeros(rgb.shape[:2], dtype=bool)
        hood[12:28, 16:50] = True
        return [
            MaskCand(person, "sam2", "amg", 0.9, 0.9, "raw"),
            MaskCand(hood, "sam2", "amg", 0.91, 0.9, "raw"),
        ], None

    monkeypatch.setattr("semblon.visual.engine.sam2_capability", ready)
    monkeypatch.setattr(Sam2AmgDiscovery, "discover", fake_discover)
    rgb, *_ = _scene()
    analysis = analyse(
        rgb,
        config=VisualConfig(min_area_frac=0.001, display_min_px=1),
        use_sam2=True,
        allow_local_naming=False,
    )
    assert analysis.diagnostics["sam2"]["proposed"] == 2
    assert analysis.diagnostics["sam2"]["kept"] == 2
    assert analysis.diagnostics["sam2"]["params"]["box_nms_thresh"] == 0.95


def test_coarse_pass_publishes_before_sam2(tmp_path, monkeypatch):
    calls = []
    real = analyse

    def wrapped(image, **kwargs):
        calls.append(kwargs.get("use_sam2"))
        return real(image, **kwargs)

    def ready():
        return {"state": "READY", "note": "test", "weights": "w", "params": {}}

    def fake_discover(self, rgb, config):
        mask = np.zeros(rgb.shape[:2], dtype=bool)
        mask[28:42, 46:72] = True
        return [MaskCand(mask, "sam2", "amg", 0.9, 0.9, "raw")], None

    monkeypatch.setattr("semblon.visual.engine.analyse", wrapped)
    monkeypatch.setattr("semblon.visual.discovery.sam2_capability", ready)
    monkeypatch.setattr(Sam2AmgDiscovery, "discover", fake_discover)
    store = tmp_path / "s.sqlite"
    _seed(store)
    engine = JobEngine(store)
    events = []
    done = threading.Event()
    box: dict = {}
    rgb, *_ = _scene()
    _bind_scene(store, rgb)
    engine.submit_visual(
        media_id="m1",
        run_id="r1",
        on_event=lambda event: events.append(event.kind),
        on_done=lambda result: (box.__setitem__("result", result), done.set()),
    )
    assert done.wait(8)
    assert box["result"].status == "completed"
    assert calls[:2] == [False, True]
    assert "partial" in events
    assert box["result"].rec["persons"] == 0
    assert engine.ingest_busy is False


def test_mask_overlay_is_empty_off_the_piece():
    png = mask_png({"1": [[0, 2]]}, width=4, height=3, scale=1, alpha=200)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    import cv2

    img = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    assert img[1, 0].tolist() == [202, 94, 40, 200]
    assert img[0, 0, 3] == 0
    assert img[1, 3, 3] == 0
