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


def test_shell_decision_packet_stays_unnamed():
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "docs" / "r3-artifacts" / "07-shell-decision.md"
    text = path.read_text(encoding="utf-8")
    assert "Winner | _none yet_" in text or "Winner | `_none yet_`" in text or "_none yet_" in text
    # Decision record must not claim a toolkit.
    assert "Winner | WinUI" not in text
    assert "Winner | Qt" not in text
    assert "Winner | PySide" not in text
