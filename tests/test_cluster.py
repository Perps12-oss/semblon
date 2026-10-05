"""Cluster + export — no InsightFace."""

from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path

from semblon.cluster import cluster_run
from semblon.export import _stored_json
from semblon.review_board import load_board
from semblon.store import init_db

_VECTOR_KEYS = frozenset({
    "embedding",
    "centroid",
    "vector",
    "normed_embedding",
    "bbox",
    "det_score",
    "person_id",
    "sha256",
    "decision_id",
})
_EVIDENCE_KEYS = {
    "schema_version",
    "run_id",
    "started_at",
    "finished_at",
    "software_version",
    "pack_id",
    "embedding_dim",
    "embedding_norm",
    "config_json",
    "runtime_json",
    "arch",
    "execution",
    "ort_version",
    "peak_rss_mb",
    "timings_json",
    "strong_min_intra",
    "counts",
    "clusters",
    "decisions",
}
_COUNT_KEYS = {
    "faces",
    "ok",
    "low_quality",
    "rejected",
    "clusters",
    "review_required",
    "strong",
    "unassigned",
    "decisions",
}


def _parse_evidence(html: str) -> dict:
    marker = f'id="{EVIDENCE_SCRIPT_ID}"'
    start = html.index(marker)
    open_gt = html.index(">", start) + 1
    close = html.index("</script>", open_gt)
    return json.loads(html[open_gt:close])


def _assert_no_vector_fields(obj) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in _VECTOR_KEYS
            assert not isinstance(v, (bytes, bytearray, memoryview))
            _assert_no_vector_fields(v)
    elif isinstance(obj, list):
        for item in obj:
            _assert_no_vector_fields(item)


def _vec(*xs: float) -> bytes:
    return struct.pack(f"<{len(xs)}f", *xs)


def _seed(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',100,100,0,1)")
    conn.execute("INSERT INTO media VALUES ('m2','folder','/b.jpg','bbb',100,100,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute("INSERT INTO observations VALUES ('o2','m2',NULL,NULL,'r1')")
    faces = [
        ("f1", "o1", _vec(1.0, 0.0), "ok"),
        ("f2", "o1", _vec(0.99, 0.141), "ok"),
        ("f3", "o2", _vec(0.0, 1.0), "ok"),
        ("f4", "o2", _vec(0.141, 0.99), "ok"),
        ("f5", "o1", _vec(0.707, 0.707), "ok"),
        ("f6", "o2", None, "rejected"),
        ("f7", "o1", _vec(1.0, 0.0), "low_quality"),
    ]
    for fid, oid, blob, status in faces:
        pack = "pack-a" if blob is not None else None
        dim = 2 if blob is not None else None
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, oid, "r1", 0, 0, 20, 20, 0.9, 20, 20, "80-119", status, blob, pack, dim),
        )
    conn.commit()
    return conn


def test_cluster_groups_and_leaves_noise(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    rec = cluster_run(store, "r1", eps=0.15, min_samples=2)
    assert rec["clusters"] == 2
    assert rec["clustered"] == 4
    assert rec["unassigned"] == 1
    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    assigned = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT face_id, cluster_id FROM faces WHERE status='ok'"
        )
    }
    assert assigned["f1"] == assigned["f2"]
    assert assigned["f3"] == assigned["f4"]
    assert assigned["f1"] != assigned["f3"]
    assert assigned["f5"] is None
    assert conn.execute("SELECT cluster_id FROM faces WHERE face_id='f6'").fetchone()[0] is None
    assert conn.execute("SELECT cluster_id FROM faces WHERE face_id='f7'").fetchone()[0] is None
    rows = conn.execute("SELECT face_count, min_intra FROM clusters ORDER BY min_intra").fetchall()
    assert all(r[0] == 2 for r in rows)
    assert all(r[1] is not None and r[1] > 0.9 for r in rows)


def test_cluster_replaces_previous(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = sqlite3.connect(str(store))
    n = conn.execute("SELECT COUNT(*) FROM clusters WHERE run_id='r1'").fetchone()[0]
    assert n == 2
    dangling = conn.execute(
        "SELECT COUNT(*) FROM faces WHERE cluster_id IS NOT NULL AND cluster_id NOT IN (SELECT cluster_id FROM clusters)"
    ).fetchone()[0]
    assert dangling == 0


def test_cluster_unknown_run(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    import pytest
    from semblon.cluster import ClusterError

    with pytest.raises(ClusterError):
        cluster_run(store, "nope")


def test_stored_json_parses_only_valid_json():
    assert _stored_json(None) is None
    assert _stored_json("") == ""
    assert _stored_json("{}") == {}
    assert _stored_json('{"folder":"D:\\\\photos"}') == {"folder": r"D:\photos"}
    assert _stored_json("not-json") == "not-json"
    already = {"keep": 1}
    assert _stored_json(already) is already


def test_board_sections_are_readonly(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    before = sqlite3.connect(str(store))
    n_runs = before.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    n_clusters = before.execute("SELECT COUNT(*) FROM clusters").fetchone()[0]
    before.close()

    board = load_board(store, "r1")
    assert board["run_id"] == "r1"
    bands = {item["band"] for item in board["items"]}
    assert "review" in bands or "strong" in bands
    assert "unassigned" in bands
    assert board["decisions"] == []
    conn = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
    n_dec = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    assert n_dec == 0
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == n_runs
    assert conn.execute("SELECT COUNT(*) FROM clusters").fetchone()[0] == n_clusters
    conn.close()
    assert not (tmp_path / "review.html").exists()


def test_board_has_run_identity_and_no_embeddings(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    board = load_board(store, "r1")
    assert board["run_id"] == "r1"
    assert board["pack_id"] == "pack-a"
    assert board["strong_min_intra"] == 0.50
    assert board["decisions"] == []

    def _walk(obj):
        if isinstance(obj, dict):
            assert "embedding" not in obj
            assert "centroid" not in obj
            for value in obj.values():
                _walk(value)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(board)
    clusters = [item for item in board["items"] if item["kind"] == "cluster"]
    assert len(clusters) == 2
    assert all(item["face_count"] == 2 for item in clusters)


def test_board_unassigned_is_ok_faces_without_cluster(tmp_path):
    """OK+clustered / OK+none / low_quality / rejected — only OK+none is unassigned."""
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    rec = cluster_run(store, "r1", eps=0.15, min_samples=2)
    assert rec["clustered"] == 4
    assert rec["unassigned"] == 1

    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    rows = {
        r["face_id"]: (r["status"], r["cluster_id"])
        for r in conn.execute("SELECT face_id, status, cluster_id FROM faces")
    }
    conn.close()
    assert rows["f1"][0] == "ok" and rows["f1"][1] is not None
    assert rows["f2"][0] == "ok" and rows["f2"][1] is not None
    assert rows["f5"] == ("ok", None)
    assert rows["f7"] == ("low_quality", None)
    assert rows["f6"] == ("rejected", None)

    board = load_board(store, "r1")
    unassigned = [item for item in board["items"] if item["band"] == "unassigned"]
    assert len(unassigned) == rec["unassigned"] == 1


def test_cli_cluster_export_views(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    from semblon.cli import main

    assert main(["cluster", "--run", "r1", "--store", str(store), "--eps", "0.15"]) == 0
    dest = tmp_path / "views"
    assert main(["export", "--run", "r1", "--store", str(store), "--views", str(dest)]) == 0
    assert (dest / "VIEW.txt").is_file()
    assert not (tmp_path / "review.html").exists()
    assert main(["cluster", "--run", "missing", "--store", str(store)]) == 2
