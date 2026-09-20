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


def test_empty_state_line_names_populated_run(tmp_path):
    """Empty skip-all run must still point at faces that remain on the store."""
    from semblon.process import empty_state_line

    store = tmp_path / "s.sqlite"
    _seed(store)
    conn = sqlite3.connect(str(store))
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("r-empty", "t9", "t9b", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.commit()
    conn.close()
    line = empty_state_line(store, "r-empty")
    assert line.startswith("this run: 0 faces")
    assert "store has 5 on run r1" in line
    board = load_board(store, "r-empty")
    assert board["items"] == []
    assert board["empty_state"] == line
    assert board["counts"]["faces"] == 0
    assert board["counts"]["ok"] == 0


def test_empty_state_line_flags_held_out_ok_zero(tmp_path):
    """low_quality faces exist but never appear on the board."""
    from semblon.process import empty_state_line

    store = tmp_path / "s.sqlite"
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("rlq", "t0", "t1", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'rlq')")
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("flq", "o1", "rlq", 0, 0, 20, 20, 0.2, 20, 20, "<80", "low_quality", _vec(1.0, 0.0), "pack-a", 2),
    )
    conn.commit()
    conn.close()
    line = empty_state_line(store, "rlq")
    assert "this run: 1 faces (0 ok)" in line
    assert "store has 1 on run rlq" in line
    board = load_board(store, "rlq")
    assert board["items"] == []
    assert board["counts"]["faces"] == 1
    assert board["counts"]["ok"] == 0
    assert board["counts"]["unassigned"] == 0


def test_resolve_run_skips_empty_later_run(tmp_path):
    """FACE-005 skip-all leaves a newer run with zero faces. Review must not go blank."""
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    assert assigned
    conn = sqlite3.connect(str(store))
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("r-empty", "t9", "t9b", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.commit()
    conn.close()
    assert resolve_run_id(store, None) == "r1"
    assert resolve_run_id(store, "r-empty") == "r-empty"
    empty = load_board(store, "r-empty")
    assert empty["items"] == []
    board = load_board(store, resolve_run_id(store, None))
    assert board["items"]


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
    # Ignored clusters are hidden from the actionable board.
    assert not any(it.get("cluster_id") == cid for it in board2["items"] if it["kind"] == "cluster")
    assert board2["counts"].get("ignored_clusters", 0) >= 1


def test_face_ignore_defaults_needs_review(tmp_path):
    store = tmp_path / "s.sqlite"
    _clustered(store)
    board = load_board(store, "r1")
    item = next(it for it in board["items"] if it["kind"] == "unassigned")
    rec = apply_ignore(store, "r1", item)
    assert rec["disposition"] == "needs-review"
    board2 = load_board(store, "r1")
    assert not any(
        it["kind"] == "unassigned" and it.get("face_id") == item["face_id"]
        for it in board2["items"]
    )


def test_note_kind_on_board(tmp_path):
    from semblon.review_ui import apply_note

    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    cid = assigned["f1"]
    board = load_board(store, "r1")
    item = next(it for it in board["items"] if it.get("cluster_id") == cid)
    apply_note(store, "r1", item, "check lighting")
    board2 = load_board(store, "r1")
    assert any(d["kind"] == "note" for d in board2["decisions"])
    hit = next(it for it in board2["items"] if it.get("cluster_id") == cid)
    assert hit.get("has_note") is True


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
    assert board["counts"]["tracks"] == 0
    assert board["counts"]["untracked"] == 1
    item = board["items"][0]
    assert item["kind"] == "unassigned"
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


def test_board_renders_derived_tracks_not_media_bags(tmp_path):
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
    conn.execute("INSERT INTO observations VALUES ('ov3','mv',150,6000,'rg')")
    conn.execute("INSERT INTO observations VALUES ('os','ms',NULL,NULL,'rg')")
    # Overlapping boxes 400ms apart → one track. Isolated later face → untracked.
    for fid, oid, bbox in (
        ("fv1", "ov1", (0, 0, 20, 20)),
        ("fv2", "ov2", (1, 1, 21, 21)),
        ("fv3", "ov3", (200, 0, 220, 20)),
        ("fs1", "os", (0, 0, 20, 20)),
    ):
        x1, y1, x2, y2 = bbox
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, oid, "rg", x1, y1, x2, y2, 0.9, x2 - x1, y2 - y1, "80-119", "ok", _vec(1.0, 0.0), "pack-a", 2),
        )
    conn.commit()
    conn.close()
    board = load_board(store, "rg")
    assert board["counts"]["unassigned"] == 4
    assert board["counts"]["tracks"] == 1
    assert board["counts"]["untracked"] == 1
    track = next(it for it in board["items"] if it["kind"] == "track")
    singles = [it for it in board["items"] if it["kind"] == "unassigned"]
    assert [m["face_id"] for m in track["members"]] == ["fv1", "fv2"]
    assert {it["face_id"] for it in singles} == {"fv3", "fs1"}
    from semblon.review_ui import apply_name, item_label

    assert item_label(track).startswith("TRACK")
    named = apply_name(store, "rg", track, "Ada")
    assert named["display_name"] == "Ada"
    assert named["faces_named"] == 2
    assert named["track_id"] == track["track_id"]
    assert named["person_id"] != track["track_id"]
    from semblon.identify import identify_face

    hit = identify_face(store, "rg", "fv2")
    assert hit["decision"] == "ACCEPT"
    assert hit["person_id"] == named["person_id"]


