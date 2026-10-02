"""Home library shell presentation — honest capabilities, real counts."""

from __future__ import annotations

from pathlib import Path

from semblon.home_shell import (
    SHELL_HEADLINE,
    SHELL_SAVED_LINE,
    SHELL_SUBCOPY,
    capability_sections,
    enrich_summary_counts,
    last_result_copy,
    recent_activity_lines,
    shell_stats,
)
from semblon.library_status import library_summary
from semblon.review import name_cluster
from tests.test_review import _clustered


def test_shell_headline_matches_product_home():
    assert SHELL_HEADLINE == "Welcome to Semblon"
    assert "visual memory" in SHELL_SUBCOPY.lower()
    assert "facial" not in SHELL_SUBCOPY.lower()


def test_recent_activity_empty_is_quiet(tmp_path):
    lines = recent_activity_lines(tmp_path / "missing.sqlite")
    assert lines == ["No recent activity."]
    assert "Nothing matched" not in " ".join(lines)


def test_capability_sections_list_missing_models():
    sections = capability_sections(has_library_content=False, model_overrides={})
    ready_ids = {r["id"] for r in sections["ready"]}
    tracked_ids = {r["id"] for r in sections["tracked"]}
    assert "library_query" in ready_ids
    assert "saved_local" not in ready_ids
    assert "visual_embedding" in tracked_ids
    assert "ocr" in tracked_ids
    assert "vlm" in tracked_ids
    assert "ann_index" not in tracked_ids
    assert any(
        r["state"] == "Experimental" for r in sections["tracked"] if r["id"] == "vlm"
    )
    assert any(
        "Optional" in r["state"] or "install" in r["state"].lower()
        for r in sections["tracked"]
        if r["id"] == "visual_embedding"
    )


def test_capability_sections_add_saved_line_when_library_has_content():
    sections = capability_sections(has_library_content=True, model_overrides={})
    labels = [r["label"] for r in sections["ready"]]
    assert SHELL_SAVED_LINE in labels


def test_shell_stats_and_enrichment(tmp_path):
    store = tmp_path / "s.sqlite"
    assigned = _clustered(store)
    name_cluster(store, "r1", assigned["f1"], "Alice")
    base = library_summary(store)
    assert base is not None
    enriched = enrich_summary_counts(store, base)
    assert enriched is not None
    assert enriched["photos"] >= 1
    assert enriched["named_people"] == 1
    assert enriched["observations"] >= 1
    tiles = shell_stats(enriched)
    keys = [t["key"] for t in tiles]
    assert keys == ["photos", "video_frames", "named", "to_name", "observations"]
    named = next(t for t in tiles if t["key"] == "named")
    assert named["value"] == 1


def test_last_result_copy_is_honest():
    body, hint = last_result_copy(None)
    assert "Nothing has been asked" in body
    assert "Nothing matched" in hint
    fail_body, _ = last_result_copy(
        {"status": "UNAVAILABLE", "reason": "Open a photo first. Nothing was searched."}
    )
    assert "did not run" in fail_body.lower() or "Open a photo" in fail_body
    empty_body, _ = last_result_copy({"status": "NO_RESULT"})
    assert empty_body == "Nothing matched."
