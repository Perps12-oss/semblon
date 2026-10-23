"""Ship-audit regressions. No InsightFace download and no identity retune."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.cluster import cluster_run
from semblon.engine import ModelPackError, accept_local_face_pack, assert_face_pack_ready
from semblon.erasure import delete_person, wipe_library
from semblon.logging_setup import configure_logging, redact
from semblon.review import note_subject
from semblon.store import apply_migrations, connect, connect_readonly, delete_observation_tree, init_db, restore_store
from semblon.temporal import VideoError, iter_sampled_frames, open_video, read_bgr
from tests.test_cluster import _seed


def _decision(conn, *, kind: str, face_id: str | None, cluster_id: str | None) -> None:
    conn.execute(
        """INSERT INTO decisions(decision_id, kind, face_id, person_id, cluster_id, pack_id,
           score_top1, score_top2, margin, policy_json, run_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            f"d-{kind}-{face_id or cluster_id}",
            kind,
            face_id,
            None,
            cluster_id,
            "pack-a",
            None,
            None,
            None,
            "{}",
            "r1",
            "t",
        ),
    )


def test_identify_decision_does_not_split_the_cluster(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = connect(store)
    cid = conn.execute("SELECT cluster_id FROM faces WHERE face_id='f1'").fetchone()[0]
    _decision(conn, kind="identify", face_id="f1", cluster_id=cid)
    _decision(conn, kind="note", face_id="f2", cluster_id=cid)
    conn.commit()
    conn.close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = connect(store)
    try:
        ids = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT face_id, cluster_id FROM faces WHERE face_id IN ('f1','f2')"
            )
        }
        assert ids["f1"] is not None and ids["f1"] == ids["f2"]
        n = conn.execute("SELECT COUNT(*) FROM clusters WHERE run_id='r1'").fetchone()[0]
        assert n == 2
    finally:
        conn.close()


def test_name_decision_still_locks_the_cluster(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = connect(store)
    cid = conn.execute("SELECT cluster_id FROM faces WHERE face_id='f1'").fetchone()[0]
    _decision(conn, kind="name", face_id="f1", cluster_id=cid)
    conn.commit()
    conn.close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = connect(store)
    try:
        assert conn.execute("SELECT cluster_id FROM faces WHERE face_id='f1'").fetchone()[0] == cid
    finally:
        conn.close()


def test_migration_4_rolls_back_and_resumes(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r1','t','0','pack-a',2,'l2','{}','{}','x64','native')"""
    )
    conn.execute(
        """INSERT INTO decisions(decision_id, kind, face_id, person_id, cluster_id, pack_id,
           policy_json, run_id, created_at)
           VALUES ('d1','note',NULL,NULL,NULL,'pack-a','{}','r1','t')"""
    )
    conn.execute("UPDATE schema_meta SET value='3' WHERE key='schema_version'")
    conn.execute("DELETE FROM schema_migrations WHERE version=4")
    conn.commit()
    with pytest.raises(RuntimeError, match="interrupted"):
        apply_migrations(conn, fail_after="drop")
    left = conn.execute("SELECT decision_id FROM decisions").fetchone()[0]
    assert left == "d1"
    assert not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='decisions_new'"
    ).fetchone()
    conn.close()

    conn = connect(store)
    init_db(conn)
    previous = conn.isolation_level
    conn.isolation_level = None
    conn.execute(
        """CREATE TABLE decisions_kept AS SELECT * FROM decisions"""
    )
    conn.execute("ALTER TABLE decisions RENAME TO decisions_new")
    conn.execute("DROP TABLE decisions_kept")
    conn.execute("UPDATE schema_meta SET value='3' WHERE key='schema_version'")
    conn.isolation_level = previous
    conn.close()

    conn = connect(store)
    init_db(conn)
    try:
        assert conn.execute("SELECT decision_id FROM decisions").fetchone()[0] == "d1"
        assert conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0] == "4"
        assert not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='decisions_new'"
        ).fetchone()
    finally:
        conn.close()


