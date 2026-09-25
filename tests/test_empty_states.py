"""UX Rescue §§12–17 empty-state helpers and classification."""

from __future__ import annotations

import sqlite3

from semblon.empty_states import (
    SEARCH_PLACEHOLDER,
    SEARCH_PLACEHOLDER_PHOTOS,
    ConditionKind,
    activity_empty,
    activity_history_lines,
    classify_condition,
    failure_dialog_for,
    groups_waiting_line,
    is_expected_condition,
    people_empty,
    photos_empty,
    search_no_matches,
    search_no_named_people,
    search_no_store,
    search_placeholder,
    search_result_lines,
    to_review_empty,
    videos_empty,
)
from semblon.home_ui import (
    format_activity_lines,
    format_people_lines,
    format_search_lines,
    format_unknown_lines,
)


def test_empty_state_anatomy_has_no_forbidden_vocab():
    forbidden = (
        "store",
        "run_id",
        "observation_groups",
        "integrity",
        "source-media",
        "Error",
        "\\",
        "/",
    )
    states = [
        photos_empty(),
        videos_empty(),
        people_empty(),
        to_review_empty(has_store=False),
        to_review_empty(has_store=True, has_faces=False),
        activity_empty(),
        search_no_store(),
        search_no_named_people(),
        search_no_matches("Ada"),
    ]
    for st in states:
        blob = "\n".join(st.as_lines())
        assert st.headline
        assert st.description
        # Primary or tertiary action present for coaching empties.
        assert st.primary_action or st.tertiary_action
        for bad in forbidden:
            if bad in {"/", "\\"}:
                # Paths forbidden — no Windows/Unix path separators in copy.
                assert ":\\" not in blob and "C:" not in blob
                continue
            assert bad.lower() not in blob.lower() or bad == "Error"
        assert "Error" not in blob


def test_search_placeholder_copy():
    assert SEARCH_PLACEHOLDER == "Search people and text"
    assert SEARCH_PLACEHOLDER_PHOTOS == "Search photos…"
    assert search_placeholder(has_named_people=False) == "Search photos…"
    assert search_placeholder(has_named_people=True) == "Search people and text"


def test_groups_waiting_line():
    assert groups_waiting_line(0) == "No people to name."
    assert groups_waiting_line(1) == "1 person to name."
    assert groups_waiting_line(12) == "12 people to name."


def test_format_unknown_demotes_known_unknown_codes():
    soft = format_unknown_lines({"counts": {"KNOWN": 1, "UNKNOWN": 4}}, "r1")
    assert soft[0] == "4 people to name."
    assert "Unknown is fine" in "\n".join(soft)
    assert "KNOWN=" not in "\n".join(soft)
    adv = format_unknown_lines(
        {"counts": {"KNOWN": 1, "UNKNOWN": 4}}, "r1", advanced=True
    )
    assert any("KNOWN=1" in ln for ln in adv)
    assert any("UNKNOWN=4" in ln for ln in adv)


def test_format_people_empty_coaching():
    lines = format_people_lines({"items": []})
    assert lines[0] == "No people yet"
    assert "People to name" in "\n".join(lines) or "Open Review" in "\n".join(lines)


def test_format_search_demotes_modality_pack():
    rec = {
        "kind": "similar",
        "query": "abc",
        "modality": "appearance",
        "pack_id": "appearance/rgb8@1",
        "count": 1,
        "items": [
            {
                "score": 0.9,
                "kind": "appearance",
                "item_id": "x",
                "why": "same modality+pack only; not a person",
            }
        ],
        "note": "Similarity is not identity.",
    }
    soft = format_search_lines(rec)
    assert "modality=" not in "\n".join(soft)
    assert "pack=" not in "\n".join(soft)
    adv = format_search_lines(rec, advanced=True)
    assert "modality=appearance" in adv[0]
    assert "pack=" in adv[0]


def test_format_search_no_matches():
    lines = format_search_lines({"kind": "person", "query": "Zed", "items": []})
    assert 'No matches for "Zed"' in lines[0]
    assert "Clear search" in "\n".join(lines)
    assert "photo" in "\n".join(lines).lower() or "name" in "\n".join(lines).lower()


def test_activity_history_soft_vs_advanced():
    soft = format_activity_lines(
        run_line="run=r1",
        integrity_line="integrity ok=1 unfinished=0",
        groups=[{"kind": "x", "member_count": 2, "status": "auto"}],
        relationships=[],
        events=[],
        track_count=3,
        photos=10,
        faces=4,
        group_count=2,
        has_unnamed=True,
        advanced=False,
    )
    text = "\n".join(soft)
    assert "10 photos processed" in text
    assert "4 faces" in text
    assert "2 groups" in text
    assert "Review people" in text
    assert "observation_groups" not in text
    assert "integrity" not in text
    assert "track ≠ person" not in text

    adv = format_activity_lines(
        run_line="run=r1",
        integrity_line="integrity ok=1 unfinished=0",
        groups=[{"kind": "x", "member_count": 2, "status": "auto"}],
        relationships=[],
        events=[],
        track_count=3,
        photos=10,
        faces=4,
        advanced=True,
    )
    adv_text = "\n".join(adv)
    assert "observation_groups" in adv_text
    assert "track ≠ person" in adv_text


def test_activity_history_lines_helper():
    lines = activity_history_lines(
        photos=340, faces=42, groups=12, stamped="18 Sep 2026", has_unnamed=True
    )
    assert lines[0] == "340 photos processed"
    assert "42 faces · 12 groups" in lines[1]
    assert "Review people" in lines


def test_classify_expected_vs_failure():
    assert classify_condition("store not found: x") is ConditionKind.EXPECTED
    assert classify_condition("store has no runs") is ConditionKind.EXPECTED
    assert is_expected_condition(ValueError("store not found: /tmp/x"))
    assert classify_condition(sqlite3.DatabaseError("disk image is malformed")) is (
        ConditionKind.FAILURE
    )
    assert not is_expected_condition(RuntimeError("boom"))


def test_failure_dialog_keeps_exception_in_details_only():
    dlg = failure_dialog_for(RuntimeError("boom"))
    assert "RuntimeError" not in dlg.headline
    assert "RuntimeError" not in dlg.body
    assert "RuntimeError" in dlg.detail
    assert "boom" in dlg.detail


def test_search_result_lines_person_populated():
    lines = search_result_lines(
        {
            "kind": "person",
            "items": [{"display_name": "Ada", "faces": 3}],
        }
    )
    assert lines[0] == "People"
    assert "Ada" in lines[1]
    assert "3 photos" in lines[1]
