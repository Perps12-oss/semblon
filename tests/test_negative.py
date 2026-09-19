"""Negative / boundary behaviour. No InsightFace. Unknown and failure stay honest."""

from __future__ import annotations

import sqlite3
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.cli import main
from semblon.ingest import ingest
from semblon.review import name_cluster
from semblon.review_ui import ReviewUiError, resolve_run_id
from semblon.store import backup_store, init_db, restore_store
from tests.test_cluster import _seed
from tests.test_review import _clustered


def _embed_patches(faces_for, imread=None):
    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    img = np.zeros((20, 20, 3), dtype=np.uint8) if imread is None else imread
    stack = ExitStack()
    stack.enter_context(patch("semblon.ingest.load_app", return_value=object()))
    stack.enter_context(patch("semblon.ingest.discover_weight_hashes", return_value={}))
    stack.enter_context(
        patch("semblon.ingest.embed_image", side_effect=lambda app, path: faces_for(path))
    )
    stack.enter_context(
        patch(
            "semblon.ingest.cv2.imread",
            side_effect=img if callable(img) else lambda *_a, **_k: img,
        )
    )
    stack.enter_context(patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}))
    return stack


def _one_face(_path):
    vec = np.zeros(4, dtype=np.float32)
    return [
        {
            "bbox": (0.0, 0.0, 100.0, 100.0),
            "det_score": 0.9,
            "face_w": 100,
            "face_h": 100,
            "dim": 4,
            "embedding": vec,
        }
    ]


def test_unsupported_and_zero_byte_and_corrupt_do_not_invent_faces(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "ok.jpg").write_bytes(b"aaaa")
    (folder / "empty.jpg").write_bytes(b"")
    (folder / "notes.txt").write_text("ignore")
    (folder / "corrupt.jpg").write_bytes(b"not-an-image")

    def imread(path, *args, **kwargs):
        if Path(path).name == "ok.jpg":
            return np.zeros((20, 20, 3), dtype=np.uint8)
        return None

    with _embed_patches(_one_face, imread=imread):
        rec = ingest(folder, tmp_path / "s.sqlite")

    assert rec["files"] == 3  # stills only; .txt ignored
    assert rec["failed"] == 2
    assert rec["new_media"] == 1
    assert rec["faces"] == 1
    conn = sqlite3.connect(str(tmp_path / "s.sqlite"))
    names = [r[0] for r in conn.execute("SELECT path FROM media")]
    conn.close()
    assert any(p.endswith("ok.jpg") for p in names)
    assert not any(p.endswith("empty.jpg") for p in names)
    assert not any(p.endswith("corrupt.jpg") for p in names)


def test_duplicate_content_is_skipped_not_duplicated(tmp_path):
    folder = tmp_path / "photos"
    folder.mkdir()
    payload = b"same-bytes"
    (folder / "a.jpg").write_bytes(payload)
    (folder / "b.jpg").write_bytes(payload)
    with _embed_patches(_one_face):
        rec = ingest(folder, tmp_path / "s.sqlite")
    assert rec["new_media"] == 1
    assert rec["skipped_same_run"] == 1
    conn = sqlite3.connect(str(tmp_path / "s.sqlite"))
    n_media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    n_obs = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    conn.close()
    assert n_media == 1
    assert n_obs == 1


def test_interrupted_ingest_then_reingest_does_not_duplicate(tmp_path):
    """Crash leaves finished_at NULL; next ingest skips seen hashes."""
    folder = tmp_path / "photos"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"aaaa")
    store = tmp_path / "s.sqlite"
    with _embed_patches(_one_face):
        rec1 = ingest(folder, store)
    conn = sqlite3.connect(str(store))
    conn.execute("UPDATE runs SET finished_at=NULL, notes='interrupted' WHERE run_id=?", (rec1["run_id"],))
    conn.commit()
    conn.close()
    (folder / "b.jpg").write_bytes(b"bbbb")
    with _embed_patches(_one_face):
        rec2 = ingest(folder, store)
    assert rec2["skipped_seen"] == 1
    assert rec2["new_media"] == 1
    conn = sqlite3.connect(str(store))
    n_media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    n_ok = conn.execute("SELECT COUNT(*) FROM faces WHERE status='ok'").fetchone()[0]
    conn.close()
    assert n_media == 2
    assert n_ok == 2


def test_cluster_is_not_a_person(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    conn = sqlite3.connect(str(store))
    persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    named = conn.execute("SELECT COUNT(*) FROM faces WHERE person_id IS NOT NULL").fetchone()[0]
    conn.close()
    assert persons == 0
    assert named == 0
    assert assigned["f1"]  # cluster exists
    name_cluster(store, "r1", assigned["f1"], "Alice")
    conn = sqlite3.connect(str(store))
    pid = conn.execute("SELECT person_id FROM faces WHERE face_id='f1'").fetchone()[0]
    cid = conn.execute("SELECT cluster_id FROM faces WHERE face_id='f1'").fetchone()[0]
    other = conn.execute("SELECT person_id FROM faces WHERE face_id='f3'").fetchone()[0]
    conn.close()
    assert pid is not None
    assert pid != cid
    assert other is None


def test_naming_one_person_does_not_rename_another(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_cluster(store, "r1", assigned["f3"], "Bob")
    conn = sqlite3.connect(str(store))
    names = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT f.face_id, p.display_name FROM faces f JOIN persons p ON p.person_id=f.person_id"
        )
    }
    conn.close()
    assert names["f1"] == "Alice"
    assert names["f2"] == "Alice"
    assert names["f3"] == "Bob"
    assert names["f4"] == "Bob"
    assert "f5" not in names


def test_review_ui_missing_store_and_empty_store(tmp_path):
    missing = tmp_path / "nope.sqlite"
    with pytest.raises(ReviewUiError, match="store not found"):
        resolve_run_id(missing, None)
    store = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(str(store))
    init_db(conn)
    conn.close()
    with pytest.raises(ReviewUiError, match="store has no runs"):
        resolve_run_id(store, None)


def test_memory_survives_unreadable_source_path(tmp_path):
    """Missing/invalid originals must not crash history (unknown place is valid)."""
    from semblon.memory import history, read_still_exif

    assert read_still_exif(Path(r"D:\photos\lake\20260509_140604.jpg")) == {}
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    rec = history(store, person="Alice")
    assert rec["display_name"] == "Alice"
    assert rec["items"]


def test_backup_restore_roundtrip_and_refuse_overwrite(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    bak = tmp_path / "bak.sqlite"
    rec = backup_store(store, bak)
    assert Path(rec["out"]).is_file()
    dest = tmp_path / "restored.sqlite"
    restore_store(bak, dest)
    conn = sqlite3.connect(str(dest))
    n = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
    conn.close()
    assert n >= 1
    with pytest.raises(FileExistsError):
        restore_store(bak, dest)
    restore_store(bak, dest, force=True)
    assert main(["lab", "backup", "--store", str(store), "--out", str(tmp_path / "cli.sqlite")]) == 0
    assert main(["lab", "restore", "--from", str(bak), "--store", str(dest)]) == 2