def test_restore_keeps_dest_when_copy_fails(tmp_path):
    src = tmp_path / "src.sqlite"
    dest = tmp_path / "dest.sqlite"
    conn = connect(src)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r1','t','0','p',2,'l2','{}','{}','x64','native')"""
    )
    conn.commit()
    conn.close()
    restore_store(src, dest)
    dest.write_bytes(dest.read_bytes())  # touch
    before = dest.read_bytes()

    def _boom(src_path, dest_path):
        raise sqlite3.OperationalError("backup failed")

    with patch("semblon.store._backup_into", _boom):
        with pytest.raises(sqlite3.OperationalError):
            restore_store(src, dest, force=True)
    assert dest.read_bytes() == before


def test_moved_path_updates_and_live_copy_does_not(tmp_path):
    from semblon.ingest import _remember_path

    store = tmp_path / "s.sqlite"
    folder = tmp_path / "photos"
    folder.mkdir()
    src = folder / "a.jpg"
    src.write_bytes(b"same-bytes")
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(src), "abc", 1, 1, 0, 1),
    )
    conn.commit()
    moved = folder / "b.jpg"
    src.replace(moved)
    assert _remember_path(conn, "m1", moved, 2, 9) is True
    assert conn.execute("SELECT path FROM media WHERE media_id='m1'").fetchone()[0] == str(moved)
    copy = folder / "c.jpg"
    copy.write_bytes(b"same-bytes")
    assert _remember_path(conn, "m1", copy, 3, 9) is False
    assert conn.execute("SELECT path FROM media WHERE media_id='m1'").fetchone()[0] == str(moved)
    conn.close()


def test_zero_frame_count_reads_until_a_frame(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"not-a-real-container")
    frame = np.zeros((4, 4, 3), dtype=np.uint8)

    class _Cap:
        def __init__(self):
            self.reads = 0

        def isOpened(self):
            return True

        def get(self, prop):
            import cv2

            if prop == cv2.CAP_PROP_FRAME_COUNT:
                return 0
            if prop == cv2.CAP_PROP_FPS:
                return 1
            return 0

        def read(self):
            self.reads += 1
            if self.reads == 1:
                return True, frame
            return False, None

        def grab(self):
            return False

        def release(self):
            return None

    with patch("semblon.temporal.cv2.VideoCapture", return_value=_Cap()):
        frames = list(iter_sampled_frames(path, 1.0))
    assert len(frames) == 1
    assert frames[0][0] == 0


def test_zero_frames_is_an_error(tmp_path):
    path = tmp_path / "empty.mp4"
    path.write_bytes(b"x")

    class _Cap:
        def isOpened(self):
            return True

        def get(self, _prop):
            return 0

        def read(self):
            return False, None

        def grab(self):
            return False

        def release(self):
            return None

    with patch("semblon.temporal.cv2.VideoCapture", return_value=_Cap()):
        with pytest.raises(VideoError):
            list(iter_sampled_frames(path, 1.0))


