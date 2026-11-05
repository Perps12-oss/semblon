"""G1 People: Named / Not sure / Not checked yet — no machine ACCEPT as a name."""

from __future__ import annotations

import sqlite3

from semblon.inbox import _bucket, inbox, people_identity_copy
from semblon.identify import identify_face
from semblon.review import name_cluster
from tests.test_review import _clustered


def test_people_copy_uses_ordinary_words():
    text = people_identity_copy(
        {"KNOWN": 2, "UNKNOWN": 1, "NOT_CHECKED": 3, "REVIEW_REQUIRED": 0}
    )
    assert "named" in text
    assert "not sure" in text
    assert "not checked yet" in text
    assert "UNKNOWN" not in text
    assert "NOT_CHECKED" not in text


def test_machine_accept_without_name_is_not_known():
    face = {"status": "ok", "person_id": None}
    decision = {
        "score_top1": 0.9,
        "score_top2": 0.1,
        "policy_json": '{"decision":"ACCEPT","threshold":0.6}',
    }
    assert _bucket(face, decision, {"outcome": "ACCEPT"}, 0.6) == "REVIEW_REQUIRED"


def test_inbox_distinguishes_not_checked_and_not_sure(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    # Before any identify: ok unnamed faces are not checked yet.
    before = inbox(store, "r1")
    assert before["counts"]["NOT_CHECKED"] >= 1
    assert "not checked yet" in before["people_copy"]

    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_cluster(store, "r1", assigned["f3"], "Bob")
    unknown = identify_face(store, "r1", "f5")
    assert unknown["decision"] == "UNKNOWN"

    after = inbox(store, "r1")
    by_id = {i["face_id"]: i["bucket"] for i in after["items"]}
    assert by_id["f1"] == "KNOWN"
    assert by_id["f5"] == "UNKNOWN"
    assert "not sure" in after["people_copy"]
    assert "KNOWN" not in after["people_copy"]  # ordinary wording only
