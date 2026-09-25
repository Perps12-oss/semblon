"""Product exposure consolidation — canonical Home, stale chrome, soft Lens/Search."""

from __future__ import annotations

import inspect

from semblon.product_exposure import (
    GUI_PATHS,
    canonical_product_entry,
    paths_by_class,
    product_chrome_forbidden_labels,
    soft_capability_label,
)
from semblon.runtime_contract import StructuredResult
from semblon.selection import format_query_lines, lens_result_summary


class _Report:
    def __init__(self, results, region=None):
        self.results = results
        self.region = region or {"x": 0, "y": 0, "w": 10, "h": 10}


def test_canonical_entry_is_tk_home():
    assert canonical_product_entry() == "semblon home"
    import semblon.cli as cli

    src = inspect.getsource(cli.main)
    assert "authoritative production GUI" in src
    assert "not the product Home" in src
    assert "secondary Review workspace" in src
    assert "secondary observation workspace" in src
    assert 'cmd == "home"' in src
    assert "run_home_ui" in src
    assert "run_native_shell" in src


def test_exposure_registry_covers_required_classes():
    classes = {cls for _n, cls, *_rest in GUI_PATHS}
    for required in (
        "CANONICAL",
        "SECONDARY",
        "OPTIONAL",
        "CLI",
        "LAB",
        "ENGINEERING",
        "SUPERSEDED",
        "STALE",
    ):
        assert required in classes
    stale = paths_by_class("STALE")
    assert any("review.html" in name.lower() for name, *_ in stale)
    assert any("Canvas" in name for name, *_ in stale)
    optional = paths_by_class("OPTIONAL")
    assert any("shell" in name.lower() or "Qt" in name for name, *_ in optional)


def test_home_product_chrome_drops_review_html_and_job_bar_canvas():
    import semblon.home_ui as home_ui

    init = inspect.getsource(home_ui.HomeApp.__init__)
    assert "Open review.html" not in init
    sync = inspect.getsource(home_ui.HomeApp._sync_chrome_for_route)
    assert "btn_canvas.pack" not in sync
    assert "btn_html" not in sync
    settings = inspect.getsource(home_ui.HomeApp._show_settings)
    assert "SETTINGS_EXPORT_REVIEW" in settings or "Open export review page" in settings
    assert "SETTINGS_ADVANCED" in settings or "Advanced" in settings
    assert "html" not in home_ui.HOME_CONTROLS_ALWAYS_ON
    assert "canvas" not in home_ui.HOME_CONTROLS_ALWAYS_ON
    forbidden = product_chrome_forbidden_labels()
    assert "Open review.html" in forbidden
    assert hasattr(home_ui.HomeApp, "_open_html")


def test_interactive_launcher_opens_home_only():
    from pathlib import Path

    from semblon.launcher import interactive_script_path

    script = interactive_script_path(Path(".").resolve())
    text = script.read_text(encoding="utf-8")
    assert "-m semblon home" in text
    assert "semblon shell" not in text


def test_lens_lines_use_plain_labels_not_internal_ids():
    report = _Report(
        [
            StructuredResult(
                status="NO_RESULT",
                capability_id="barcode",
                provider_id="symbology",
                model_state="AVAILABLE",
                provider_state="READY",
                reason="",
                items=(),
            ),
            StructuredResult(
                status="UNAVAILABLE",
                capability_id="visual_embedding",
                provider_id="siglip",
                model_state="MISSING",
                provider_state="FAILED",
                reason="Visual embedding is not installed. Nothing was searched.",
                items=(),
            ),
        ]
    )
    lines = format_query_lines(report)
    text = "\n".join(lines)
    assert "Lens" in text
    assert "embed_siglip" not in text
    assert "visual_embedding:" not in text
    assert "barcode:" not in text
    assert "Barcode" in text or "ran, nothing matched" in text
    summary = lens_result_summary(report)
    assert summary["status"] in {"UNAVAILABLE", "NO_RESULT"}


def test_soft_capability_label_prefers_catalog():
    assert soft_capability_label("visual_embedding", catalog_label="Visual embedding") == (
        "Visual embedding"
    )
    assert "siglip" not in soft_capability_label("visual_embedding").lower()


def test_home_search_tries_text_without_modality_gate():
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp._search_person)
    assert "search_text" in src
    assert "MODALITY_PRODUCT" not in src
    assert "person name or text" in src.lower() or "text from a photo" in src.lower()


def test_people_unknown_copy_avoids_uuid_and_keeps_unknown_valid():
    from semblon.home_ui import format_people_lines, format_unknown_lines

    people = format_people_lines(
        {
            "items": [
                {"person_id": "deadbeef", "display_name": "Alex", "faces": 3},
                {"person_id": "cafebabe", "display_name": "", "faces": 1},
            ]
        }
    )
    text = "\n".join(people)
    assert "Alex" in text
    assert "deadbeef" not in text
    assert "cafebabe" not in text
    assert "Named person" in text
    unknown = format_unknown_lines({"counts": {"UNKNOWN": 2, "REVIEW_REQUIRED": 1}}, "r1")
    ut = "\n".join(unknown)
    assert "Unknown is fine" in ut
    assert "run=r1" not in ut
    assert "People you have named" in "\n".join(people) or "Named" in "\n".join(people)