def test_video_thumb_does_not_seek_by_frame_number(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")
    seen = {"set": False}

    class _Cap:
        def isOpened(self):
            return True

        def set(self, *_a):
            seen["set"] = True
            return True

        def grab(self):
            return True

        def read(self):
            return True, np.zeros((2, 2, 3), np.uint8)

        def release(self):
            return None

    with patch("semblon.temporal.cv2.VideoCapture", return_value=_Cap()):
        img = read_bgr(path, 2)
    assert img is not None
    assert seen["set"] is False


def test_windows_video_open_tries_extended_path(tmp_path):
    """The open loop must try the extended path without flipping os.name.

    Patching os.name to ``nt`` on Linux makes pathlib.Path() construct
    WindowsPath and raise NotImplementedError before VideoCapture runs.
    The prefix itself is covered by test_extended_win_prefix_drive_unc_and_passthrough.
    """
    path = tmp_path / "José.mp4"
    path.write_bytes(b"x")
    calls: list[str] = []
    extended = "\\\\?\\C:\\Users\\José\\clip.mp4"

    class _Cap:
        def __init__(self, name):
            self.name = name

        def isOpened(self):
            return str(self.name).startswith("\\\\?\\")

        def release(self):
            return None

    def _open(name):
        calls.append(str(name))
        return _Cap(name)

    with (
        patch("semblon.temporal._extended_win_path", return_value=extended),
        patch("semblon.temporal.cv2.VideoCapture", side_effect=_open),
    ):
        cap = open_video(path)
    assert cap.isOpened()
    assert calls[0] == str(path)
    assert extended in calls
    cap.release()


def test_extended_win_prefix_drive_unc_and_passthrough():
    from semblon.temporal import _extended_prefix, _extended_win_path

    assert _extended_prefix("C:\\Users\\José\\clip.mp4") == "\\\\?\\C:\\Users\\José\\clip.mp4"
    assert _extended_prefix("\\\\server\\share\\José.mp4") == "\\\\?\\UNC\\server\\share\\José.mp4"
    already = "\\\\?\\C:\\already.mp4"
    assert _extended_prefix(already) == already
    if os.name != "nt":
        assert _extended_win_path(Path("José.mp4")) is None


def test_readonly_open_keeps_hash_and_percent_in_the_path(tmp_path):
    folder = tmp_path / "Photos #2 %2F..%2F"
    folder.mkdir()
    store = folder / "store.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r-ro','t','0','p',2,'l2','{}','{}','x64','native')"""
    )
    conn.commit()
    conn.close()
    ro = connect_readonly(store)
    try:
        assert ro.execute("SELECT run_id FROM runs").fetchone()["run_id"] == "r-ro"
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("CREATE TABLE leaked(n INTEGER)")
    finally:
        ro.close()
    assert not (tmp_path / "leaked").exists()
    assert list(folder.glob("*.sqlite")) == [store]


def test_live_part_box_uses_detector_corners(monkeypatch):
    from semblon.region_parts import _crop_parts

    monkeypatch.setattr("semblon.object_pack.probe_nanodet_status", lambda: (True, "ready"))
    monkeypatch.setattr(
        "semblon.object_nanodet.detect_objects",
        lambda _crop: [{"label": "cup", "bbox": (10, 20, 40, 60)}],
    )
    parts = _crop_parts(object(), 100, 200)
    assert parts == [{"label": "cup", "kind": "object", "box": [110, 220, 30, 40]}]


def test_observation_delete_removes_items(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r1','t','0','p',2,'l2','{}','{}','x64','native')"""
    )
    conn.execute("INSERT INTO media VALUES ('m1','video','/v.mp4','h',1,1,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',0,0,'r1')")
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider)
           VALUES ('i1','o1','r1','object','visual.region')"""
    )
    delete_observation_tree(conn, "o1")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM observation_items").fetchone()[0] == 0
    conn.close()


def test_delete_person_removes_templates_and_wipe_is_not_reset(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    conn.execute(
        "INSERT INTO persons(person_id, display_name, status) VALUES ('p1','Ada','active')"
    )
    conn.execute("UPDATE faces SET person_id='p1' WHERE face_id='f1'")
    blob = np.zeros(2, np.float32).tobytes()
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider, face_id)
           VALUES ('i1','o1','r1','face','facekit','f1')"""
    )
    conn.execute(
        """INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
           VALUES ('e1','i1','face','pack-a',2,?)""",
        (blob,),
    )
    conn.execute(
        """INSERT INTO decisions(decision_id, kind, face_id, person_id, cluster_id, pack_id,
           policy_json, run_id, created_at)
           VALUES ('d1','name','f1','p1',NULL,'pack-a','{}','r1','t')"""
    )
    conn.commit()
    conn.close()
    rec = delete_person(store, "p1")
    assert rec["faces_deleted"] == 1
    conn = connect(store)
    try:
        assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM faces WHERE face_id='f1'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 2
    finally:
        conn.close()
    from semblon.app_reset import reset_app_to_defaults

    reset_app_to_defaults(store)
    conn = connect(store)
    try:
        assert conn.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 2
    finally:
        conn.close()
    wiped = wipe_library(store)
    assert wiped["files_deleted"] is False
    conn = connect(store)
    try:
        assert conn.execute("SELECT COUNT(*) FROM media").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0] == 0
    finally:
        conn.close()


