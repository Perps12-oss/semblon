"""Lens Home workspace — route, soft labels, honest unavailable, no identity writes."""

from __future__ import annotations

import inspect
import sqlite3
from pathlib import Path

from semblon.empty_states import lens_empty
from semblon.home_shell import lens_understanding_rows
from semblon.home_ui import HOME_NAV
from semblon.product_exposure import product_chrome_forbidden_labels
from semblon.runtime_contract import StructuredResult
from semblon.selection import (
    LENS_EMPTY_GUIDE,
    format_query_lines,
    lens_result_summary,
    media_file,
    run_lens_query,
    widget_drag_to_image,
)


class _Report:
    def __init__(self, results, region=None):
        self.results = results
        self.region = region or {"x": 0, "y": 0, "w": 10, "h": 10}


def test_home_nav_includes_lens_route():
    flat = {nav_id: label for _sec, items in HOME_NAV for nav_id, label in items}
    assert flat["lens"] == "Lens"
    assert "ASK" in {sec for sec, _ in HOME_NAV}


def test_lens_route_opens_workspace_not_photos_redirect():
    import semblon.home_ui as home_ui

    open_src = inspect.getsource(home_ui.HomeApp._open_lens)
    assert "_show_lens_workspace" in open_src
    assert '_navigate("photos")' not in open_src
    assert "_build_lens_workspace" in inspect.getsource(home_ui.HomeApp)
    nav = inspect.getsource(home_ui.HomeApp._navigate)
    assert 'nav_id == "lens"' in nav
    hide = inspect.getsource(home_ui.HomeApp._hide_workspace_panes)
    assert "_lens" in hide


def test_photos_path_into_lens_with_current_asset():
    import semblon.home_ui as home_ui

    src = inspect.getsource(home_ui.HomeApp)
    assert "_ask_with_lens" in src
    assert "Ask with Lens" in src
    ask = inspect.getsource(home_ui.HomeApp._ask_with_lens)
    assert "_open_lens" in ask
    tip = inspect.getsource(__import__("semblon.product_surface", fromlist=["soft_inspector_for_media"]).soft_inspector_for_media)
    assert "Open Lens" in tip


def test_lens_empty_guides_user():
    empty = lens_empty()
    text = "\n".join(empty.as_lines())
    assert "Open a photo" in text
    assert "select something to look at" in text.lower() or "select something" in text.lower()
    assert LENS_EMPTY_GUIDE.split(",")[0] in text or "Open a photo" in text
    assert "embed_siglip" not in text
    assert "pack_id" not in text
    assert empty.action_id == "browse_photos"


def test_lens_understanding_rows_are_soft_and_honest():
    rows = lens_understanding_rows()
    assert rows
    labels = " ".join(r["label"] for r in rows)
    states = " ".join(r["state"] for r in rows)
    assert "embed_siglip" not in labels.lower()
    assert "visual_embedding" not in labels  # product label, not id
    assert "siglip" not in labels.lower()
    assert "Read text" in labels or "Barcode" in labels
    assert "Optional" in states or "Available" in states or "Experimental" in states
    # ids exist for tests only — UX must not dump them as labels
    assert all(r["label"] != r["id"] for r in rows)


def test_unsupported_capability_honest_not_empty_match():
    report = _Report(
        [
            StructuredResult(
                status="UNAVAILABLE",
                capability_id="visual_embedding",
                provider_id="siglip",
                model_state="MISSING",
                provider_state="FAILED",
                reason="Visual embedding is not installed. Nothing was searched.",
                items=(),
            )
        ]
    )
    lines = format_query_lines(report)
    text = "\n".join(lines)
    assert "Nothing was searched" in text or "not installed" in text.lower()
    assert "embed_siglip" not in text
    assert "visual_embedding:" not in text
    summary = lens_result_summary(report)
    assert summary["status"] == "UNAVAILABLE"


