"""User-drawn regions persist as observations. They are not persons."""

from __future__ import annotations

from pathlib import Path

from semblon.store import connect, init_db
from semblon.user_region import (
    list_user_regions,
    name_user_region,
    persist_user_region,
)


def _seed(path: Path):
    conn = connect(path)
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


def test_box_survives_reconnect_and_is_not_a_person(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store)
    rec = persist_user_region(store, media_id="m1", x=10, y=10, w=40, h=20)
    assert rec["persons"] == 0
    assert rec["face_embeddings"] == 0
    assert rec["named"] is None
    assert rec["norm"]["x1"] == 10 / 200
    listed = list_user_regions(store)
    assert len(listed) == 1
    assert listed[0]["item_id"] == rec["item_id"]
    assert listed[0]["person"] is False
    assert listed[0]["entity"] is False
    named = name_user_region(store, rec["item_id"], "my old camera")
    assert named["named"] == "my old camera"
    assert named["persons"] == 0
    assert named["entity"] is False
    again = list_user_regions(store)
    assert again[0]["named"] == "my old camera"
    conn = connect(store)
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
    kinds = {row[0] for row in conn.execute("SELECT kind FROM observation_items")}
    providers = {row[0] for row in conn.execute("SELECT provider FROM observation_items")}
    conn.close()
    assert "face" not in kinds
    assert "user_box" in providers


def test_application_door_does_not_enrol(tmp_path):
    from semblon.application import Application

    store = tmp_path / "s.sqlite"
    _seed(store)
    app = Application(store)
    rec = app.remember_region("m1", 0, 0, 20, 10)
    rows = app.regions()
    assert rec["item_id"] == rows[0]["item_id"]
    labelled = app.name_region(rec["item_id"], "box")
    assert labelled["persons"] == 0
