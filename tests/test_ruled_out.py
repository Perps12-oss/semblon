"""Ruled out scaffold — flag ON writes reject+action=rule_out; flag OFF refuses."""

from __future__ import annotations

import json
import os
import sqlite3
import struct
from pathlib import Path

import pytest

from semblon.cli import main
from semblon.cluster import cluster_run
from semblon.review import (
    ReviewError,
    ignore_subject,
    rule_out_subject,
    ruled_out_enabled,
)
from semblon.review_ui import apply_rule_out
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
    for fid, oid, emb, st in faces:
        conn.execute(
            """INSERT INTO faces(
                 face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                 det_score, face_w, face_h, size_band, blur, landmarks_json,
                 embedding, embedding_pack, embedding_dim, status, cluster_id, person_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fid,
                oid,
                "r1",
                0,
                0,
                10,
                10,
                0.9,
                10,
                10,
                "ok",
                None,
                "[]",
                emb,
                "pack-a",
                2,
                st,
                None,
                None,
            ),
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
    return {fid: cid for fid, cid in rows}


@pytest.fixture(autouse=True)
def _clear_flag(monkeypatch):
    monkeypatch.delenv("SEMBLON_RULED_OUT", raising=False)


def test_flag_defaults_on():
    assert ruled_out_enabled() is True


def test_rule_out_refuses_when_opted_out(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    monkeypatch.setenv("SEMBLON_RULED_OUT", "0")
    with pytest.raises(ReviewError, match="disabled"):
        rule_out_subject(store, "r1", cluster_id=c1)

def test_rule_out_cluster_writes_reject_action(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMBLON_RULED_OUT", "1")
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    rec = rule_out_subject(store, "r1", cluster_id=c1, text="not Maya")
    assert rec["action"] == "rule_out"
    assert rec["person_id"] is None

    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT kind, person_id, policy_json, cluster_id FROM decisions WHERE decision_id=?",
        (rec["decision_id"],),
    ).fetchone()
    status = conn.execute(
        "SELECT status FROM clusters WHERE cluster_id=?", (c1,)
    ).fetchone()[0]
    conn.close()

    assert row["kind"] == "reject"
    assert row["cluster_id"] == c1
    pol = json.loads(row["policy_json"])
    assert pol["action"] == "rule_out"
    assert pol["subject"] == "cluster"
    assert pol["text"] == "not Maya"
    assert status != "ignored"


def test_rule_out_distinct_from_ignore(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMBLON_RULED_OUT", "1")
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    rule_out_subject(store, "r1", cluster_id=c1)
    ignore_subject(store, "r1", cluster_id=c2)

    conn = sqlite3.connect(str(store))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT cluster_id, policy_json FROM decisions WHERE kind='reject' ORDER BY created_at"
    ).fetchall()
    st1 = conn.execute("SELECT status FROM clusters WHERE cluster_id=?", (c1,)).fetchone()[0]
    st2 = conn.execute("SELECT status FROM clusters WHERE cluster_id=?", (c2,)).fetchone()[0]
    conn.close()

    actions = {r["cluster_id"]: json.loads(r["policy_json"])["action"] for r in rows}
    assert actions[c1] == "rule_out"
    assert actions[c2] == "ignore"
    assert st1 != "ignored"
    assert st2 == "ignored"


def test_rule_out_face_and_optional_person(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMBLON_RULED_OUT", "1")
    store = tmp_path / "s.sqlite"
    _clustered(store)
    conn = sqlite3.connect(str(store))
    conn.execute(
        "INSERT INTO persons(person_id, display_name, status, created_run) VALUES (?,?,?,?)",
        ("p-maya", "Maya", "active", "r1"),
    )
    conn.commit()
    conn.close()

    rec = rule_out_subject(store, "r1", face_id="f5", person_id="p-maya")
    assert rec["person_id"] == "p-maya"
    conn = sqlite3.connect(str(store))
    pol = json.loads(
        conn.execute(
            "SELECT policy_json FROM decisions WHERE decision_id=?",
            (rec["decision_id"],),
        ).fetchone()[0]
    )
    person = conn.execute(
        "SELECT person_id FROM decisions WHERE decision_id=?",
        (rec["decision_id"],),
    ).fetchone()[0]
    conn.close()
    assert pol["action"] == "rule_out"
    assert pol["subject"] == "face"
    assert pol["hidden"] is False
    assert pol["target_person_id"] == "p-maya"
    assert person == "p-maya"


def test_apply_rule_out_wrapper(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMBLON_RULED_OUT", "1")
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    rec = apply_rule_out(store, "r1", {"kind": "cluster", "cluster_id": c1})
    assert rec["action"] == "rule_out"


def test_cli_rule_out_refuses_when_opted_out(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    monkeypatch.setenv("SEMBLON_RULED_OUT", "0")
    assert (
        main(
            [
                "review",
                "--run",
                "r1",
                "--store",
                str(store),
                "rule-out",
                "--cluster",
                c1,
            ]
        )
        == 2
    )


def test_cli_rule_out_with_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("SEMBLON_RULED_OUT", "1")
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    assert (
        main(
            [
                "review",
                "--run",
                "r1",
                "--store",
                str(store),
                "rule-out",
                "--cluster",
                c1,
            ]
        )
        == 0
    )
    conn = sqlite3.connect(str(store))
    pol = json.loads(
        conn.execute(
            "SELECT policy_json FROM decisions WHERE kind='reject' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0]
    )
    conn.close()
    assert pol["action"] == "rule_out"
