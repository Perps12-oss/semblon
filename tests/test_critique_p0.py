"""Critique P0: inbox, tracks, search correctness."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.inbox import _bucket, inbox
from semblon.search import _like_pattern, search_face, search_person
from semblon.tracks import derive_tracks, stable_track_id
from tests.test_cluster import _seed
from tests.test_tracks import _seed as _seed_tracks


def test_stable_track_id_ignores_order():
    a = stable_track_id("m1", ["fb", "fa"])
    b = stable_track_id("m1", ["fa", "fb"])
    assert a == b
    assert a.startswith("t-m1-")
    assert stable_track_id("m1", ["fa"]) != stable_track_id("m1", ["fa", "fb"])


def test_track_id_stable_across_derive(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_tracks(store)
    a = derive_tracks(store, "rt")
    b = derive_tracks(store, "rt")
    ids_a = sorted(t["track_id"] for t in a["tracks"])
    ids_b = sorted(t["track_id"] for t in b["tracks"])
    assert ids_a == ids_b
    # Membership hash, not first face_id alone.
    left = next(t for t in a["tracks"] if t["face_ids"] == ["fa", "fb"])
    assert left["track_id"] == stable_track_id("mv1", ["fa", "fb"])
    assert left["track_id"] != "t-mv1-fa"


def test_inbox_named_low_quality_is_known(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed(store).close()
    # Stamp person_id on low_quality f7 without name_face (name requires status=ok).
    conn = sqlite3.connect(str(store))
    conn.execute(
        """INSERT INTO persons(person_id, display_name, status, created_run)
           VALUES ('p-soft','Soft','active','r1')"""
    )
    conn.execute("UPDATE faces SET person_id='p-soft' WHERE face_id='f7'")
    conn.commit()
    conn.close()
    rec = inbox(store, "r1")
    by_id = {i["face_id"]: i["bucket"] for i in rec["items"]}
    assert by_id["f7"] == "KNOWN"
    face = {"status": "low_quality", "person_id": "p1"}
    assert _bucket(face, None, 0.6) == "KNOWN"


def test_search_face_does_not_write_decision(tmp_path):
    from tests.test_review import _clustered
    from semblon.review import name_cluster

    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    conn = sqlite3.connect(str(store))
    before = conn.execute(
        "SELECT COUNT(*) FROM decisions WHERE kind='identify'"
    ).fetchone()[0]
    conn.close()
    out = search_face(store, "r1", "f2")
    assert out["identify"]["recorded"] is False
    assert out["identify"]["decision_id"] is None
    conn = sqlite3.connect(str(store))
    after = conn.execute(
        "SELECT COUNT(*) FROM decisions WHERE kind='identify'"
    ).fetchone()[0]
    conn.close()
    assert after == before


def test_like_pattern_escapes_percent():
    assert _like_pattern("100%") == r"%100\%%"
    assert _like_pattern("a_b") == r"%a\_b%"


def test_search_person_why_fields(tmp_path):
    from tests.test_review import _clustered
    from semblon.review import name_cluster

    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    rec = search_person(store, "Alice")
    assert rec["items"][0]["why"] == "display_name exact"
    pid = rec["items"][0]["person_id"]
    by_id = search_person(store, pid)
    assert by_id["items"][0]["why"] == "person_id exact"
