"""Application façade — RO board/activity + re-exported review apply_*."""

from __future__ import annotations

from semblon.application import activity, board
from semblon.observers import snapshot_memory_graph
from semblon.review import name_cluster, name_face
from tests.test_review import _clustered


def test_board_and_activity_are_read_only_facade(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    name_face(store, "r1", "f5", "Bob")
    snapshot_memory_graph(store, run_id="r1")

    board_rec = board(store, "r1")
    assert board_rec["run_id"] == "r1"
    assert "items" in board_rec
    assert "persons" in board_rec

    act = activity(store, "r1")
    assert act["track_count"] >= 0
    assert "groups" in act
    assert "relationships" in act
    assert "events" in act
    # Activity snapshot is observation-graph RO — not a person enrolment record.
    assert set(act) >= {"groups", "relationships", "events", "track_count"}