def test_soft_labels_exclude_capability_and_provider_jargon():
    forbidden = product_chrome_forbidden_labels()
    for token in (
        "embed_siglip",
        "ground_selection",
        "describe_vlm",
        "ANN",
        "buffalo_l",
        "FaceKit",
    ):
        assert token in forbidden
    report = _Report(
        [
            StructuredResult(
                status="NO_RESULT",
                capability_id="ocr",
                provider_id="tesseract",
                model_state="AVAILABLE",
                provider_state="READY",
                reason="",
                items=(),
            )
        ]
    )
    text = "\n".join(format_query_lines(report))
    assert "tesseract" not in text.lower() or "Read text" in text
    assert "ocr:" not in text


def test_lens_errors_do_not_crash_home_handlers():
    import semblon.home_ui as home_ui

    region = inspect.getsource(home_ui.HomeApp._open_region_select)
    assert "except Exception" in region
    whole = inspect.getsource(home_ui.HomeApp._lens_ask_whole)
    assert "on_error" in whole
    assert "show_failure_dialog" in whole or "messagebox" in whole
    # Off UI thread for inference
    assert "schedule" in region
    assert "semblon-lens-query" in inspect.getsource(
        __import__("semblon.selection", fromlist=["run_lens_query"]).run_lens_query
    )


def test_lens_does_not_write_identity():
    """Identity firewall: Lens query path must not stamp faces.person_id."""
    import semblon.selection as selection

    src = inspect.getsource(selection.run_lens_query)
    assert "UPDATE" not in src.lower()
    assert "INSERT" not in src
    assert "person_id" not in src
    home_lens = inspect.getsource(
        __import__("semblon.home_ui", fromlist=["HomeApp"]).HomeApp._lens_ask_whole
    )
    assert "UPDATE faces" not in home_lens.lower()
    assert "person_id" not in home_lens
    region = inspect.getsource(selection.mount_region_select)
    assert "person_id" not in region
    assert "sqlite" not in region.lower()
    assert "Never writes the store" in (selection.run_lens_query.__doc__ or "")


def test_review_html_not_product_ux_regression():
    import semblon.home_ui as home_ui

    init = inspect.getsource(home_ui.HomeApp.__init__)
    assert "Open review.html" not in init
    sync = inspect.getsource(home_ui.HomeApp._sync_chrome_for_route)
    assert "btn_html" not in sync
    settings = inspect.getsource(home_ui.HomeApp._show_settings)
    assert "Open export review page" in settings


def test_widget_drag_and_media_file(tmp_path):
    assert widget_drag_to_image(0, 0, 0, 10, view_w=100, view_h=100, image_w=200, image_h=200) is None
    rect = widget_drag_to_image(0, 0, 50, 50, view_w=100, view_h=100, image_w=200, image_h=200)
    assert rect == {"x": 0, "y": 0, "w": 100, "h": 100}
    assert media_file(tmp_path / "missing.sqlite", "m1") is None

    store = tmp_path / "s.sqlite"
    conn = sqlite3.connect(str(store))
    conn.execute(
        "CREATE TABLE media (media_id TEXT PRIMARY KEY, path TEXT, source_type TEXT)"
    )
    img = tmp_path / "a.jpg"
    img.write_bytes(b"not-a-real-jpeg")
    conn.execute("INSERT INTO media VALUES (?,?,?)", ("m1", str(img), "folder"))
    conn.commit()
    conn.close()
    assert media_file(store, "m1") == img


def test_run_lens_query_sync_unreadable(tmp_path):
    bad = tmp_path / "nope.jpg"
    bad.write_bytes(b"x")
    captured: list[list[str]] = []

    def on_lines(lines):
        captured.append(lines)

    # cv2.imread returns None for garbage — honest empty search
    run_lens_query(bad, on_lines=on_lines, schedule=None)
    assert captured
    assert "Nothing was searched" in "\n".join(captured[0])


def test_exposure_map_marks_lens_workspace():
    text = Path("docs/UI-EXPOSURE-MAP.md").read_text(encoding="utf-8")
    assert "Lens / Inspect" in text
    assert "PARTIAL" not in text.split("Lens / Inspect")[1].split("\n")[0]
    assert "Home route/workspace" in text or "workspace" in text.lower()
