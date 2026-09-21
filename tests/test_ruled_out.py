"""Ruled-out scaffold: display matrix + gated dry-run / write path."""

from __future__ import annotations

import json
import sqlite3
import struct
from pathlib import Path

import pytest

from semblon import gates, ruled_out
from semblon.review import ReviewError
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
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute(
        """INSERT INTO faces(face_id,observation_id,run_id,bbox_x1,bbox_y1,bbox_x2,bbox_y2,
           det_score,face_w,face_h,size_band,status,embedding,embedding_pack,embedding_dim)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("f1", "o1", "r1", 0, 0, 20, 20, 0.9, 20, 20, "80-119", "ok", _vec(1.0, 0.0), "pack-a", 2),
    )
    conn.execute(
        """INSERT INTO clusters(cluster_id, run_id, strategy, face_count, status)
           VALUES (?,?,?,?,?)""",
        ("c1", "r1", "dbscan", 1, "auto"),
    )
    conn.execute("UPDATE faces SET cluster_id=? WHERE face_id=?", ("c1", "f1"))
    conn.commit()
    conn.close()


# --- display_state (R3 matrix) ---


@pytest.mark.parametrize(
    "evidence,decision,expected",
    [
        ("none", "undecided", "Unknown"),
        ("none", "deferred", "Ignored"),
        ("similar", "undecided", "Possible"),
        ("similar", "affirmed", "Confirmed"),
        ("similar", "rejected", "Ruled out"),
        ("similar", "deferred", "Ignored"),
        ("clustered", "undecided", "Possible"),
        ("clustered", "affirmed", "Confirmed"),
        ("clustered", "rejected", "Ruled out"),
        ("clustered", "deferred", "Ignored"),
        ("detected", "undecided", "Possible"),
        ("weak", "rejected", "Ruled out"),
        ("strong", "affirmed", "Confirmed"),
    ],
)
def test_display_state_matrix(evidence, decision, expected):
    assert ruled_out.display_state(evidence, decision) == expected


def test_display_state_impossible_none_affirmed():
    with pytest.raises(ValueError, match="impossible"):
        ruled_out.display_state("none", "affirmed")


def test_display_state_impossible_none_rejected():
    with pytest.raises(ValueError, match="impossible"):
        ruled_out.display_state("none", "rejected")


def test_display_state_unknown_evidence():
    with pytest.raises(ValueError, match="unknown evidence"):
        ruled_out.display_state("geometry", "undecided")


# --- propose_ruled_out_policy ---


def test_propose_policy_face():
    pol = ruled_out.propose_ruled_out_policy(face_id="f1", person_id="p1", reason="not maya")
    assert pol["action"] == "ruled_out"
    assert pol["action"] != "ignore"
    assert pol["subject"] == "face"
    assert pol["person_id"] == "p1"
    assert pol["disposition"] == "not_this_person"
    assert pol["reason"] == "not maya"


def test_propose_policy_requires_one_subject():
    with pytest.raises(ReviewError, match="exactly one"):
        ruled_out.propose_ruled_out_policy()
    with pytest.raises(ReviewError, match="exactly one"):
        ruled_out.propose_ruled_out_policy(face_id="f1", cluster_id="c1")


# --- record_ruled_out (gate + dry_run) ---


def test_record_requires_gate(monkeypatch, tmp_path):
    monkeypatch.delenv("SEMBLON_GATE_RULED_OUT", raising=False)
    store = tmp_path / "s.sqlite"
    _seed(store)
    with pytest.raises(RuntimeError, match="is OFF"):
        ruled_out.record_ruled_out(store, "r1", face_id="f1")


def test_record_dry_run_default_no_write(monkeypatch, tmp_path):
    monkeypatch.setenv("SEMBLON_GATE_RULED_OUT", "1")
    assert gates.is_enabled("ruled_out") is True
    store = tmp_path / "s.sqlite"
    _seed(store)
    out = ruled_out.record_ruled_out(store, "r1", face_id="f1", person_id="p-cand")
    assert out["dry_run"] is True
    assert out["written"] is False
    dec = out["decision"]
    assert dec["kind"] == "reject"
    assert dec["policy_json"]["action"] == "ruled_out"
    assert dec["policy_json"]["person_id"] == "p-cand"
    assert dec["face_id"] == "f1"
    # no persons row → decisions.person_id stays None (FK-safe); candidate is in policy
    assert dec["person_id"] is None
    assert dec["cluster_id"] == "c1"

    conn = sqlite3.connect(str(store))
    n = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    conn.close()
    assert n == 0


def test_record_write_when_gate_and_not_dry_run(monkeypatch, tmp_path):
    monkeypatch.setenv("SEMBLON_GATE_RULED_OUT", "1")
    store = tmp_path / "s.sqlite"
    _seed(store)
    conn = sqlite3.connect(str(store))
    conn.execute(
        "INSERT INTO persons(person_id, display_name, status, created_run) VALUES (?,?,?,?)",
        ("p-cand", "Maya", "active", "r1"),
    )
    conn.commit()
    conn.close()

    out = ruled_out.record_ruled_out(
        store, "r1", cluster_id="c1", person_id="p-cand", dry_run=False
    )
    assert out["written"] is True
    assert out["dry_run"] is False
    did = out["decision_id"]

    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM decisions WHERE decision_id=?", (did,)).fetchone()
    assert row is not None
    assert row["kind"] == "reject"
    pol = json.loads(row["policy_json"])
    assert pol["action"] == "ruled_out"
    assert pol["subject"] == "cluster"
    assert pol["person_id"] == "p-cand"
    assert row["cluster_id"] == "c1"
    assert row["person_id"] == "p-cand"
    # no cluster identity mutation
    status = conn.execute(
        "SELECT status FROM clusters WHERE cluster_id=?", ("c1",)
    ).fetchone()[0]
    assert status == "auto"
    conn.close()


def test_record_cluster_unknown(monkeypatch, tmp_path):
    monkeypatch.setenv("SEMBLON_GATE_RULED_OUT", "1")
    store = tmp_path / "s.sqlite"
    _seed(store)
    with pytest.raises(ReviewError, match="unknown cluster"):
        ruled_out.record_ruled_out(store, "r1", cluster_id="missing")
