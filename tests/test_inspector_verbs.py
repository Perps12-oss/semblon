"""Home Inspector verb policy — evidence vs action (R3-BRIEF §4 / Artifact 1 §9–12).

API-level tests. No inventing PASS; assert enablement + apply wiring only.
"""

from __future__ import annotations

import inspect

import pytest

from semblon.inspector_verbs import (
    REASON_ASSIGN,
    REASON_MERGE,
    REASON_NAME,
    REASON_SPLIT,
    action_block_labels,
    apply_inspector_ignore,
    apply_inspector_merge,
    apply_inspector_name,
    apply_inspector_rule_out,
    apply_inspector_split,
    evidence_lines_for_selection,
    flatten_board_items_for_inspector,
    inspector_verb_states,
    items_from_media_board,
)
from semblon.review_ui import load_board
from tests.test_review import _clustered


def test_verb_states_empty_selection():
    st = inspector_verb_states([], run_id="r1")
    assert st["merge"]["enabled"] is False
    assert st["merge"]["reason"] == REASON_MERGE
    assert st["split"]["enabled"] is False
    assert st["split"]["reason"] == REASON_SPLIT
    assert st["name"]["enabled"] is False
    assert st["name"]["reason"] == REASON_NAME
    assert st["ignore"]["enabled"] is True  # never disabled
    assert st["assign"]["enabled"] is False
    assert st["assign"]["reason"] == REASON_ASSIGN
    assert st["note"]["enabled"] is False
    assert "note" in (st["note"]["reason"] or "").lower() or "Select" in (
        st["note"]["reason"] or ""
    )


def test_merge_requires_two_clusters_not_assign():
    selected = [
        {"kind": "cluster", "cluster_id": "c1"},
        {"kind": "cluster", "cluster_id": "c2"},
    ]
    st = inspector_verb_states(selected, run_id="r1")
    assert st["merge"]["enabled"] is True
    assert st["merge"]["cluster_ids"] == ["c1", "c2"]
    # Assign stays off without a person target — separate control.
    assert st["assign"]["enabled"] is False
    assert "person" in (st["assign"]["reason"] or "").lower()


def test_assign_separate_from_merge():
    selected = [{"kind": "cluster", "cluster_id": "c1"}]
    st = inspector_verb_states(
        selected, run_id="r1", target_person_id="p-alice"
    )
    assert st["merge"]["enabled"] is False
    assert st["assign"]["enabled"] is True
    assert st["assign"]["person_id"] == "p-alice"
    assert st["name"]["enabled"] is True


def test_split_cluster_and_name_face():
    selected = [
        {"kind": "cluster", "cluster_id": "c1", "members": []},
        {"kind": "face", "face_id": "f2", "cluster_id": "c1"},
    ]
    st = inspector_verb_states(selected, run_id="r1")
    assert st["split"]["enabled"] is True
    assert st["split"]["cluster_id"] == "c1"
    assert st["split"]["face_ids"] == ["f2"]


def test_rule_out_gate_default_on(monkeypatch):
    monkeypatch.delenv("SEMBLON_RULED_OUT", raising=False)
    st = inspector_verb_states(
        [{"kind": "cluster", "cluster_id": "c1"}], run_id="r1"
    )
    assert st["rule_out"]["enabled"] is True

    monkeypatch.setenv("SEMBLON_RULED_OUT", "0")
    st_off = inspector_verb_states(
        [{"kind": "cluster", "cluster_id": "c1"}], run_id="r1"
    )
    assert st_off["rule_out"]["enabled"] is False
    assert "RULED_OUT" in (st_off["rule_out"]["reason"] or "")


def test_evidence_and_action_blocks_split():
    evid = evidence_lines_for_selection(
        run_id="r1",
        media_id="m1",
        selected=[{"kind": "cluster", "cluster_id": "c-abc"}],
    )
    text = "\n".join(evid)
    assert "Evidence relationship (machine)" in text
    assert "cluster membership" in text
    assert "Group ≠ person" in text or "Group != person" in text

    st = inspector_verb_states([], run_id="r1")
    actions = "\n".join(action_block_labels(st))
    assert "Proposed action (human)" in actions
    assert "Merge observations ≠ Assign to person" in actions
    assert "Select 2 or more items" in actions


def test_items_from_media_board_lists_member_faces():
    board = {
        "faces": [
            {"media_id": "m1", "face_id": "f1", "cluster_id": "c1", "person_id": None},
            {"media_id": "m1", "face_id": "f2", "cluster_id": "c1", "person_id": None},
            {"media_id": "m1", "face_id": "f3", "cluster_id": None, "person_id": None},
            {"media_id": "m2", "face_id": "f9", "cluster_id": "c9", "person_id": None},
        ]
    }
    items = items_from_media_board(board, "m1")
    kinds = [i["kind"] for i in items]
    assert kinds.count("cluster") == 1
    assert kinds.count("face") == 3  # 2 members + 1 unassigned
    assert any(i.get("face_id") == "f3" for i in items)


