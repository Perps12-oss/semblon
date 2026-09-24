"""Status bar counts come from the library. No invented last-scan phrase."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from semblon.library_status import (
    library_summary,
    people_to_name_text,
    relative_time,
    review_people_cta,
    status_bar_text,
)
from semblon.review import name_cluster
from tests.test_review import _clustered


def test_missing_store_is_empty_not_zero():
    assert library_summary(Path("/no/such/store.sqlite")) is None
    assert status_bar_text(None) == ""


def test_people_to_name_phrase_is_one_noun():
    assert people_to_name_text(0) == "No people to name"
    assert people_to_name_text(1) == "1 person to name"
    assert people_to_name_text(133) == "133 people to name"
    assert review_people_cta(133) == "Review 133 people to name"
    assert "suggestion" not in review_people_cta(133).lower()
    assert "unnamed" not in people_to_name_text(133).lower()


def test_summary_counts_unconfirmed_groups(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    summary = library_summary(store)
    assert summary is not None
    assert summary["files"] == 2
    assert summary["faces"] == 5
    assert summary["unnamed_groups"] >= 1
    assert summary["named_people"] == 0
    before = summary["unnamed_groups"]
    name_cluster(store, "r1", assigned["f1"], "Alice")
    after = library_summary(store)
    assert after is not None
    assert after["unnamed_groups"] == before - 1
    assert after["named_people"] == 1
    line = status_bar_text(after)
    assert f"{after['files']} files · {after['faces']} faces · {people_to_name_text(after['unnamed_groups'])}" in line
    # Seed stamp is not a timestamp, so Last scan stays off the line.
    assert "Last scan" not in line
    assert "unnamed people" not in line


def test_relative_time_phrases():
    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    assert relative_time(None) is None
    assert relative_time("t") is None
    assert relative_time("2026-09-24T11:59:40+00:00", now=now) == "just now"
    assert relative_time("2026-09-24T11:00:00+00:00", now=now) == "1 hour ago"
    assert relative_time((now - timedelta(days=1, hours=2)).isoformat(), now=now) == "yesterday"
    stamped = status_bar_text(
        {"files": 3, "faces": 1, "unnamed_groups": 0, "last_scan": "2026-09-24T11:59:40+00:00"},
        now=now,
    )
    assert stamped == "3 files · 1 faces · No people to name · Last scan just now"
