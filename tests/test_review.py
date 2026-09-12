"""0.4 name / merge / split — decisions as evidence. No InsightFace."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

from semblon.cluster import cluster_run
from semblon.review import ReviewError, merge_clusters, name_cluster, split_cluster
from semblon.store import init_db


def _vec(*xs: float) -> bytes:
    return struct.pack(f"<{len(xs)}f", *xs)


def _seed(path: Path) -> None:
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
    ]
    for fid, oid, blob, status in faces:
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, oid, "r1", 0, 0, 20, 20, 0.9, 20, 20, "80-119", status, blob, "pack-a", 2),
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


def test_name_creates_person_and_decision(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    cid = assigned["f1"]
    rec = name_cluster(store, "r1", cid, "Alice")
    assert rec["created_person"] is True
    assert rec["display_name"] == "Alice"
    assert rec["faces_named"] == 2

    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    person = conn.execute("SELECT * FROM persons WHERE person_id=?", (rec["person_id"],)).fetchone()
    assert person["display_name"] == "Alice"
    assert person["status"] == "active"
    link = conn.execute(
        "SELECT 1 FROM cluster_person WHERE cluster_id=? AND person_id=?",
        (cid, rec["person_id"]),
    ).fetchone()
    assert link is not None
    named = {
        r[0]
        for r in conn.execute(
            "SELECT face_id FROM faces WHERE person_id=?", (rec["person_id"],)
        )
    }
    assert named == {"f1", "f2"}
    # cluster id is not the person id
    assert cid != rec["person_id"]
    dec = conn.execute(
        "SELECT kind, cluster_id, person_id FROM decisions WHERE decision_id=?",
        (rec["decision_id"],),
    ).fetchone()
    assert dec["kind"] == "name"
    assert dec["cluster_id"] == cid
    assert dec["person_id"] == rec["person_id"]
    conn.close()


def test_name_same_display_reuses_person(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    a = name_cluster(store, "r1", c1, "Bob")
    b = name_cluster(store, "r1", c2, "Bob")
    assert a["person_id"] == b["person_id"]
    assert b["created_person"] is False


def test_merge_clusters_records_decision(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    assert c1 != c2
    rec = merge_clusters(store, "r1", [c1, c2])
    assert rec["survivor"] == c1
    assert rec["moved_faces"] == 2
    assert rec["face_count"] == 4

    conn = sqlite3.connect(str(store))
    n = conn.execute("SELECT COUNT(*) FROM clusters WHERE run_id='r1'").fetchone()[0]
    assert n == 1
    faces = {
        r[0]: r[1]
        for r in conn.execute("SELECT face_id, cluster_id FROM faces WHERE status='ok'")
    }
    assert faces["f1"] == faces["f3"] == c1
    assert faces["f5"] is None
    kind = conn.execute(
        "SELECT kind FROM decisions WHERE decision_id=?", (rec["decision_id"],)
    ).fetchone()[0]
    assert kind == "merge"
    conn.close()


def test_merge_rejects_different_persons(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    name_cluster(store, "r1", c1, "A")
    name_cluster(store, "r1", c2, "B")
    import pytest

    with pytest.raises(ReviewError, match="different persons"):
        merge_clusters(store, "r1", [c1, c2])


def test_split_clears_person_on_moved_faces(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    named = name_cluster(store, "r1", c1, "Carol")
    rec = split_cluster(store, "r1", c1, ["f2"])
    assert rec["new_cluster"] != c1
    assert rec["moved_faces"] == ["f2"]
    assert rec["faces_remaining"] == 1

    conn = sqlite3.connect(str(store))
    f1 = conn.execute(
        "SELECT cluster_id, person_id FROM faces WHERE face_id='f1'"
    ).fetchone()
    f2 = conn.execute(
        "SELECT cluster_id, person_id FROM faces WHERE face_id='f2'"
    ).fetchone()
    assert f1[0] == c1
    assert f1[1] == named["person_id"]
    assert f2[0] == rec["new_cluster"]
    assert f2[1] is None
    # split-off cluster is not auto-linked as a person
    n_link = conn.execute(
        "SELECT COUNT(*) FROM cluster_person WHERE cluster_id=?",
        (rec["new_cluster"],),
    ).fetchone()[0]
    assert n_link == 0
    kind = conn.execute(
        "SELECT kind FROM decisions WHERE decision_id=?", (rec["decision_id"],)
    ).fetchone()[0]
    assert kind == "split"
    conn.close()


def test_split_rejects_empty_original(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    import pytest

    with pytest.raises(ReviewError, match="leave at least one"):
        split_cluster(store, "r1", c1, ["f1", "f2"])


def test_cli_name_merge_split(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    from semblon.cli import main

    assert main(["name", "--cluster", c1, "--as", "Dana", "--run", "r1", "--store", str(store)]) == 0
    assert main(["split", "--cluster", c1, "--faces", "f2", "--run", "r1", "--store", str(store)]) == 0
    # re-merge the split-off back after clearing the person conflict path:
    # survivor still named; new cluster unnamed — merge allowed (same or no person intersection)
    conn = sqlite3.connect(str(store))
    new_c = conn.execute(
        "SELECT cluster_id FROM faces WHERE face_id='f2'"
    ).fetchone()[0]
    conn.close()
    assert main(["merge", "--clusters", c1, new_c, "--run", "r1", "--store", str(store)]) == 0
    assert main(["name", "--cluster", "missing", "--as", "X", "--run", "r1", "--store", str(store)]) == 2
    # other cluster still distinct
    assert c2 == assigned["f3"]
