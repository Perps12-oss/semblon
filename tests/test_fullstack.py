"""Full-stack architecture expansion. Identity firewall must hold."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from semblon.canvas import load_canvas
from semblon.cli import main
from semblon.compare import CompareError, compare, compare_space
from semblon.engine import select_execution_provider
from semblon.observers import color_histogram, observe_bgr, optional_status
from semblon.opencv_probe import probe_opencv
from semblon.search import SearchError, search_similar
from semblon.store import SCHEMA_VERSION, apply_migrations, connect, init_db
from semblon.watch import watch_folder
from tests.test_cluster import _seed, _vec
from tests.test_review import _clustered
from semblon.review import name_cluster
from semblon.identify import identify_face
from semblon.cluster import cluster_run


def test_migrate_v1_store_to_v2(tmp_path):
    store = tmp_path / "old.sqlite"
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    from semblon.store import DDL

    conn.executescript(DDL)
    conn.execute("INSERT INTO schema_meta(key,value) VALUES ('schema_version','1')")
    conn.commit()
    apply_migrations(conn)
    ver = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0]
    assert ver == SCHEMA_VERSION
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "observation_items" in tables
    conn.close()


def test_appearance_does_not_enter_identity(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    conn = connect(store)
    init_db(conn)
    oid = conn.execute("SELECT observation_id FROM observations LIMIT 1").fetchone()[0]
    rid = conn.execute("SELECT run_id FROM observations LIMIT 1").fetchone()[0]
    img = np.zeros((20, 20, 3), dtype=np.uint8)
    img[:] = (10, 200, 30)
    observe_bgr(conn, observation_id=oid, run_id=rid, img=img, observers=("color", "object"))
    conn.commit()
    n_app = conn.execute("SELECT COUNT(*) FROM observation_items WHERE kind='appearance'").fetchone()[0]
    n_emb = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    assert n_app == 1
    assert n_emb == 1
    modality = conn.execute("SELECT modality FROM embeddings").fetchone()[0]
    assert modality == "appearance"
    item = conn.execute("SELECT item_id FROM observation_items WHERE kind='appearance'").fetchone()[0]
    conn.close()
    rec = identify_face(store, "r1", "f2")
    assert rec["decision"] in {"ACCEPT", "UNKNOWN"}
    # appearance similar search works; cannot be used as identify
    sim = search_similar(store, item)
    assert sim["modality"] == "appearance"
    with pytest.raises(SearchError):
        search_similar(store, "f2")


def test_compare_space_cannot_score_faces():
    blob = _vec(1.0, 0.0)
    with pytest.raises(CompareError, match="face identity"):
        compare_space("face", "p", 2, blob, "face", "p", 2, blob)
    assert compare("p", 2, blob, "p", 2, blob) == pytest.approx(1.0)


def test_cluster_ignores_observation_items(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    conn = connect(store)
    init_db(conn)
    img = np.ones((16, 16, 3), dtype=np.uint8) * 40
    observe_bgr(conn, observation_id="o1", run_id="r1", img=img, observers=("color",))
    conn.commit()
    conn.close()
    rec = cluster_run(store, "r1", eps=0.15, min_samples=2)
    assert rec["clusters"] >= 1
    conn = sqlite3.connect(str(store))
    persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    conn.close()
    assert persons == 0


def test_watch_once(tmp_path):
    folder = tmp_path / "p"
    folder.mkdir()
    (folder / "a.jpg").write_bytes(b"aaaa")
    events = []
    fake_if = type("m", (), {"__version__": "0.test"})()
    fake_ort = type("m", (), {"__version__": "0.test"})()
    vec = np.zeros(4, dtype=np.float32)

    def faces(_app, _img):
        return [
            {
                "bbox": (0.0, 0.0, 10.0, 10.0),
                "det_score": 0.9,
                "face_w": 10,
                "face_h": 10,
                "dim": 4,
                "embedding": vec,
            }
        ]

    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.discover_weight_hashes", return_value={}),
        patch("semblon.ingest.embed_bgr", side_effect=faces),
        patch("semblon.ingest.cv2.imread", return_value=np.zeros((20, 20, 3), dtype=np.uint8)),
        patch.dict("sys.modules", {"insightface": fake_if, "onnxruntime": fake_ort}),
    ):
        rec = watch_folder(folder, tmp_path / "s.sqlite", once=True, on_event=events.append)
    assert rec["cycles"] == 1
    assert rec["runs"]
    conn = sqlite3.connect(str(tmp_path / "s.sqlite"))
    n_media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    n_faces = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
    conn.close()
    assert n_media >= 1
    assert n_faces >= 1


def test_canvas_board(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    board = load_canvas(store, "r1")
    assert board["run_id"] == "r1"
    assert board["faces"]
    assert "not person" in board["note"].lower() or "Track" in board["note"]


def test_cli_help_lists_fullstack_commands():
    assert main(["lab", "providers"]) == 0

    import io
    from unittest.mock import patch

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        try:
            main(["--help"])
        except SystemExit as e:
            assert e.code == 0
    out = buf.getvalue()
    for cmd in ("watch", "live", "canvas", "search"):
        assert cmd in out, cmd


def test_gpu_detection_does_not_invent_gpu():
    rec = select_execution_provider(prefer_gpu=True)
    assert rec["chosen"]
    assert rec["gpu"] is True or rec["device"] == "cpu"
    if rec["gpu"]:
        assert rec["chosen"] in rec["available"]
        assert rec["chosen"] in (
            "CUDAExecutionProvider",
            "DmlExecutionProvider",
            "TensorrtExecutionProvider",
        )
    else:
        assert rec["device"] == "cpu"
        assert "AzureExecutionProvider" not in (
            [rec["chosen"]] if rec.get("gpu") else []
        )
    # Azure never counts as GPU even if listed.
    assert "AzureExecutionProvider" not in (
        rec.get("gpu_eps") or []
    )


def test_opencv_probe_returns_dict():
    rec = probe_opencv(timeout_s=15.0)
    assert "ok" in rec
    assert rec["status"] in {"ok", "timeout", "error", "parse"}


def test_optional_providers_are_honest():
    st = optional_status()
    assert st["facekit"] is True
    assert st["identity"] == "facekit only"
    assert "ocr" in st
    assert "clip" in st
    assert "pose" in st
    # False means a real probe failed; notes must explain why (not silent True-on-import).
    for key in ("ocr", "clip", "pose"):
        if st[key] is False:
            assert key in st["notes"]
            assert "unavailable" in st["notes"][key]
        else:
            assert key not in st["notes"]


def test_cluster_writes_groups_not_persons(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    rec = cluster_run(store, "r1", eps=0.15, min_samples=2)
    assert rec["clusters"] >= 1
    conn = sqlite3.connect(str(store))
    n_groups = conn.execute("SELECT COUNT(*) FROM observation_groups WHERE run_id='r1'").fetchone()[0]
    n_items = conn.execute("SELECT COUNT(*) FROM observation_items WHERE kind='face'").fetchone()[0]
    n_emb_face = conn.execute("SELECT COUNT(*) FROM embeddings WHERE modality='face'").fetchone()[0]
    n_persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    conn.close()
    assert n_groups == rec["clusters"]
    assert n_items >= rec["clustered"]
    assert n_emb_face == 0
    assert n_persons == 0


def test_naming_snapshots_together_relationships(tmp_path):
    from semblon.review import name_cluster, name_face

    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_face(store, "r1", "f5", "Bob")
    conn = sqlite3.connect(str(store))
    n_rel = conn.execute("SELECT COUNT(*) FROM relationships WHERE kind='together' AND confirmed=0").fetchone()[0]
    conn.close()
    assert n_rel >= 1


def test_facekit_provider_load_is_ingest_boundary():
    import inspect

    from semblon import ingest as ing

    src = inspect.getsource(ing.load_app)
    assert "FaceKitProvider" in src


def test_path_traversal_store_is_a_path(tmp_path):
    from semblon.store import integrity_report

    with pytest.raises(FileNotFoundError):
        integrity_report(tmp_path / ".." / "nope-not-a-store.sqlite")