def test_duplicate_scan_rehashes_and_sees_other_folder(tmp_path):
    from semblon.duplicates import find_exact_duplicate_groups

    store = tmp_path / "s.sqlite"
    original = tmp_path / "photos"
    original.mkdir()
    other = tmp_path / "copies"
    other.mkdir()
    a = original / "a.jpg"
    a.write_bytes(b"same-bytes")
    b = other / "b.jpg"
    b.write_bytes(b"same-bytes")
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r1','t','0','p',2,'l2',?,'{}','x64','native')""",
        (json.dumps({"folder": str(other)}),),
    )
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(a), "stale-hash", 1, 1, 0, 1),
    )
    conn.commit()
    conn.close()
    result = find_exact_duplicate_groups(store)
    assert result["status"] == "SUCCESS"
    names = {Path(member["path"]).name for member in result["groups"][0]["members"]}
    assert names == {"a.jpg", "b.jpg"}
    assert result["groups"][0]["content_hash"] != "stale-hash"


def test_face_pack_refuses_download(tmp_path):
    with pytest.raises(ModelPackError, match="does not download|YuNet ONNX missing|missing"):
        assert_face_pack_ready(tmp_path)
    home = tmp_path / "yunet_sface"
    home.mkdir()
    (home / "face_detection_yunet_2023mar.onnx").write_bytes(b"not-a-real-yunet")
    (home / "face_recognition_sface_2021dec.onnx").write_bytes(b"not-a-real-sface")
    with pytest.raises(ModelPackError, match="pin"):
        assert_face_pack_ready(home)
    rec = accept_local_face_pack(home)
    assert rec["opt_in"] is True
    assert rec.get("engine") == "yunet_sface"
    pinned = assert_face_pack_ready(home)
    assert "face_recognition_sface_2021dec.onnx" in pinned
    (home / "face_recognition_sface_2021dec.onnx").write_bytes(b"tampered")
    with pytest.raises(ModelPackError, match="hashes"):
        assert_face_pack_ready(home)


def test_log_redacts_home_and_names(tmp_path, monkeypatch):
    import sys

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    previous = sys.excepthook
    try:
        path = configure_logging(tmp_path)
        assert path is not None
        text = redact(str(Path.home() / "secret") + " display_name='Ada'")
        assert "Ada" not in text
        assert str(Path.home()) not in text
    finally:
        sys.excepthook = previous


