"""User-drawn geometry stays the user-drawn geometry."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from semblon.geometry import (
    contain_rect,
    normalize_pixels,
    pixels_from_norm,
    same_norm,
    widget_to_image,
)
from semblon.observers import persist_item
from semblon.region_search import crop_bgr
from semblon.store import connect, init_db
from semblon.user_region import list_user_regions, name_user_region, persist_user_region


def test_letterbox_does_not_map_bars_into_the_image():
    # 200x100 image in a 200x200 square view: 50px bars top and bottom.
    box = contain_rect(view_w=200, view_h=200, image_w=200, image_h=100)
    assert box["y"] == 50
    assert box["h"] == 100
    # Drag only on the image band → full image.
    rect = widget_to_image(0, 50, 200, 150, view_w=200, view_h=200, image_w=200, image_h=100)
    assert rect == {"x": 0, "y": 0, "w": 200, "h": 100}
    # Drag in the top bar does not invent a center crop.
    assert widget_to_image(0, 0, 200, 40, view_w=200, view_h=200, image_w=200, image_h=100) is None


def test_stretch_mapping_is_opt_in_not_default():
    stretched = widget_to_image(
        0, 0, 100, 100, view_w=100, view_h=100, image_w=200, image_h=100, letterbox=False
    )
    contained = widget_to_image(
        0, 25, 100, 75, view_w=100, view_h=100, image_w=200, image_h=100, letterbox=True
    )
    assert stretched == {"x": 0, "y": 0, "w": 200, "h": 100}
    assert contained == {"x": 0, "y": 0, "w": 200, "h": 100}


def test_quadrant_crop_matches_selected_pixels(tmp_path):
    import cv2

    img = np.zeros((40, 40, 3), dtype=np.uint8)
    img[0:20, 0:20] = (0, 0, 255)
    img[0:20, 20:40] = (0, 255, 0)
    img[20:40, 0:20] = (255, 0, 0)
    img[20:40, 20:40] = (0, 255, 255)
    path = tmp_path / "q.jpg"
    cv2.imwrite(str(path), img)
    crop = crop_bgr(path, 20, 0, 20, 20)
    assert crop.shape[0] == 20 and crop.shape[1] == 20
    assert int(crop[:, :, 1].mean()) > 200  # green quadrant
    assert int(crop[:, :, 2].mean()) < 40


def test_unknown_selection_keeps_geometry_after_reconnect(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',200,100,0,1)")
    conn.commit()
    conn.close()
    user = persist_user_region(store, media_id="m1", x=10, y=20, w=40, h=30)
    expected = normalize_pixels(10, 20, 40, 30, 200, 100)
    assert same_norm(user["norm"], expected)
    # Detector disagreement: another item, different bbox, same observation.
    conn = connect(store)
    persist_item(
        conn,
        observation_id=user["observation_id"],
        run_id=user["run_id"],
        kind="object",
        provider="auto_detector",
        payload={"class": "hypothesis", "identity": "not facekit"},
        bbox=(1.0, 1.0, 8.0, 8.0),
        score=0.2,
    )
    conn.commit()
    conn.close()
    listed = list_user_regions(store)
    assert len(listed) == 1
    assert same_norm(listed[0]["norm"], expected)
    assert listed[0]["bbox"] == [10.0, 20.0, 50.0, 50.0]
    named = name_user_region(store, user["item_id"], "the thing")
    assert named["named"] == "the thing"
    assert named["persons"] == 0
    restored = pixels_from_norm(listed[0]["norm"], 200, 100)
    assert restored == {"x": 10, "y": 20, "w": 40, "h": 30}


def test_portrait_and_square_normalize():
    p = normalize_pixels(10, 40, 20, 80, 100, 200)
    assert p["x1"] == 0.1 and p["y1"] == 0.2
    s = normalize_pixels(25, 25, 50, 50, 100, 100)
    assert s["x1"] == 0.25 and s["x2"] == 0.75
