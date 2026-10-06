"""Query-time region search uses existing appearance rows. No sibling vectors."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from semblon.observers import observe_bgr
from semblon.region_search import remember_and_find, search_vector
from semblon.observers import APPEARANCE_DIM, APPEARANCE_PACK, color_histogram
from semblon.store import connect, init_db


def _seed(path: Path):
    conn = connect(path)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',16,16,0,1)")
    conn.execute("INSERT INTO media VALUES ('m2','folder','/b.jpg','bbb',16,16,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',NULL,NULL,'r1')")
    dark = np.zeros((16, 16, 3), dtype=np.uint8)
    light = np.full((16, 16, 3), 255, dtype=np.uint8)
    observe_bgr(conn, observation_id="o1", run_id="r1", img=dark, observers=("color",))
    observe_bgr(conn, observation_id="o2", run_id="r1", img=light, observers=("color",))
    conn.commit()
    conn.close()
    return dark, light


def test_crop_follows_display_orientation_and_plain_files(tmp_path):
    cv2 = __import__("cv2")
    from PIL import Image, ImageOps

    from semblon.region_search import crop_bgr

    plain = tmp_path / "plain.png"
    raw = np.zeros((20, 40, 3), dtype=np.uint8)
    raw[:, :20] = (0, 0, 255)
    raw[:, 20:] = (255, 0, 0)
    cv2.imwrite(str(plain), raw)
    plain_crop = crop_bgr(plain, 0, 0, 10, 10)
    assert plain_crop.shape == (10, 10, 3)
    assert int(plain_crop[0, 0, 2]) > 200

    rotated = tmp_path / "rotated.jpg"
    rgb = raw[:, :, ::-1]
    image = Image.fromarray(rgb, mode="RGB")
    exif = image.getexif()
    exif[274] = 6
    image.save(rotated, exif=exif.tobytes())
    opened = Image.open(rotated)
    transposed = ImageOps.exif_transpose(opened)
    assert transposed.size == (20, 40)
    displayed = np.asarray(transposed.convert("RGB"))[:, :, ::-1]
    crop = crop_bgr(rotated, 0, 0, 8, 8)
    assert crop.shape == displayed[0:8, 0:8].shape
    assert np.array_equal(crop, displayed[0:8, 0:8])
    assert opened.size == (40, 20)
    assert displayed.shape[:2] == (40, 20)


def test_query_time_search_does_not_write_embeddings(tmp_path):
    store = tmp_path / "s.sqlite"
    dark, light = _seed(store)
    photo = tmp_path / "a.jpg"
    import cv2

    cv2.imwrite(str(photo), dark)
    before = connect(store).execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    rec = remember_and_find(
        store,
        media_id="m1",
        image_path=photo,
        x=0,
        y=0,
        w=8,
        h=8,
    )
    conn = connect(store)
    after = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    providers = [r[0] for r in conn.execute("SELECT provider FROM observation_items").fetchall()]
    persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    conn.close()
    assert after == before
    assert rec["wrote_embedding"] is False
    assert rec["persons"] == 0
    assert "user_box" in providers
    assert rec["similar"]["modality"] == "appearance"
    assert rec["similar"]["pack_id"] == APPEARANCE_PACK
    assert rec["similar"]["status"] in {"SUCCESS", "NO_RESULT"}
    assert persons == 0


def test_same_space_firewall_skips_other_packs(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store)
    blob = color_histogram(np.zeros((8, 8, 3), dtype=np.uint8))
    rec = search_vector(
        store,
        blob=blob,
        modality="appearance",
        pack_id="appearance/other@9",
        dim=APPEARANCE_DIM,
    )
    assert rec["status"] == "UNAVAILABLE"
    assert rec["error_id"] == "region.NO_LIBRARY_SPACE"
