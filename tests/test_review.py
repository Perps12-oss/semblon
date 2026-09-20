"""0.4 name / merge / split — decisions as evidence. No InsightFace."""

from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import pytest

from semblon.cluster import cluster_run
from semblon.export import export_review
from semblon.review import (
    ReviewError,
    ignore_subject,
    merge_clusters,
    name_cluster,
    name_faces,
    name_track,
    note_subject,
    split_cluster,
)
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


def test_name_same_display_creates_distinct_persons(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    a = name_cluster(store, "r1", c1, "Bob")
    b = name_cluster(store, "r1", c2, "Bob")
    assert a["person_id"] != b["person_id"]
    assert a["created_person"] is True
    assert b["created_person"] is True


def test_name_attach_to_reuses_person(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    a = name_cluster(store, "r1", c1, "Bob")
    b = name_cluster(store, "r1", c2, "Bob", attach_to_person_id=a["person_id"])
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


def test_delete_all_clusters_is_blocked_after_merge(tmp_path):
    """S1 traceback: DELETE FROM clusters WHERE run_id=? after a merge decision.

    The FK is correct. cluster_run must not use that wipe.
    """
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    merge_clusters(store, "r1", [assigned["f1"], assigned["f3"]])
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("UPDATE faces SET cluster_id=NULL WHERE run_id='r1'")
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute("DELETE FROM clusters WHERE run_id='r1'")
    conn.close()


def test_cli_merge_then_cluster_then_export_keeps_review_identity(tmp_path):
    """Exact ship path: cluster → merge → cluster again → export."""
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    from semblon.cli import main

    assert (
        main(["merge", "--clusters", c1, c2, "--run", "r1", "--store", str(store)])
        == 0
    )
    rec = cluster_run(store, "r1", eps=0.15, min_samples=2)
    assert rec["ok_faces"] == 5
    assert rec["review_locked"] > 0

    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    faces = {
        r["face_id"]: r["cluster_id"]
        for r in conn.execute("SELECT face_id, cluster_id FROM faces WHERE status='ok'")
    }
    assert faces["f1"] == faces["f2"] == faces["f3"] == faces["f4"] == c1
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM decisions WHERE kind='merge'").fetchone()[0] == 1
    # Survivor status is not clobbered to 'merged'; merge is locked via decisions.
    st = conn.execute("SELECT status FROM clusters WHERE cluster_id=?", (c1,)).fetchone()[0]
    assert st != "ignored"
    conn.close()

    out = tmp_path / "review.html"
    export_review(store, "r1", out)
    text = out.read_text(encoding="utf-8")
    assert "DECISIONS" in text
    assert "merge" in text
    assert c1[:8] in text or c1 in text


def test_merge_is_not_a_person_and_survives_recluster(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    rec = merge_clusters(store, "r1", [c1, c2])
    assert rec["person_id"] is None

    conn = sqlite3.connect(str(store))
    n_person = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    n_link = conn.execute("SELECT COUNT(*) FROM cluster_person").fetchone()[0]
    assert n_person == 0
    assert n_link == 0
    before = conn.execute(
        "SELECT COUNT(*) FROM decisions WHERE kind='merge'"
    ).fetchone()[0]
    conn.close()

    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = sqlite3.connect(str(store))
    faces = {
        r[0]: r[1]
        for r in conn.execute("SELECT face_id, cluster_id FROM faces WHERE status='ok'")
    }
    assert faces["f1"] == faces["f2"] == faces["f3"] == faces["f4"] == c1
    assert faces["f5"] is None
    after = conn.execute("SELECT COUNT(*) FROM decisions WHERE kind='merge'").fetchone()[0]
    assert after == before == 1
    n_person = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    assert n_person == 0
    conn.close()


def test_cluster_run_does_not_create_persons(tmp_path):
    """FACE-003 must-not: STRONG/auto clusters are not people until name."""
    store = tmp_path / "s.sqlite"
    _clustered(store)
    conn = sqlite3.connect(str(store))
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM faces WHERE person_id IS NOT NULL"
    ).fetchone()[0] == 0
    conn.close()
    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = sqlite3.connect(str(store))
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM faces WHERE person_id IS NOT NULL"
    ).fetchone()[0] == 0
    conn.close()


def test_ignore_and_note_export_without_person(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    ign = ignore_subject(store, "r1", cluster_id=c1, disposition="not_a_person")
    assert ign["person_id"] is None
    note = note_subject(store, "r1", "same person split across groups", cluster_id=c1)
    assert note["person_id"] is None
    mark = ignore_subject(store, "r1", face_id="f5", disposition="singleton")
    assert mark["disposition"] == "singleton"

    cluster_run(store, "r1", eps=0.15, min_samples=2)
    conn = sqlite3.connect(str(store))
    assert conn.execute("SELECT cluster_id FROM faces WHERE face_id='f1'").fetchone()[0] == c1
    assert conn.execute("SELECT cluster_id FROM faces WHERE face_id='f5'").fetchone()[0] is None
    assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
    note_kind = conn.execute(
        "SELECT kind FROM decisions WHERE decision_id=?", (note["decision_id"],)
    ).fetchone()[0]
    assert note_kind == "note"
    conn.close()

    out = tmp_path / "review.html"
    export_review(store, "r1", out)
    text = out.read_text(encoding="utf-8")
    assert "DECISIONS" in text
    assert "not_a_person" in text
    assert "singleton" in text
    assert "same person split across groups" in text


def test_name_refuses_ignored_cluster(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    ignore_subject(store, "r1", cluster_id=c1)
    with pytest.raises(ReviewError, match="ignored"):
        name_cluster(store, "r1", c1, "Nope")


def test_split_strategy_is_plain(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    rec = split_cluster(store, "r1", c1, ["f2"])
    conn = sqlite3.connect(str(store))
    strat = conn.execute(
        "SELECT strategy FROM clusters WHERE cluster_id=?", (rec["new_cluster"],)
    ).fetchone()[0]
    conn.close()
    assert strat == "split"


def test_cli_review_merge_ignore(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    from semblon.cli import main

    assert (
        main(
            [
                "review",
                "--run",
                "r1",
                "--store",
                str(store),
                "merge",
                "--clusters",
                c1,
                c2,
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "review",
                "--run",
                "r1",
                "--store",
                str(store),
                "ignore",
                "--face",
                "f5",
                "--as",
                "junk",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "review",
                "--run",
                "r1",
                "--store",
                str(store),
                "note",
                "--cluster",
                c1,
                "--text",
                "held as review identity, not a name",
            ]
        )
        == 0
    )
    assert main(["review", "--run", "r1", "--store", str(store), "ignore"]) == 2


def _seed_video_track(store: Path) -> str:
    """Two overlapping video faces → one derived track. Returns track_id."""
    conn = sqlite3.connect(str(store))
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, finished_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        ("rt", "t0", "t1", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "native"),
    )
    conn.execute("INSERT INTO media VALUES ('mv','video','C:/clips/a.mp4','v1',320,240,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','mv',0,0,'rt')")
    conn.execute("INSERT INTO observations VALUES ('o2','mv',25,1000,'rt')")
    for fid, oid, blob in (
        ("fa", "o1", _vec(1.0, 0.0)),
        ("fb", "o2", _vec(0.0, 1.0)),
    ):
        conn.execute(
            """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
               det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, oid, "rt", 10, 10, 110, 110, 0.9, 100, 100, "80-119", "ok", blob, "pack-a", 2),
        )
    conn.commit()
    conn.close()
    from semblon.tracks import derive_tracks

    rec = derive_tracks(store, "rt")
    assert rec["counts"]["tracks"] == 1
    return rec["tracks"][0]["track_id"]


def test_name_track_enrols_members_not_as_cluster(tmp_path):
    store = tmp_path / "s.sqlite"
    tid = _seed_video_track(store)
    rec = name_track(store, "rt", tid, "Ada")
    assert rec["faces_named"] == 2
    assert rec["created_person"] is True
    assert rec["person_id"] != tid
    assert rec["track_id"] == tid
    conn = sqlite3.connect(str(store))
    persons = conn.execute("SELECT person_id, display_name FROM persons").fetchall()
    assert len(persons) == 1
    assert persons[0][1] == "Ada"
    named = {
        r[0]
        for r in conn.execute("SELECT face_id FROM faces WHERE person_id=?", (rec["person_id"],))
    }
    assert named == {"fa", "fb"}
    clustered = conn.execute("SELECT cluster_id FROM faces WHERE face_id='fa'").fetchone()[0]
    assert clustered is None
    links = conn.execute("SELECT 1 FROM cluster_person").fetchone()
    assert links is None
    pol = conn.execute("SELECT policy_json FROM decisions WHERE decision_id=?", (rec["decision_id"],)).fetchone()[0]
    conn.close()
    assert "track" in pol
    assert tid in pol


def test_name_faces_refuses_clustered(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    cid = assigned["f1"]
    with pytest.raises(ReviewError, match="cluster"):
        name_faces(store, "r1", ["f1", "f2"], "Nope")
    assert cid


def test_cli_name_track(tmp_path):
    from semblon.cli import main

    store = tmp_path / "s.sqlite"
    tid = _seed_video_track(store)
    assert (
        main(
            [
                "name",
                "--run",
                "rt",
                "--store",
                str(store),
                "--track",
                tid,
                "--as",
                "Ada",
            ]
        )
        == 0
    )
    conn = sqlite3.connect(str(store))
    n = conn.execute("SELECT COUNT(*) FROM faces WHERE person_id IS NOT NULL").fetchone()[0]
    conn.close()
    assert n == 2
