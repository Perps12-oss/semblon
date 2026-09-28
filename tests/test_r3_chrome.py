"""R3 chrome vocabulary — toolkit-agnostic display + processing grammar."""

from __future__ import annotations

import pytest

from semblon.r3_chrome import (
    DISPLAY_STATES,
    SHELL_CHROME_NOTE,
    chrome_legend_lines,
    decision_from_face,
    display_state,
    evidence_from_face,
    face_display_state,
    face_evidence_label,
    processing_glyph,
)
from semblon.ui_copy import process_event_snapshot
from semblon.progress import ProgressEvent, KIND_PROGRESS, STAGE_INGEST


def test_five_display_states_and_matrix():
    assert DISPLAY_STATES == (
        "Unknown",
        "Possible",
        "Confirmed",
        "Ruled out",
        "Ignored",
    )
    assert display_state("none", "undecided") == "Unknown"
    assert display_state("clustered", "undecided") == "Possible"
    assert display_state("similar", "affirmed") == "Confirmed"
    assert display_state("detected", "rejected") == "Ruled out"
    assert display_state("none", "deferred") == "Ignored"
    with pytest.raises(ValueError, match="impossible"):
        display_state("none", "affirmed")


def test_face_axes_do_not_smuggle_person_into_evidence():
    face = {"face_id": "f1", "bbox_x1": 0, "person_id": "p1", "cluster_id": None}
    assert evidence_from_face(face) == "detected"
    assert decision_from_face(face) == "affirmed"
    assert face_display_state(face) == "Confirmed"
    assert face_evidence_label({"cluster_id": "c1"}) == "clustered"
    assert face_display_state({"cluster_id": "c1"}, policy_action="rule_out") == "Ruled out"
    assert face_display_state({"face_id": "f"}, policy_action="ignore") == "Ignored"


def test_caller_similarity_is_evidence_not_identity():
    """Caller scores change the evidence token only. They do not enrol anyone."""
    from semblon.canvas import face_evidence_tag

    scored = {"face_id": "f", "similarity": 0.71}
    assert evidence_from_face(scored) == "similar"
    assert "person_id" not in scored
    assert decision_from_face(scored) == "undecided"
    assert face_display_state(scored) == "Possible"
    assert face_evidence_tag(scored) == "similar"

    assert evidence_from_face({"face_id": "f", "similar_score": 0.55}) == "similar"
    assert evidence_from_face({"face_id": "f", "candidate_score": "0.2"}) == "similar"
    assert face_display_state({"face_id": "f", "similar_score": 0.55}) == "Possible"

    bare = {"face_id": "f", "bbox_x1": 0}
    assert evidence_from_face(bare) == "detected"
    assert face_display_state(bare) == face_display_state(scored)
    assert evidence_from_face({"face_id": "f", "similarity": 0}) == "detected"
    assert evidence_from_face({"face_id": "f", "similarity": -0.4}) == "detected"
    assert evidence_from_face({"face_id": "f", "similar_score": ""}) == "detected"
    assert evidence_from_face({"face_id": "f", "candidate_score": None}) == "detected"
    assert evidence_from_face({"face_id": "f", "similarity": "high"}) == "detected"
    assert evidence_from_face({"face_id": "f", "similarity": True}) == "detected"

    clustered = {"face_id": "f", "cluster_id": "c", "similarity": 0.99}
    assert evidence_from_face(clustered) == "clustered"
    assert "person_id" not in clustered
    assert decision_from_face(clustered) == "undecided"

    named = {"face_id": "f", "person_id": "p", "similarity": 0.9}
    assert evidence_from_face(named) == "similar"
    assert named["person_id"] == "p"
    assert decision_from_face(named) == "affirmed"
    assert face_display_state(named) == face_display_state({"face_id": "f", "person_id": "p"})
    assert decision_from_face({"face_id": "f", "candidate_score": 0.99}) == "undecided"
    assert face_display_state({"face_id": "f", "candidate_score": 0.99}) != "Confirmed"
    assert evidence_from_face({"face_id": "f", "status": "low_quality", "similarity": 0.9}) == "none"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.8, "similar"),
        ("0.8", "similar"),
        (1, "similar"),
        ("1", "similar"),
        (0, "detected"),
        ("0", "detected"),
        (-0.2, "detected"),
        ("-0.2", "detected"),
        (True, "detected"),
        (False, "detected"),
        ("", "detected"),
        (None, "detected"),
        ("high", "detected"),
        ("abc", "detected"),
    ],
)
def test_caller_similarity_type_boundary(value, expected):
    face = {"face_id": "f", "bbox_x1": 1, "similarity": value}
    assert evidence_from_face(face) == expected
    assert face == {"face_id": "f", "bbox_x1": 1, "similarity": value}
    assert "person_id" not in face


def test_caller_similarity_does_not_decide_identity():
    clustered = {"face_id": "f", "cluster_id": "c9", "similarity": 0.8}
    assert evidence_from_face(clustered) == "clustered"
    assert clustered["cluster_id"] == "c9"
    assert "person_id" not in clustered
    assert decision_from_face(clustered) == "undecided"

    only_person = {"face_id": "f", "person_id": "p1"}
    assert evidence_from_face(only_person) == "detected"
    assert only_person == {"face_id": "f", "person_id": "p1"}

    ignored = {"face_id": "f", "similarity": 0.8}
    assert evidence_from_face(ignored) == "similar"
    assert decision_from_face(ignored, policy_action="ignore") == "deferred"
    assert face_display_state(ignored, policy_action="ignore") == "Ignored"

    ruled = {"face_id": "f", "candidate_score": "0.8"}
    assert evidence_from_face(ruled) == "similar"
    assert decision_from_face(ruled, policy_action="rule_out") == "rejected"
    assert face_display_state(ruled, policy_action="rule_out") == "Ruled out"
    assert "person_id" not in ruled
    assert face_display_state(ruled) == "Possible"


def test_processing_glyph_shape_not_hue():
    assert processing_glyph("queued") == "hollow-ring"
    assert processing_glyph("progress") == "partial-ring-sweep"
    assert processing_glyph("progress", paused=True) == "partial-ring-paused"
    assert processing_glyph("failed") == "ring-gap-bang"
    assert processing_glyph("cancelled") == "hollow-ring-slash"
    assert processing_glyph("stalled") == "dotted-ring"


def test_chrome_legend_does_not_name_toolkit():
    text = "\n".join(chrome_legend_lines())
    assert "Unknown" in text
    assert "Ruled out" in text
    assert "WinUI" not in text
    assert "Qt" not in text
    assert "PySide" not in text
    assert "AppShell" in SHELL_CHROME_NOTE


def test_process_snapshot_includes_processing_glyph():
    ev = ProgressEvent(
        stage=STAGE_INGEST,
        kind=KIND_PROGRESS,
        files_processed=1,
        files_total=10,
    )
    snap = process_event_snapshot(ev)
    assert snap["processing_glyph"] == "partial-ring-sweep"
    assert "Qt" not in snap["headline"]


def test_shell_decision_packet_closed_native_authorized():
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "docs" / "r3-artifacts" / "07-shell-decision.md"
    text = path.read_text(encoding="utf-8")
    assert "CLOSED / DONE" in text
    assert "native" in text.lower()
    # Still refuse naming a specific toolkit winner row.
    assert "Winner | WinUI" not in text
    assert "Winner | Qt" not in text
    assert "Winner | PySide" not in text
