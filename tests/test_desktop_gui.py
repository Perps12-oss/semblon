"""Offscreen desktop shell: launch, navigate, empty states, progress copy.

Does not claim a live Windows dump-gate. Skips when PySide6 is missing.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from semblon.desktop.app import main as desktop_main  # noqa: E402
from semblon.desktop.window import ImportDialog, MainWindow  # noqa: E402
from semblon.desktop.widgets import ProgressBanner  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_window_launches_and_navigates(qapp, tmp_path):
    win = MainWindow(store=tmp_path / "missing.sqlite")
    win.show()
    assert "Semblon" in win.windowTitle()
    assert win.stack.count() == 8
    for name in ("Home", "Photos", "Videos", "Live", "People", "Unknown", "Activity", "Settings"):
        win.navigate(name)
        assert win.current_page() == name
    win.close()


def test_empty_states_on_major_views(qapp, tmp_path):
    win = MainWindow(store=tmp_path / "missing.sqlite")
    win.show()
    assert win.home.empty.isVisible()
    win.navigate("Photos")
    assert win.photos.empty.isVisible()
    win.navigate("Videos")
    assert win.videos.empty.isVisible()
    win.navigate("People")
    assert win.people.empty.isVisible()
    win.navigate("Unknown")
    assert win.unknown.empty.isVisible()
    win.navigate("Activity")
    assert win.activity.empty.isVisible()
    win.close()


def test_home_open_unknown_navigates(qapp, tmp_path):
    win = MainWindow(store=tmp_path / "missing.sqlite")
    win.show()
    win.home.open_unknown.emit()
    assert win.current_page() == "Unknown"
    win.close()


def test_import_dialog_does_not_contradict_recursive_contract(qapp):
    dlg = ImportDialog()
    blob = "\n".join(w.text() for w in dlg.findChildren(QLabel))
    assert "subfolders" in blob.lower()
    assert "sampled" in blob.lower()
    assert dlg._ok.isEnabled() is False
    dlg.close()


def test_progress_banner_cancel_and_complete_are_distinct(qapp):
    banner = ProgressBanner()
    banner.show_busy({"headline": "Processing library…", "lines": ["Processing library…", "12 processed"]})
    assert banner.cancel_btn.isVisible()
    assert banner.review_btn.isHidden()
    banner.show_stopping()
    assert "Do not close Semblon" in banner.stopping.text()
    assert banner.cancel_btn.isEnabled() is False
    banner.show_cancelled("12 files processed")
    assert banner.headline.text() == "Import cancelled"
    assert "Partial results" in banner.current.text()
    assert banner.review_btn.isVisible()
    banner.show_complete("48 files processed")
    assert banner.headline.text() == "Import complete"
    assert "cancelled" not in banner.headline.text().lower()


def test_busy_import_explains_why_a_second_import_is_blocked(qapp, tmp_path):
    win = MainWindow(store=tmp_path / "missing.sqlite")
    win._busy = True
    win.open_import()
    assert "already running" in (win._last_info or "").lower()
    win.close()


def test_search_empty_query_does_not_fake_lens(qapp, tmp_path):
    win = MainWindow(store=tmp_path / "missing.sqlite")
    win.search.setText("")
    win._run_search()
    assert "named" in (win._last_info or "").lower()
    assert "visual similarity" in (win._last_info or "").lower()
    win.close()


def test_stylesheet_styles_empty_state(qapp, tmp_path):
    from semblon.desktop.theme import load_stylesheet

    qss = load_stylesheet()
    assert "#emptyState" in qss
    win = MainWindow(store=tmp_path / "missing.sqlite")
    assert win.home.empty.objectName() == "emptyState"
    win.close()


def test_import_success_opens_review_in_same_window(qapp, tmp_path):
    win = MainWindow(store=tmp_path / "missing.sqlite")
    win.show()
    win._on_success({"ingest": {"files": 4}})
    assert win.current_page() == "Unknown"
    assert win.unknown.heading.text() == "Review"
    src = Path(__file__).resolve().parents[1] / "semblon" / "desktop" / "window.py"
    text = src.read_text(encoding="utf-8")
    assert "run_review_ui" not in text
    win.close()


def test_home_cli_prefers_pyside_shell():
    from semblon.cli import main
    import inspect
    from semblon import cli as cli_mod

    src = inspect.getsource(cli_mod)
    assert "desktop.app" in src
    assert "--legacy" in src
    assert "run_home_ui" in src
    import io
    from unittest.mock import patch

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        try:
            main(["home", "--help"])
        except SystemExit as e:
            assert e.code == 0
    out = buf.getvalue().lower()
    assert "--legacy" in out
    assert "pyside" in out or "desktop" in out or "accepted" in out


def test_cli_desktop_help_names_accepted_shell():
    from semblon.cli import main
    import io
    from unittest.mock import patch

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        try:
            main(["desktop", "--help"])
        except SystemExit as e:
            assert e.code == 0
    out = buf.getvalue().lower()
    assert "accepted" in out or "pyside" in out or "home" in out
    from semblon.desktop.app import main as desktop_main

    assert desktop_main is not None
