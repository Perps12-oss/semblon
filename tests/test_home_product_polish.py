"""Home product polish — Settings / Search / People / Unknown / P2 states."""

from __future__ import annotations

import inspect

from semblon.empty_states import (
    disabled_while_busy,
    loading_workspace,
    people_empty,
    search_no_matches,
    search_result_lines,
    search_text_error,
    search_text_unavailable,
)
from semblon.home_ui import format_people_lines, format_search_lines, format_unknown_lines
from semblon.product_surface import (
    settings_forbidden_product_vocab,
    settings_product_section_titles,
    soft_people_header_lines,
    soft_unknown_coach_lines,
)


def test_settings_product_sections_exclude_engineering_vocab():
    titles = settings_product_section_titles()
    assert titles == ("Library & Storage", "Local Capabilities", "Appearance & Privacy", "About")
    for bad in settings_forbidden_product_vocab():
        assert bad not in " ".join(titles)


def test_home_settings_separates_advanced_and_diagnostics():
    import semblon.home_ui as home_ui
    from semblon.product_surface import (
        SETTINGS_ADVANCED,
        SETTINGS_DIAGNOSTICS,
        SETTINGS_OPEN_DIAGNOSTICS,
    )

    src = inspect.getsource(home_ui.HomeApp._fill_settings_body)
    assert "SETTINGS_DIAGNOSTICS" in src
    assert "SETTINGS_ADVANCED" in src
    assert "SETTINGS_OPEN_DIAGNOSTICS" in src
    assert "SETTINGS_EXPORT_REVIEW" not in src
    assert "_open_html" not in src
    assert SETTINGS_DIAGNOSTICS == "Diagnostics"
    assert SETTINGS_ADVANCED == "Advanced"
    assert "diagnostics" in SETTINGS_OPEN_DIAGNOSTICS.lower()
    for bad in (
        "format_execution_status_lines",
        "weights_status",
        "buffalo_l",
        "schema_version",
        "modality_product_settings_lines",
        "JobEngine",
        "Toplevel",
        "_settings_win",
    ):
        assert bad not in src
    show = inspect.getsource(home_ui.HomeApp._show_settings)
    assert "Toplevel" not in show
    assert "_settings_win" not in show
    import semblon.product_features as pf

    assert "_navigate(\"settings\")" in inspect.getsource(pf._cmd_open_settings)

def test_search_hierarchy_empty_unavailable_error_result():
    empty = search_no_matches("Ada")
    assert "Ada" in empty.headline
    assert "person name" in empty.description.lower() or "photo" in empty.description.lower()
    assert "Error" not in empty.headline

    unavail = search_text_unavailable(
        reason="No readable text is stored in this library yet."
    )
    assert "unavailable" in unavail.headline.lower()
    assert "ocr" not in unavail.headline.lower()
    assert "capability" not in "\n".join(unavail.as_lines()).lower()

    err = search_text_error(reason="Temporary failure")
    assert "Couldn't" in err.headline
    assert "Error" not in err.headline

    lines = search_result_lines(
        {
            "kind": "text",
            "query": "hello",
            "count": 1,
            "status": "SUCCESS",
            "items": [{"text": "hello world", "item_id": "t1"}],
        }
    )
    assert any("Text in photos" in ln for ln in lines)
    assert "hello world" in "\n".join(lines)
    assert "ocr" not in "\n".join(lines).lower()


def test_search_similar_soft_copy_avoids_ann_theatre():
    soft = search_result_lines(
        {
            "kind": "similar",
            "query": "x",
            "modality": "appearance",
            "pack_id": "appearance/rgb8@1",
            "count": 1,
            "status": "SUCCESS",
            "fallback": "LIBRARY_SCAN",
            "reason": "Searched your library directly (no separate index required).",
            "items": [{"item_id": "a1", "kind": "appearance"}],
            "note": "Similar looking is not the same as a named person.",
        }
    )
    blob = "\n".join(soft)
    assert "Similar photos" in soft[0]
    assert "modality=" not in blob
    assert "pack=" not in blob
    assert "ANN" not in blob
    assert "DEGRADED" not in blob
    assert "LIBRARY_SCAN" not in blob

    unavail = search_result_lines(
        {
            "kind": "similar",
            "status": "UNAVAILABLE",
            "reason": "Similar photos need an optional model. Nothing was searched.",
            "count": 0,
            "items": [],
        }
    )
    assert unavail[0] == "Similar photos unavailable"
    assert "optional" in unavail[1].lower()


def test_people_unknown_coaching_identity_safe_no_person_id_leak():
    people = format_people_lines(
        {
            "items": [
                {"person_id": "deadbeefcafebabe", "display_name": "Alex", "faces": 2},
            ]
        }
    )
    text = "\n".join(people)
    assert soft_people_header_lines()[0] in text
    assert "Alex" in text
    assert "deadbeef" not in text
    assert "person_id" not in text
    assert "People you have named" in text
    assert people[0] == "People you have named"

    unknown = format_unknown_lines(
        {"counts": {"UNKNOWN": 3, "REVIEW_REQUIRED": 0}}, "run-secret"
    )
    ut = "\n".join(unknown)
    assert soft_unknown_coach_lines(waiting=3)[0] in ut
    assert "Unknown is fine" in ut
    assert "group is not a person" in ut.lower()
    assert "run-secret" not in ut
    assert "KNOWN=" not in ut
    assert "person_id" not in ut

    empty = people_empty()
    assert empty.headline == "No people yet"
    assert "Add a photo folder" in (empty.primary_action or "")
    assert "To name" in (empty.tertiary_action or empty.description or "")
    assert "Error" not in empty.headline
    assert "Open Review" not in (empty.primary_action or "")
    assert "Open Review" not in (empty.tertiary_action or "")


def test_p2_loading_disabled_states_are_soft():
    loading = loading_workspace("people")
    assert "Loading people" in loading.headline
    assert "Error" not in loading.headline
    busy = disabled_while_busy("changing the library")
    assert "Not available" in busy.headline
    assert "Error" not in busy.headline


def test_format_search_person_section_header():
    lines = format_search_lines(
        {
            "kind": "person",
            "query": "Ada",
            "items": [{"display_name": "Ada", "faces": 3, "person_id": "pid1"}],
        }
    )
    assert lines[0] == "People"
    assert "Ada" in lines[1]
    assert "pid1" not in "\n".join(lines)


def test_home_search_and_settings_a11y_labels():
    import semblon.home_ui as home_ui

    init = inspect.getsource(home_ui.HomeApp.__init__)
    assert 'top, "Settings"' in init
    assert "takefocus=True" in init
    assert 'search_row, "Search"' in init or "Search" in init