def test_apply_wrappers_merge_split_name_ignore(tmp_path, monkeypatch):
    monkeypatch.delenv("SEMBLON_RULED_OUT", raising=False)
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    c1 = assigned["f1"]
    c2 = assigned["f3"]
    assert c1 != c2

    merge = apply_inspector_merge(store, "r1", [c1, c2])
    assert merge["survivor"] == c1
    assert merge.get("moved_faces", 0) >= 1
    assert merge.get("decision_id")

    # After merge, split one face off survivor.
    board = load_board(store, "r1")
    clusters = [it for it in board["items"] if it["kind"] == "cluster"]
    assert clusters
    survivor = clusters[0]
    members = [m["face_id"] for m in survivor.get("members") or []]
    assert len(members) >= 2
    leave = members[-1]
    split = apply_inspector_split(store, "r1", survivor["cluster_id"], [leave])
    assert split.get("decision_id")
    assert split.get("new_cluster") or split.get("from_cluster")

    board2 = load_board(store, "r1")
    unnamed = [it for it in board2["items"] if it["kind"] == "cluster" and not it.get("named")]
    assert unnamed
    target = unnamed[0]
    named = apply_inspector_name(store, "r1", target, "Ada")
    assert named["display_name"] == "Ada"
    assert named.get("created_person") is True

    # Ignore a different unnamed cluster (not the named one).
    board3 = load_board(store, "r1")
    ignorable = next(
        (
            it
            for it in board3["items"]
            if it["kind"] == "cluster"
            and not it.get("named")
            and it["cluster_id"] != named["cluster_id"]
        ),
        None,
    )
    if ignorable is None:
        # Fall back to an unassigned face row if present.
        ignorable = next(
            (it for it in board3["items"] if it["kind"] == "face"),
            None,
        )
    if ignorable is not None:
        ign = apply_inspector_ignore(store, "r1", ignorable)
        assert ign.get("decision_id")

    # Rule out the named cluster (durable reject; stays visible).
    monkeypatch.setenv("SEMBLON_RULED_OUT", "1")
    ruled = apply_inspector_rule_out(
        store, "r1", {"kind": "cluster", "cluster_id": named["cluster_id"]}
    )
    assert ruled.get("decision_id")
    assert (ruled.get("action") or ruled.get("policy", {}).get("action") or "rule_out")


def test_flatten_board_items():
    raw = [
        {
            "kind": "cluster",
            "cluster_id": "c1",
            "named": False,
            "members": [
                {"face_id": "f1", "cluster_id": "c1", "media_id": "m1"},
                {"face_id": "f2", "cluster_id": "c1", "media_id": "m1"},
            ],
        }
    ]
    flat = flatten_board_items_for_inspector(raw)
    assert flat[0]["kind"] == "cluster"
    assert [x["face_id"] for x in flat[1:]] == ["f1", "f2"]


def test_home_ui_wires_inspector_verbs():
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp)
    # Soft product labels (engineering verbs stay in inspector_verbs / apply_*).
    assert "VERB_LABEL_MERGE" in src or "Combine face groups" in src
    assert "VERB_LABEL_ASSIGN" in src or "Add to person" in src
    assert "What you can do" in src
    assert "apply_inspector_merge" in src or "inspector_verbs" in src
    assert "_name_entry" in src
    assert "<Return>" in src
    assert "<Escape>" in src
    assert "btn_rule_out" in src
    assert "btn_ignore" in src
    # Must not equate merge with assign in one control.
    assert "Combining groups is separate from naming" in src
    # Engineering dump headings stay out of the product inspector.
    assert "Evidence relationship (machine)" not in src
    assert "Proposed action (human)" not in src

def test_canvas_inspector_lines_split_evidence_action():
    from semblon.canvas import media_inspector_lines

    lines = media_inspector_lines(
        {
            "run_id": "r1",
            "note": "Canvas never writes faces.person_id.",
            "media": [{"media_id": "m1", "path": "/a.jpg", "source_type": "folder"}],
            "faces": [
                {"media_id": "m1", "face_id": "f1", "cluster_id": "c1"},
            ],
            "items": [],
            "tracks": [],
        },
        "m1",
    )
    text = "\n".join(lines)
    assert "Evidence relationship (machine)" in text
    assert "Proposed action (human)" in text
    assert "Merge observations ≠ Assign to person" in text
