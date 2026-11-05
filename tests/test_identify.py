"""FACE-004 identify vs persons — no InsightFace."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from semblon.cli import main
from semblon.erasure import delete_person
from semblon.identify import IdentifyError, identify_face
from semblon.review import name_cluster
from tests.test_cluster import _seed
from tests.test_review import _clustered


def _conn(store: Path):
    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    return conn


def test_identify_accepts_named_person_not_cluster(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c_alice = assigned["f1"]
    c_bob = assigned["f3"]
    assert c_alice != c_bob
    name_cluster(store, "r1", c_alice, "Alice")
    name_cluster(store, "r1", c_bob, "Bob")

    rec = identify_face(store, "r1", "f2")
    assert rec["decision"] == "ACCEPT"
    assert rec["display_name"] == "Alice"
    assert rec["person_id"] is not None
    assert rec["score_top1"] >= 0.60
    assert rec["gallery_size"] == 2

    conn = _conn(store)
    face = conn.execute("SELECT person_id FROM faces WHERE face_id='f2'").fetchone()
    # f2 was named with the cluster, so it already has Alice. Identify must not
    # change that, and must not invent a cluster-as-person path.
    assert face["person_id"] is not None
    d = conn.execute(
        "SELECT kind, person_id, cluster_id, score_top1, score_top2, margin, policy_json"
        " FROM decisions WHERE kind='identify'"
    ).fetchone()
    assert d["kind"] == "identify"
    assert d["cluster_id"] is None
    assert d["person_id"] == rec["person_id"]
    policy = json.loads(d["policy_json"])
    assert policy["against"] == "persons"
    assert policy["decision"] == "ACCEPT"
    conn.close()


def test_identify_does_not_auto_assign_person(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_cluster(store, "r1", assigned["f3"], "Bob")
    rec = identify_face(store, "r1", "f5")
    assert rec["decision"] == "UNKNOWN"
    conn = _conn(store)
    assert conn.execute("SELECT person_id FROM faces WHERE face_id='f5'").fetchone()[0] is None
    conn.close()


def test_identify_unknown_when_gallery_empty(tmp_path):
    store = tmp_path / "s.sqlite"
    _clustered(store)
    rec = identify_face(store, "r1", "f1")
    assert rec["decision"] == "UNKNOWN"
    assert rec["person_id"] is None
    assert rec["gallery_size"] == 0
    assert rec["reason"] == "empty_gallery"
    conn = _conn(store)
    row = conn.execute(
        "SELECT outcome, reason FROM identify_evaluations WHERE evaluation_id=?",
        (rec["evaluation_id"],),
    ).fetchone()
    conn.close()
    assert row["outcome"] == "UNKNOWN"
    assert row["reason"] == "empty_gallery"


def test_identify_unknown_on_ambiguous_gallery(tmp_path):
    """Two named persons both ≥ threshold → UNKNOWN. Wrong identity > unknown."""
    from tests.test_cluster import _vec

    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_cluster(store, "r1", assigned["f3"], "Bob")
    conn = _conn(store)
    # After naming, overwrite one exemplar each so both match probe f5.
    conn.execute(
        "UPDATE faces SET embedding=? WHERE face_id='f1'",
        (_vec(0.707, 0.707),),
    )
    conn.execute(
        "UPDATE faces SET embedding=? WHERE face_id='f3'",
        (_vec(0.707, 0.707),),
    )
    conn.commit()
    conn.close()
    rec = identify_face(store, "r1", "f5")
    assert rec["decision"] == "UNKNOWN"
    assert rec["person_id"] is None
    assert rec["score_top1"] is not None and rec["score_top1"] >= 0.60
    assert rec["score_top2"] is not None and rec["score_top2"] >= 0.60


def test_identify_rejects_bad_face_and_requires_run(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    with pytest.raises(IdentifyError, match="not identifiable"):
        identify_face(store, "r1", "f6")
    with pytest.raises(IdentifyError, match="unknown face"):
        identify_face(store, "r1", "nope")
    with pytest.raises(IdentifyError, match="unknown run"):
        identify_face(store, "missing", "f1")


def test_identify_image_missing_file(tmp_path):
    from semblon.identify import identify_image

    store = tmp_path / "s.sqlite"
    _clustered(store)
    with pytest.raises(IdentifyError, match="not found"):
        identify_image(store, "r1", tmp_path / "nope.jpg")


def test_cli_identify_face(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    assert main(["identify", "--face", "f2", "--run", "r1", "--store", str(store)]) == 0
    assert main(["identify", "--run", "r1", "--store", str(store)]) == 0
    assert main(["identify", "--face", "f2", "--image", "x.jpg", "--run", "r1", "--store", str(store)]) == 2


def test_process_arch_x64_on_arm64_is_emulated():
    from semblon.engine import process_arch, process_execution
    import os

    arch = process_arch()
    exe = process_execution()
    assert arch in {"x64", "arm64"}
    if os.environ.get("PROCESSOR_ARCHITECTURE", "").upper() == "ARM64" and arch == "x64":
        assert exe == "emulated"


def test_identify_persists_evaluation_for_unknown_and_accept(tmp_path):
    """Durable UNKNOWN is distinct from never evaluated (identify_evaluations row)."""
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_cluster(store, "r1", assigned["f3"], "Bob")

    unknown = identify_face(store, "r1", "f5")
    assert unknown["decision"] == "UNKNOWN"
    assert unknown["evaluation_id"]

    accepted = identify_face(store, "r1", "f2")
    assert accepted["decision"] == "ACCEPT"
    assert accepted["evaluation_id"]

    conn = _conn(store)
    rows = conn.execute(
        "SELECT probe_face_id, outcome, reason FROM identify_evaluations ORDER BY probe_face_id"
    ).fetchall()
    by_face = {r["probe_face_id"]: r for r in rows}
    assert by_face["f5"]["outcome"] == "UNKNOWN"
    assert by_face["f2"]["outcome"] == "ACCEPT"
    never = conn.execute(
        "SELECT 1 FROM identify_evaluations WHERE probe_face_id='f6'"
    ).fetchone()
    assert never is None
    conn.close()


def test_identify_unknown_survives_store_reopen(tmp_path):
    """Restart evidence: persist UNKNOWN+reason, close store, read fields back."""
    from semblon.identify import POLICY_VERSION

    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_cluster(store, "r1", assigned["f3"], "Bob")

    unknown = identify_face(store, "r1", "f5")
    assert unknown["decision"] == "UNKNOWN"
    assert unknown["reason"]
    eid = unknown["evaluation_id"]
    reason = unknown["reason"]

    # Simulate process restart: new connection, no in-memory state.
    conn = _conn(store)
    row = conn.execute(
        """SELECT evaluation_id, probe_face_id, embedding_pack, embedding_dim, run_id,
                  outcome, reason, threshold, policy_version, gallery_size,
                  score_top1, score_top2, margin, person_id, source, created_at
           FROM identify_evaluations WHERE evaluation_id=?""",
        (eid,),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["probe_face_id"] == "f5"
    assert row["embedding_pack"]
    assert int(row["embedding_dim"]) > 0
    assert row["run_id"] == "r1"
    assert row["gallery_size"] is not None
    assert row["outcome"] == "UNKNOWN"
    assert row["reason"] == reason
    assert row["policy_version"] == POLICY_VERSION
    assert row["threshold"] is not None
    assert row["created_at"]
    assert row["person_id"] is None


def test_gallery_corrupt_exemplar_dropped_independently(tmp_path):
    """Gallery contract is validated at load, not only when compare() sees the probe."""
    import struct

    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_cluster(store, "r1", assigned["f3"], "Bob")
    conn = _conn(store)
    # Corrupt Alice's exemplar (NaN) while leaving Bob intact (fixture dim=2).
    bad = struct.pack("<2f", float("nan"), 0.0)
    conn.execute("UPDATE faces SET embedding=? WHERE face_id='f1'", (bad,))
    conn.commit()
    conn.close()

    # f2 is near Alice historically; with Alice dropped, Bob-only gallery must not ACCEPT Alice.
    rec = identify_face(store, "r1", "f2")
    assert rec["decision"] in {"ACCEPT", "UNKNOWN"}
    if rec["decision"] == "ACCEPT":
        assert rec["display_name"] != "Alice"
    conn = _conn(store)
    # Probe itself still evaluated; Alice never scored as a valid gallery member.
    assert conn.execute(
        "SELECT COUNT(*) FROM identify_evaluations WHERE probe_face_id='f2'"
    ).fetchone()[0] == 1
    conn.close()


def test_identify_refuses_non_finite_threshold(tmp_path):
    store = tmp_path / "s.sqlite"
    _clustered(store)
    with pytest.raises(IdentifyError, match="non-finite threshold"):
        identify_face(store, "r1", "f1", threshold=float("nan"))


def test_decisions_kind_unchanged_by_identify_evaluations(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    identify_face(store, "r1", "f2")
    conn = _conn(store)
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='decisions'"
    ).fetchone()[0]
    compact = "".join(sql.split())
    assert "kindTEXTNOTNULLCHECK(kindIN('identify','merge','split','name','reject','note'))" in compact
    assert "identify_evaluations" in {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    conn.close()


def test_delete_person_clears_identify_evaluations(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    accepted = identify_face(store, "r1", "f2")
    assert accepted["decision"] == "ACCEPT"
    pid = accepted["person_id"]
    delete_person(store, pid)
    conn = _conn(store)
    left = conn.execute("SELECT COUNT(*) FROM identify_evaluations").fetchone()[0]
    conn.close()
    assert left == 0
