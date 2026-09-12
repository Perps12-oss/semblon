"""0.3 cluster + export — no InsightFace."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

from semblon.cluster import cluster_run
from semblon.export import export_review
from semblon.store import init_db


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


def test_export_sections_and_readonly(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    out = tmp_path / "review.html"
    rec = export_review(store, "r1", out, strong_min_intra=0.50)
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "REVIEW REQUIRED" in text
    assert "STRONG" in text
    assert "UNASSIGNED" in text
    assert "REJECTED" in text
    assert "not a person" in text
    assert rec["clusters"] == 2
    conn = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
    n_dec = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    assert n_dec == 0


def test_cli_cluster_export(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    from semblon.cli import main

    assert main(["cluster", "--run", "r1", "--store", str(store), "--eps", "0.15"]) == 0
    out = tmp_path / "r.html"
    assert main(["export", "--run", "r1", "--store", str(store), "--out", str(out)]) == 0
    assert out.is_file()
    assert main(["cluster", "--run", "missing", "--store", str(store)]) == 2
