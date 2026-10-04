"""Release → remember_and_find_region uses the same canonical pixels."""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np

from semblon.application import Application
from semblon.geometry import normalize_pixels, same_norm
from semblon.lens_home import open_region_select
from semblon.lens_release import remember_selection
from semblon.observers import observe_bgr, persist_item
from semblon.store import connect, init_db
from semblon.user_region import list_user_regions


def _seed(store: Path, photo: Path):
    import cv2

    dark = np.zeros((40, 40, 3), dtype=np.uint8)
    light = np.full((40, 40, 3), 255, dtype=np.uint8)
    cv2.imwrite(str(photo), dark)
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute(
        "INSERT INTO media VALUES ('m1','folder',?, 'aaa',40,40,0,1)",
        (str(photo),),
    )
    conn.execute("INSERT INTO media VALUES ('m2','folder','/b.jpg','bbb',40,40,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',NULL,NULL,'r1')")
    observe_bgr(conn, observation_id="o1", run_id="r1", img=dark, observers=("color",))
    observe_bgr(conn, observation_id="o2", run_id="r1", img=light, observers=("color",))
    conn.commit()
    conn.close()


def test_release_passes_canonical_bbox_through_application(tmp_path):
    store = tmp_path / "s.sqlite"
    photo = tmp_path / "a.jpg"
    _seed(store, photo)
    app = Application(store)
    persons_before = connect(store).execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    faces_before = connect(store).execute(
        "SELECT COUNT(*) FROM embeddings WHERE modality='face'"
    ).fetchone()[0]
    rec = remember_selection(
        store,
        media_id="m1",
        image_path=photo,
        x=2,
        y=4,
        w=10,
        h=12,
        app=app,
    )
    assert rec["rect"] == {"x": 2, "y": 4, "w": 10, "h": 12}
    assert rec["query_pixels"] == {"x": 2, "y": 4, "w": 10, "h": 12}
    assert rec["wrote_embedding"] is False
    assert rec["persons"] == 0
    assert rec["box_kept"] is True
    saved = rec["region"]
    expected = normalize_pixels(2, 4, 10, 12, 40, 40)
    assert same_norm(saved["norm"], expected)
    listed = list_user_regions(store)
    assert listed[0]["bbox"] == [2.0, 4.0, 12.0, 16.0]
    text = "\n".join(rec["lines"])
    assert "Unknown selection" in text
    assert "embedding" not in text.lower()
    assert "pack_id" not in text
    conn = connect(store)
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == persons_before
    assert conn.execute(
        "SELECT COUNT(*) FROM embeddings WHERE modality='face'"
    ).fetchone()[0] == faces_before
    conn.close()


def test_detector_box_does_not_mutate_user_box(tmp_path):
    store = tmp_path / "s.sqlite"
    photo = tmp_path / "a.jpg"
    _seed(store, photo)
    rec = remember_selection(
        store, media_id="m1", image_path=photo, x=8, y=8, w=8, h=8
    )
    conn = connect(store)
    persist_item(
        conn,
        observation_id=rec["region"]["observation_id"],
        run_id=rec["region"]["run_id"],
        kind="object",
        provider="auto_detector",
        payload={"class": "hypothesis", "identity": "not facekit"},
        bbox=(0.0, 0.0, 3.0, 3.0),
        score=0.1,
    )
    conn.commit()
    conn.close()
    listed = list_user_regions(store)
    assert listed[0]["bbox"] == [8.0, 8.0, 16.0, 16.0]


def test_home_release_path_calls_remember_and_find():
    import semblon.home_ui as home_ui

    method = inspect.getsource(home_ui.HomeApp._open_region_select)
    assert "open_region_select(self)" in method
    src = inspect.getsource(open_region_select)
    assert "remember_selection" in src
    assert "on_rect" in src
    assert "_refresh_lens_workspace()" not in src.split("def done")[1]
    sel = inspect.getsource(__import__("semblon.selection", fromlist=["mount_region_select"]).mount_region_select)
    assert "on_rect" in sel
    assert "person_id" not in sel


def test_empty_similar_copy_is_truthful(tmp_path):
    store = tmp_path / "empty.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/missing.jpg','aaa',20,20,0,1)")
    conn.commit()
    conn.close()
    rec = remember_selection(
        store, media_id="m1", image_path=tmp_path / "nope.jpg", x=1, y=1, w=4, h=4
    )
    text = "\n".join(rec["lines"])
    assert (
        "No similar images found yet." in text
        or "Similar search" in text
        or "could not read" in text.lower()
        or "needs photos" in text
    )
    assert rec["region"]["item_id"]
