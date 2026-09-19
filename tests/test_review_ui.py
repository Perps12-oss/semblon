"""S8 Interactive Review slice — board + API wiring (no display required)."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import pytest

from semblon.cluster import cluster_run
from semblon.identify import identify_face
from semblon.review_ui import (
    ReviewUiError,
    apply_ignore,
    apply_merge,
    apply_name,
    apply_split,
    crop_png_b64,
    load_board,
    resolve_run_id,
)
from semblon.store import init_db


def _vec(*xs: float) -> bytes:
    return struct.pack(f"<{len(xs)}f", *xs)


def _seed(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t0", "t1", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',100,100,0,1)")
    conn.execute("INSERT INTO media VALUES ('m2','folder','/b.jpg','bbb',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',NULL,NULL,'r1')")
    faces = [
        ("f1", "o1", _vec(1.0, 0.0)),
        ("f2", "o1", _vec(0.99, 0.141)),
        ("f3", "o2", _vec(0.0, 1.0)),
        ("f4", "o2", _vec(0.141, 0.99)),
        ("f5", "o1", _vec(0.707, 0.707)),
    ]
    for fid, oid, blob in faces:
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, oid, "r1", 0, 0, 20, 20, 0.9, 20, 20, "80-119", "ok", blob, "pack-a", 2),
        )
    conn.commit()
    conn.close()


def _clustered(store: Path) -> dict[str, str]:
    _seed(store)
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = sqlite3.connect(str(store))
    rows = conn.execute(
        "SELECT face_id, cluster_id FROM faces WHERE cluster_id IS NOT NULL"
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def test_resolve_run_defaults_to_latest(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store)
    assert resolve_run_id(store, None) == "r1"
    assert resolve_run_id(store, "r1") == "r1"
    with pytest.raises(ReviewUiError, match="unknown run"):
        resolve_run_id(store, "nope")


def test_strong_cluster_is_unnamed_until_name(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    board = load_board(store, "r1", strong_min_intra=0.0)
    # With strong_min_intra=0, every clustered item with min_intra is STRONG band.
    clusters = [it for it in board["items"] if it["kind"] == "cluster"]
    assert clusters
    for it in clusters:
        assert it["named"] is False
        assert it["person_names"] == []
    # Name one cluster -> person exists; others stay unnamed.
    cid = assigned["f1"]
    item = next(it for it in clusters if it["cluster_id"] == cid)
    rec = apply_name(store, "r1", item, "Alice")
    board2 = load_board(store, "r1", strong_min_intra=0.0)
    named = next(it for it in board2["items"] if it.get("cluster_id") == cid)
    assert named["named"] is True
    assert "Alice" in named["person_names"]
    assert rec["person_id"]
    # cluster id is never the person id
    assert cid != rec["person_id"]


def test_name_then_identify_returns_same_person(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    cid = assigned["f1"]
    board = load_board(store, "r1")
    item = next(it for it in board["items"] if it.get("cluster_id") == cid)
    named = apply_name(store, "r1", item, "Alice")
    # Gallery has f1+f2; identify f1 against remaining exemplars.
    hit = identify_face(store, "r1", "f1")
    assert hit["decision"] == "ACCEPT"
    assert hit["person_id"] == named["person_id"]
    assert hit["display_name"] == "Alice"


def test_merge_persists_after_reload(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    assert c1 != c2
    merge = apply_merge(store, "r1", [c1, c2])
    assert merge["survivor"] == c1
    board = load_board(store, "r1")
    ids = {it["cluster_id"] for it in board["items"] if it["kind"] == "cluster"}
    assert c1 in ids
    assert c2 not in ids
    kinds = {d["kind"] for d in board["decisions"]}
    assert "merge" in kinds


def test_split_persists_after_reload(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    cid = assigned["f1"]
    # f1 and f2 share a cluster under eps=0.15
    split = apply_split(store, "r1", cid, ["f2"])
    board = load_board(store, "r1")
    ids = {it["cluster_id"] for it in board["items"] if it["kind"] == "cluster"}
    assert cid in ids
    assert split["new_cluster"] in ids
    kinds = {d["kind"] for d in board["decisions"]}
    assert "split" in kinds
    conn = sqlite3.connect(str(store))
    f2 = conn.execute("SELECT cluster_id, person_id FROM faces WHERE face_id='f2'").fetchone()
    conn.close()
    assert f2[0] == split["new_cluster"]
    assert f2[1] is None


def test_ignore_persists_after_reload(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    cid = assigned["f3"]
    board = load_board(store, "r1")
    item = next(it for it in board["items"] if it.get("cluster_id") == cid)
    rec = apply_ignore(store, "r1", item)
    assert rec["cluster_id"] == cid
    board2 = load_board(store, "r1")
    kinds = {d["kind"] for d in board2["decisions"]}
    assert "reject" in kinds
    # Cluster remains listable; ignore is a decision, not auto-enrol.
    assert any(it.get("cluster_id") == cid for it in board2["items"] if it["kind"] == "cluster")


def test_cli_review_ui_help_lists_command():
    from semblon.cli import main
    import io
    from unittest.mock import patch

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        with pytest.raises(SystemExit) as ei:
            main(["--help"])
    assert ei.value.code == 0
    assert "review-ui" in buf.getvalue()


def test_board_carries_video_observation_provenance(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("rv", "t0", "t1", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute(
        "INSERT INTO media VALUES ('mv','video','C:/clips/a.mp4','vvv',1920,1080,0,1)"
    )
    conn.execute("INSERT INTO observations VALUES ('ov','mv',1300,64973,'rv')")
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "fv",
            "ov",
            "rv",
            10,
            20,
            110,
            120,
            0.9,
            100,
            100,
            "80-119",
            "ok",
            _vec(1.0, 0.0),
            "pack-a",
            2,
        ),
    )
    conn.commit()
    conn.close()

    board = load_board(store, "rv")
    assert board["counts"]["unassigned"] == 1
    assert board["counts"]["unassigned_media"] == 1
    item = board["items"][0]
    assert item["kind"] == "unassigned_media"
    assert item["face_count"] == 1
    m = item["members"][0]
    assert m["face_id"] == "fv"
    assert m["observation_id"] == "ov"
    assert m["source_type"] == "video"
    assert m["path"] == "C:/clips/a.mp4"
    assert m["frame_id"] == 1300
    assert m["t_ms"] == 64973
    assert m["bbox"] == (10, 20, 110, 120)
    assert m["cluster_id"] is None


def test_crop_png_b64_video_seeks_instead_of_imread():
    from unittest.mock import patch

    import numpy as np

    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[20:120, 10:110] = 200
    with patch("semblon.temporal.read_bgr", return_value=frame) as rb:
        b64 = crop_png_b64(
            "C:/clips/a.mp4",
            (10, 20, 110, 120),
            frame_id=1300,
            source_type="video",
        )
    assert b64 is not None
    rb.assert_called_once_with("C:/clips/a.mp4", 1300)


def test_board_groups_video_unassigned_by_media(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("rg", "t0", "t1", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('mv','video','C:/clips/a.mp4','vvv',1920,1080,0,1)")
    conn.execute("INSERT INTO media VALUES ('ms','folder','C:/stills/a.jpg','sss',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('ov1','mv',10,400,'rg')")
    conn.execute("INSERT INTO observations VALUES ('ov2','mv',20,800,'rg')")
    conn.execute("INSERT INTO observations VALUES ('os','ms',NULL,NULL,'rg')")
    for fid, oid in (("fv1", "ov1"), ("fv2", "ov2"), ("fs1", "os")):
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, oid, "rg", 0, 0, 20, 20, 0.9, 20, 20, "80-119", "ok", _vec(1.0, 0.0), "pack-a", 2),
        )
    conn.commit()
    conn.close()
    board = load_board(store, "rg")
    assert board["counts"]["unassigned"] == 3
    assert board["counts"]["unassigned_media"] == 1
    video = next(it for it in board["items"] if it["kind"] == "unassigned_media")
    still = next(it for it in board["items"] if it["kind"] == "unassigned")
    assert [m["face_id"] for m in video["members"]] == ["fv1", "fv2"]
    assert still["face_id"] == "fs1"
    from semblon.review_ui import apply_name, item_label

    assert "VIDEO" in item_label(video)
    with pytest.raises(ReviewUiError, match="not a person"):
        apply_name(store, "rg", video, "Nope")
    named = apply_name(store, "rg", {**video, "face_id": "fv1"}, "Ada")
    assert named["display_name"] == "Ada"


def test_crop_png_b64_video_without_frame_id_returns_none():
    assert (
        crop_png_b64("C:/clips/a.mp4", (0, 0, 10, 10), source_type="video") is None
    )