def test_crop_png_b64_video_without_frame_id_returns_none():
    assert (
        crop_png_b64("C:/clips/a.mp4", (0, 0, 10, 10), source_type="video") is None
    )


def test_draw_faces_reselect_keeps_photo_owner_and_refs(monkeypatch):
    from semblon import review_ui

    class _TkStub:
        NW = "nw"

        class TclError(Exception):
            pass

        _default_root = type("HomeRoot", (), {"tk": "home-interpreter"})()

        class PhotoImage:
            _n = 0

            def __init__(self, *, data, master=None):
                assert data
                type(self)._n += 1
                self.name = f"pyimage{type(self)._n}"
                owner = master if master is not None else _TkStub._default_root
                self.tk = getattr(owner, "tk", None)

    class _Root:
        def __init__(self, tk_name: str):
            self.tk = tk_name

        def after(self, _ms, callback):
            callback()

    class _Canvas:
        def __init__(self, tk_name: str):
            self.tk = tk_name
            self.images = []
            self._next = 1

        def delete(self, what):
            if what == "all":
                self.images = []

        def create_rectangle(self, *_args, **_kwargs):
            out = self._next
            self._next += 1
            return out

        def create_text(self, *_args, **_kwargs):
            out = self._next
            self._next += 1
            return out

        def create_image(self, _x, _y, *, anchor, image, tags):
            assert anchor == "nw"
            assert tags
            if image.tk != self.tk:
                raise _TkStub.TclError(f'image "{image.name}" doesn\'t exist')
            self.images.append(image)
            out = self._next
            self._next += 1
            return out

    class _Listbox:
        def __init__(self):
            self._selection: tuple[int, ...] = ()

        def set_selection(self, idx: int) -> None:
            self._selection = (idx,)

        def curselection(self):
            return self._selection

    class _ImmediateThread:
        def __init__(self, *, target, daemon):
            self._target = target
            self._daemon = daemon

        def start(self):
            self._target()

    monkeypatch.setattr(review_ui, "tk", _TkStub)
    monkeypatch.setattr(review_ui.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(review_ui, "crop_png_b64", lambda *_a, **_k: "ZmFrZQ==")

    app = review_ui.ReviewApp.__new__(review_ui.ReviewApp)
    app.root = _Root("review-interpreter")
    app.canvas = _Canvas("review-interpreter")
    app._photos = []
    app._selected_faces = set()
    app._draw_gen = 0
    app._update_action_buttons = lambda: None
    app.listbox = _Listbox()
    members_a = [
        {
            "face_id": "face-a1",
            "path": "/a.jpg",
            "bbox": (0, 0, 32, 32),
            "frame_id": None,
            "source_type": "folder",
        },
        {
            "face_id": "face-a2",
            "path": "/a.jpg",
            "bbox": (1, 1, 33, 33),
            "frame_id": None,
            "source_type": "folder",
        },
    ]
    members_b = [
        {
            "face_id": "face-b1",
            "path": "/b.jpg",
            "bbox": (4, 4, 36, 36),
            "frame_id": 42,
            "source_type": "video",
        }
    ]
    app.board = {
        "items": [
            {"kind": "cluster", "members": members_a},
            {"kind": "unassigned", "members": members_b},
        ]
    }

    for idx in (0, 1, 0, 1, 0):
        app.listbox.set_selection(idx)
        app._on_select()
        expected = len(app.board["items"][idx]["members"])
        assert len(app._photos) == expected
        assert len(app.canvas.images) == expected
        assert all(photo.tk == app.canvas.tk for photo in app._photos)
        for photo in app._photos:
            assert photo in app.canvas.images


def test_create_review_window_uses_toplevel_under_parent(monkeypatch):
    from semblon import review_ui

    calls = {"tk": 0, "toplevel": 0}

    class _Root:
        def __init__(self):
            calls["tk"] += 1
            self.tk = f"interp-{calls['tk']}"

    class _Top:
        def __init__(self, parent):
            calls["toplevel"] += 1
            self.tk = parent.tk
            self.parent = parent

        def destroy(self):
            return None

    class _TkStub:
        Tk = _Root
        Toplevel = _Top

    monkeypatch.setattr(review_ui, "tk", _TkStub)

    root, own_root = review_ui._create_review_window(None)
    assert own_root is True
    assert calls["tk"] == 1
    assert calls["toplevel"] == 0

    review_win, own_child = review_ui._create_review_window(root)
    assert own_child is False
    assert review_win.tk == root.tk
    assert calls["tk"] == 1
    assert calls["toplevel"] == 1

    review_win.destroy()
    reopened, own_reopen = review_ui._create_review_window(root)
    assert own_reopen is False
    assert reopened.tk == root.tk
    assert calls["tk"] == 1
    assert calls["toplevel"] == 2
