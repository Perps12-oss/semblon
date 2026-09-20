"""User-facing progress copy. No InsightFace. No invented percent."""

from __future__ import annotations

import sqlite3

from semblon.desktop.copy import (
    COUNT_LABELS,
    KIND_LABELS,
    _looks_internal,
    basename,
    counts_line,
    current_item_line,
    friendly_exception,
    headline,
    kind_label,
    percent_text,
    status_lines,
    status_text,
    user_state,
)
from semblon.progress import (
    KIND_CANCELLED,
    KIND_COMPLETED,
    KIND_FAILED,
    KIND_PROGRESS,
    KIND_QUEUED,
    KIND_STALLED,
    KIND_STARTED,
    STAGE_CLUSTER,
    STAGE_INGEST,
    STAGE_PROCESS,
    make_event,
)


def test_no_percent_without_denominator():
    ev = make_event(
        STAGE_INGEST,
        KIND_PROGRESS,
        files_processed=4,
        clock="12:00:00",
    )
    assert percent_text(ev) is None
    line = counts_line(ev)
    assert line is not None
    assert "4 processed" in line
    assert "%" not in " ".join(status_lines(ev))


def test_current_without_total_is_processed_count():
    ev = make_event(STAGE_INGEST, KIND_PROGRESS, current=7, clock="12:00:00")
    assert counts_line(ev) == "7 processed"
    assert percent_text(ev) is None


def test_stalled_headline_and_reassurance():
    ev = make_event(STAGE_INGEST, KIND_STALLED, clock="12:00:00")
    lines = status_lines(ev)
    assert "Still working" in lines[0]
    assert any("still running" in ln.lower() for ln in lines)
    assert any("Cancel" in ln for ln in lines)


def test_integrity_error_does_not_claim_results_are_safe():
    user, detail = friendly_exception(sqlite3.IntegrityError("UNIQUE constraint failed"))
    blob = user.lower()
    assert "safe" not in blob
    assert "not been changed" not in blob
    assert "integrity" in blob
    assert "IntegrityError" in detail


def test_generic_exception_does_not_claim_results_are_safe():
    user, _detail = friendly_exception(RuntimeError("boom"))
    assert "safe" not in user.lower()
    assert "Semblon couldn't complete this operation." in user


def test_operational_error_is_not_reported_as_store_damage():
    user, detail = friendly_exception(sqlite3.OperationalError("database is locked"))
    assert "integrity check" not in user.lower()
    assert "OperationalError" in detail


def test_friendly_exception_file_and_permission_and_memory():
    user_f, _ = friendly_exception(FileNotFoundError("missing.jpg"))
    assert "could not be found" in user_f
    user_p, _ = friendly_exception(PermissionError("denied"))
    assert "permission" in user_p.lower()
    user_m, _ = friendly_exception(MemoryError("oom"))
    assert "out of memory" in user_m.lower()


def test_unknown_stage_falls_back_to_processing():
    ev = make_event("mystery", KIND_STARTED, clock="12:00:00")
    assert user_state(ev) == "Processing"
    assert headline(ev).startswith("Processing")


def test_unknown_count_keys_are_ignored_by_design():
    ev = make_event(
        STAGE_PROCESS,
        KIND_PROGRESS,
        counts={"photos": 3, "secret_internal": 9, "clusters": 2},
        clock="12:00:00",
    )
    line = counts_line(ev) or ""
    assert "3 photos" in line
    assert "2 groups" in line
    assert "secret_internal" not in line
    assert "secret_internal" not in COUNT_LABELS


def test_ingest_count_keys_are_user_visible():
    ev = make_event(
        STAGE_INGEST,
        KIND_PROGRESS,
        counts={
            "new_media": 3,
            "skipped_same_run": 2,
            "ok": 5,
            "low_quality": 1,
            "rejected": 1,
        },
        clock="12:00:00",
    )
    line = counts_line(ev) or ""
    assert "3 new media" in line
    assert "2 already in this run" in line
    assert "5 ok faces" in line
    assert "1 low-quality" in line
    assert "1 rejected" in line


def test_kind_labels_are_wired():
    assert kind_label(KIND_QUEUED) == KIND_LABELS[KIND_QUEUED]
    ev = make_event(STAGE_PROCESS, KIND_QUEUED, clock="12:00:00")
    assert "Queued" in headline(ev)


def test_percent_is_in_status_lines_when_real():
    ev = make_event(
        STAGE_INGEST,
        KIND_PROGRESS,
        files_processed=3,
        files_total=10,
        percent=30.0,
        clock="12:00:00",
    )
    lines = status_lines(ev)
    assert any(ln == "30%" for ln in lines)


def test_current_item_is_prefixed():
    ev = make_event(STAGE_CLUSTER, KIND_PROGRESS, path=r"C:\photos\a.jpg", clock="12:00:00")
    assert current_item_line(ev) == "Current: a.jpg"
    ingest = make_event(STAGE_INGEST, KIND_PROGRESS, path="/folder/b.png", clock="12:00:00")
    assert current_item_line(ingest) == "Current: b.png"


def test_basename_handles_empty_and_trailing_slash():
    assert basename(None) == ""
    assert basename("") == ""
    assert basename("/photos/") == "photos"
    assert basename(r"C:\photos\\") == "photos"


def test_cancelled_does_not_claim_partial_results_exist():
    ev = make_event(STAGE_INGEST, KIND_CANCELLED, clock="12:00:00")
    text = " ".join(status_lines(ev))
    assert "Any partial results have been retained." in text
    assert kind_label(KIND_CANCELLED) in headline(ev)


def test_status_text_joins_lines():
    ev = make_event(STAGE_INGEST, KIND_PROGRESS, files_processed=1, files_total=2, clock="12:00:00")
    text = status_text(ev)
    assert "Reading photos" in text or "…" in text
    assert "50%" in text or "1 of 2" in text


def test_failed_error_is_labeled_detail():
    ev = make_event(STAGE_INGEST, KIND_FAILED, error="sqlite boom " * 40, clock="12:00:00")
    lines = status_lines(ev)
    assert lines[0] == "Couldn't finish"
    assert any(ln.startswith("Detail: ") for ln in lines)
    detail = next(ln for ln in lines if ln.startswith("Detail: "))
    assert len(detail) <= 8 + 180


def test_completed_has_no_ellipsis():
    ev = make_event(STAGE_INGEST, KIND_COMPLETED, files_processed=2, files_total=2, clock="12:00:00")
    assert "…" not in headline(ev)
    assert headline(ev).endswith("done")


def test_internal_message_filter_and_friendly_values():
    assert _looks_internal("ingest:progress")
    assert _looks_internal("working")
    assert not _looks_internal("reading photos in D:/pics")