def test_live_retention_chunks_past_the_variable_limit(tmp_path):
    from semblon.live import _apply_retention

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES ('r1','t','0','p',2,'l2','{}','{}','x64','native')"""
    )
    conn.execute("INSERT INTO media VALUES ('m1','live','live', 'h', 1, 1, 0, 1)")
    conn.executemany(
        "INSERT INTO observations VALUES (?,?,?,?,?)",
        [(f"o{i}", "m1", i, i, "r1") for i in range(600)],
    )
    conn.commit()
    deleted = _apply_retention(conn, run_id="r1", media_id="m1", keep_after_t_ms=10_000)
    conn.commit()
    assert deleted == 600
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
    conn.close()


def test_job_shutdown_joins(tmp_path):
    import threading
    import time

    from semblon.jobs import JobEngine

    engine = JobEngine(tmp_path / "s.sqlite")
    started = threading.Event()

    def _run():
        started.set()
        time.sleep(0.05)

    thread = threading.Thread(target=_run, daemon=False)
    engine._thread = thread
    thread.start()
    started.wait(1)
    engine.shutdown(timeout=2)
    assert thread.is_alive() is False


def test_reused_run_reports_existing_cluster_counts(tmp_path):
    from semblon.process import process_folder

    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    folder = tmp_path / "more"
    folder.mkdir()

    def _ingest(*_args, **_kwargs):
        return {
            "run_id": "empty",
            "faces": 0,
            "files": 0,
            "new_media": 0,
            "ok": 0,
            "skipped_seen": 1,
        }

    with patch("semblon.process.ingest", side_effect=_ingest):
        rec = process_folder(folder, store=store)
    assert rec["run_id"] == "r1"
    assert rec["cluster"]["clusters"] == 2
    assert rec["cluster"]["clustered"] == 4


def test_replaced_bytes_do_not_keep_the_old_path(tmp_path):
    from semblon.ingest import claim_new_media

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    photo = tmp_path / "shot.jpg"
    conn.execute(
        """INSERT INTO media(media_id, source_type, path, sha256, width, height, mtime_ns, byte_size)
           VALUES ('old','folder',?,'aaa',1,1,1,3)""",
        (str(photo),),
    )
    new_id = claim_new_media(
        conn,
        source_type="folder",
        path=photo,
        digest="bbb",
        width=2,
        height=2,
        mtime_ns=2,
        byte_size=4,
    )
    conn.commit()
    try:
        old_path = conn.execute("SELECT path FROM media WHERE media_id='old'").fetchone()[0]
        new_row = conn.execute(
            "SELECT path, sha256 FROM media WHERE media_id=?",
            (new_id,),
        ).fetchone()
        assert old_path == ""
        assert new_row[0] == str(photo)
        assert new_row[1] == "bbb"
    finally:
        conn.close()


def test_delete_person_drops_centroid_of_their_cluster(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    secret = np.array([0.2, 0.9], np.float32).tobytes()
    conn.execute(
        "INSERT INTO persons(person_id, display_name, status) VALUES ('p1','Ada','active')"
    )
    conn.execute(
        """INSERT INTO clusters(cluster_id, run_id, strategy, face_count, centroid, min_intra, status)
           VALUES ('c-secret','r1','t',1,?,0.1,'auto')""",
        (secret,),
    )
    conn.execute(
        "UPDATE faces SET person_id='p1', cluster_id='c-secret' WHERE face_id='f1'"
    )
    conn.commit()
    conn.close()
    delete_person(store, "p1")
    conn = connect(store)
    try:
        row = conn.execute(
            "SELECT face_count, centroid FROM clusters WHERE cluster_id='c-secret'"
        ).fetchone()
        assert int(row[0]) == 0
        assert row[1] is None
    finally:
        conn.close()


def test_text_search_keeps_a_zero_score(tmp_path):
    from semblon.search import search_text

    store = tmp_path / "s.sqlite"
    conn = _seed(store)
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider, score, payload_json)
           VALUES ('t0','o1','r1','text','ocr',0,'{"text":"zero semblon"}')"""
    )
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider, score, payload_json)
           VALUES ('t1','o1','r1','text','ocr',NULL,'{"text":"missing semblon"}')"""
    )
    conn.commit()
    conn.close()
    rec = search_text(store, "semblon")
    by_id = {item["item_id"]: item["score"] for item in rec["items"]}
    assert by_id["t0"] == 0
    assert by_id["t1"] == 1.0


def test_region_text_door_keeps_a_zero_score():
    """The selection text door must not turn the stored 0 back into 1.0."""
    from semblon.region_search import _as_text_result
    from semblon.similarity_profile import resolve_search_quality

    out = _as_text_result(
        {
            "status": "SUCCESS",
            "items": [
                {"item_id": "t0", "media_id": "m1", "provider": "ocr", "score": 0},
                {"item_id": "t1", "media_id": "m2", "provider": "ocr", "score": None},
            ],
        },
        token="semblon",
        quality=resolve_search_quality("balanced"),
    )
    by_id = {item["item_id"]: item["score"] for item in out["items"]}
    assert by_id["t0"] == 0.0
    assert by_id["t1"] == 1.0


def test_parallel_hash_decodes_the_same_bytes(tmp_path):
    from semblon.ingest import ingest

    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"\xff\xd8\xfffake")
    store = tmp_path / "s.sqlite"
    reads = {"n": 0}
    real = Path.read_bytes

    def _counting(self, *args, **kwargs):
        if self.suffix.lower() == ".jpg":
            reads["n"] += 1
        return real(self, *args, **kwargs)

    image = np.zeros((8, 8, 3), dtype=np.uint8)
    faces = [{
        "bbox": (0, 0, 4, 4),
        "det_score": 0.9,
        "face_w": 40,
        "face_h": 40,
        "dim": 4,
        "embedding": np.zeros(4, np.float32),
    }]
    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    with (
        patch.object(Path, "read_bytes", _counting),
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest.embed_bgr", return_value=faces),
        patch("semblon.ingest.cv2.imdecode", return_value=image),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        ingest(folder, store, workers=2)
    assert reads["n"] == 1


def test_note_on_a_face_does_not_freeze_its_cluster(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    first = cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = connect(store)
    cid = conn.execute("SELECT cluster_id FROM faces WHERE face_id='f1'").fetchone()[0]
    conn.close()
    note_subject(store, "r1", "hello", face_id="f1")
    second = cluster_run(store, "r1", eps=0.15, min_samples=2)
    assert second["clusters"] == first["clusters"]
    conn = connect(store)
    try:
        again = conn.execute("SELECT cluster_id FROM faces WHERE face_id='f1'").fetchone()[0]
        partner = conn.execute("SELECT cluster_id FROM faces WHERE face_id='f2'").fetchone()[0]
        assert again == partner
        assert again != cid
    finally:
        conn.close()


def test_same_filename_different_content_does_not_retarget(tmp_path):
    """Recovery must not merge unrelated media just because the basename matches."""
    from semblon.ingest import _remember_path

    store = tmp_path / "s.sqlite"
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()
    first = a_dir / "photo.jpg"
    first.write_bytes(b"content-one")
    other = b_dir / "photo.jpg"
    other.write_bytes(b"content-two-different")
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(first), "hash-one", 1, 1, 0, 1),
    )
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m2", "folder", str(other), "hash-two", 1, 1, 0, 1),
    )
    conn.commit()
    # Original still present: must not steal m1 onto the other file's path.
    assert _remember_path(conn, "m1", other, 9, 20) is False
    row = conn.execute("SELECT path, sha256 FROM media WHERE media_id='m1'").fetchone()
    assert row[0] == str(first)
    assert row[1] == "hash-one"
    row2 = conn.execute("SELECT path, sha256 FROM media WHERE media_id='m2'").fetchone()
    assert row2[0] == str(other)
    assert row2[1] == "hash-two"
    conn.close()


def test_ingest_updates_path_when_original_moved(tmp_path):
    """Re-adding a folder after a rename reconnects the same hash to the new path."""
    import cv2
    from unittest.mock import patch

    from semblon.process import process_folder

    folder = tmp_path / "photos"
    folder.mkdir()
    photo = folder / "a.jpg"
    img = np.zeros((24, 24, 3), dtype=np.uint8)
    img[:, :] = (40, 90, 200)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    photo.write_bytes(buf.tobytes())
    store = tmp_path / "s.sqlite"
    quiet = lambda *_a, **_k: None
    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.embed_bgr", return_value=[]),
    ):
        process_folder(folder, store=store, observers="color", progress=quiet)
    conn = connect(store)
    try:
        rows = conn.execute("SELECT media_id, path, sha256 FROM media").fetchall()
        assert len(rows) == 1
        media_id, old_path, digest = rows[0]
        assert Path(old_path) == photo
    finally:
        conn.close()
    moved = folder / "renamed.jpg"
    photo.replace(moved)
    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.embed_bgr", return_value=[]),
    ):
        process_folder(folder, store=store, observers="color", progress=quiet)
    conn = connect(store)
    try:
        rows = conn.execute("SELECT media_id, path, sha256 FROM media").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == media_id
        assert rows[0][1] == str(moved)
        assert rows[0][2] == digest
        assert not photo.is_file()
        assert moved.is_file()
    finally:
        conn.close()


def test_whole_image_similar_basis_says_colour_histogram(tmp_path):
    from semblon.observers import observe_bgr
    from semblon.search import search_similar_media

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',8,8,0,1)")
    conn.execute("INSERT INTO media VALUES ('m2','folder','/b.jpg','bbb',8,8,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',NULL,NULL,'r1')")
    dark = np.zeros((8, 8, 3), dtype=np.uint8)
    light = np.full((8, 8, 3), 255, dtype=np.uint8)
    observe_bgr(conn, observation_id="o1", run_id="r1", img=dark, observers=("color",))
    observe_bgr(conn, observation_id="o2", run_id="r1", img=light, observers=("color",))
    conn.commit()
    conn.close()
    rec = search_similar_media(store, "m1")
    assert "colour" in str(rec.get("similarity_basis") or "").lower()
    assert rec.get("modality") == "appearance" or rec.get("status") in {
        "SUCCESS",
        "NO_RESULT",
        "UNAVAILABLE",
    }
