"""Activity / Memory product surface — soft history, no schema leakage."""

from __future__ import annotations

import inspect

import pytest

from semblon.activity_surface import (
    ACTIVITY_HEADLINE,
    ACTIVITY_SUBCOPY,
    MOMENTS_EMPTY,
    SECTION_MOMENTS,
    SECTION_PROCESSING,
    SECTION_TOGETHER,
    TOGETHER_EMPTY,
    activity_workspace_sections,
    assert_no_schema_leak,
    format_activity_memory_lines,
    load_activity_memory,
    soft_moment_line,
    soft_together_line,
)
from semblon.application import activity_memory
from semblon.observers import snapshot_memory_graph
from semblon.review import name_cluster, name_face
from tests.test_memory import _prepare
from tests.test_review import _clustered


def test_soft_together_and_moment_lines_are_human():
    tog = soft_together_line(
        {
            "names": ["Alice", "Bob"],
            "folder": "lake",
            "when": "2026-05-09T14:06:04+00:00",
            "person_ids": ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"],
        }
    )
    assert tog is not None
    assert "Alice and Bob" in tog
    assert "lake" in tog
    assert "9 May 2026" in tog
    assert "person_id" not in tog
    assert "aaaaaaaa" not in tog

    burst = soft_moment_line(
        {
            "kind": "burst",
            "folder": "lake",
            "when": "2026-05-09T14:06:04+00:00",
            "media": 3,
            "person_ids": ["aaaaaaaaaaaaaaaa"],
        }
    )
    assert burst is not None
    assert "lake" in burst
    assert "person_id" not in burst
    assert "aaaaaaaa" not in burst

    day = soft_moment_line(
        {"kind": "day", "day": "2026-05-09", "people": 2, "media": 4}
    )
    assert day is not None
    assert "9 May 2026" in day
    assert "2 people" in day


def test_soft_together_drops_id_only_names():
    assert (
        soft_together_line(
            {"names": ["aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"], "folder": "lake"}
        )
        is None
    )


def test_activity_memory_empty_store(tmp_path):
    view = load_activity_memory(tmp_path / "missing.sqlite")
    assert view["empty"] is True
    lines = format_activity_memory_lines(view)
    text = "\n".join(lines)
    assert "No activity yet" in text
    assert_no_schema_leak(text)


def test_activity_memory_partial_without_named_people(tmp_path):
    store = tmp_path / "s.sqlite"
    _clustered(store)
    view = activity_memory(store, "r1")
    assert view["empty"] is False
    # Processing exists; together/moments need named people.
    assert view["partial"] is True or not view["together_lines"]
    lines = format_activity_memory_lines(view)
    text = "\n".join(lines)
    assert SECTION_PROCESSING in text
    assert SECTION_TOGETHER in text
    assert TOGETHER_EMPTY in text or view["together_lines"]
    assert SECTION_MOMENTS in text
    assert MOMENTS_EMPTY in text or view["moment_lines"]
    assert_no_schema_leak(text)
    for bad in (
        "person_id",
        "observation_groups",
        "relationships:",
        "track ≠ person",
        "pack_id",
        "buffalo",
        "media_id",
        "run_id",
    ):
        assert bad not in text


def test_activity_memory_populated_together_and_moments(tmp_path):
    store = tmp_path / "s.sqlite"
    _prepare(store)
    snapshot_memory_graph(store, run_id="r1")

    view = activity_memory(store, "r1")
    assert view["empty"] is False
    lines = format_activity_memory_lines(view)
    text = "\n".join(lines)
    assert SECTION_PROCESSING in text
    assert "photos processed" in text.lower() or "Processing complete" in text
    assert any("Alice" in row and "Bob" in row for row in view["together_lines"]) or (
        "Alice" in text and "Bob" in text
    )
    assert view["together_lines"] or view["moment_lines"]
    assert_no_schema_leak(text)
    for bad in ("person_id", "observation_groups", "evidence_json", "sqlite"):
        assert bad not in text.lower()

    sections = activity_workspace_sections(view)
    titles = [s["title"] for s in sections]
    assert SECTION_PROCESSING in titles
    assert SECTION_TOGETHER in titles
    assert SECTION_MOMENTS in titles


def test_activity_headline_and_subcopy_are_soft():
    assert ACTIVITY_HEADLINE == "Recent activity"
    assert "database" not in ACTIVITY_SUBCOPY.lower()
    assert "person_id" not in ACTIVITY_SUBCOPY
    assert "together" in ACTIVITY_SUBCOPY.lower()
    assert "moments" in ACTIVITY_SUBCOPY.lower()


def test_home_activity_uses_memory_facade_and_workspace():
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp)
    assert "_build_activity_workspace" in src
    assert "_show_activity_workspace" in src
    show = inspect.getsource(home_ui.HomeApp._show_activity)
    assert "activity_memory" in show
    assert "format_activity_lines(" not in show
    assert "observation_groups" not in show
