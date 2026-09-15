"""FACE-004 identify vs persons — no InsightFace."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from semblon.cli import main
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
    assert main(["identify", "--run", "r1", "--store", str(store)]) == 2
    assert main(["identify", "--face", "f2", "--image", "x.jpg", "--run", "r1", "--store", str(store)]) == 2


def test_process_arch_x64_on_arm64_is_emulated():
    from semblon.engine import process_arch, process_execution
    import os

    arch = process_arch()
    exe = process_execution()
    assert arch in {"x64", "arm64"}
    if os.environ.get("PROCESSOR_ARCHITECTURE", "").upper() == "ARM64" and arch == "x64":
        assert exe == "emulated"
