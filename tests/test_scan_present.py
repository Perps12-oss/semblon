"""Scan card math. No invented percent or ETA."""

from __future__ import annotations

from semblon.scan_present import ScanPace, format_hms, scan_card, scan_meta, scan_stats, scan_title


def test_format_hms_keeps_hours_past_24():
    assert format_hms(65) == "0:01:05"
    assert format_hms(3600) == "1:00:00"
    assert format_hms(90061) == "25:01:01"
    assert format_hms(None) is None
    assert format_hms(-1) is None


def test_stats_omit_missing_counters():
    assert scan_stats(files_processed=3, files_total=10, faces_found=2) == (
        "3 of 10 files · 2 faces found"
    )
    assert scan_stats(files_processed=3, files_total=None, faces_found=None) == ""
    assert scan_stats(files_processed=None, files_total=None, faces_found=4) == "4 faces found"


def test_percent_requires_a_real_total():
    meta = scan_meta(
        files_processed=4,
        files_total=None,
        elapsed_s=10,
        paused=False,
        pace=None,
    )
    assert "%" not in meta
    assert "ETA" not in meta
    assert meta == "Elapsed 0:00:10"


def test_paused_meta_freezes_elapsed_and_hides_eta():
    pace = ScanPace()
    pace.observe(10, 20.0)
    running = scan_meta(
        files_processed=10,
        files_total=40,
        elapsed_s=20,
        paused=False,
        pace=pace,
    )
    assert "ETA" in running
    paused = scan_meta(
        files_processed=10,
        files_total=40,
        elapsed_s=20,
        paused=True,
        pace=pace,
    )
    assert paused == "Elapsed 0:00:20 · paused"
    assert "ETA" not in paused
    assert "%" not in paused


def test_eta_uses_ema_and_is_absent_without_a_rate():
    pace = ScanPace(alpha=0.1)
    assert pace.eta_s(0, 10) is None
    pace.observe(10, 10.0)
    assert pace.rate == 1.0
    assert pace.eta_s(10, 20) == 10.0
    pace.observe(20, 15.0)
    # instant rate = 10 files / 5 s = 2; ema = 0.1*2 + 0.9*1 = 1.1
    assert pace.rate == 1.1
    card = scan_card(
        stage="ingest",
        kind="progress",
        files_processed=20,
        files_total=30,
        faces_found=5,
        elapsed_s=15,
        pace=pace,
    )
    assert card["title"] == "Reading photos…"
    assert card["stats"] == "20 of 30 files · 5 faces found"
    assert card["meta"].startswith("66.7%, Elapsed 0:00:15 · ETA ")


def test_titles_match_the_deck_and_do_not_call_failure_completed():
    assert scan_title(stage="discover", kind="progress", paused=False) == "Scanning"
    assert scan_title(stage="ingest", kind="progress", paused=False) == "Reading photos…"
    assert scan_title(stage="ingest", kind="progress", paused=True) == "Paused"
    assert scan_title(stage="cluster", kind="completed", paused=False) == "Completed"
    assert scan_title(stage="ingest", kind="failed", paused=False) == "Couldn't finish"
    assert scan_title(stage="ingest", kind="cancelled", paused=True) == "Cancelled"
