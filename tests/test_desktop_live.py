"""Live page overlay rendering (offscreen Qt)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from semblon.desktop.pages import LivePage  # noqa: E402
from semblon.desktop.window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_live_nav_and_overlay_multi_boxes(qapp, tmp_path):
    win = MainWindow(store=tmp_path / "missing.sqlite")
    win.show()
    assert win.stack.count() == 8
    win.navigate("Live")
    assert win.current_page() == "Live"
    page: LivePage = win.live
    page.set_running(True)
    page.apply_frame(
        {
            "frame_index": 3,
            "counts": {"detected": 2, "tracks": 2},
            "overlays": [
                {
                    "bbox": (20, 30, 80, 100),
                    "label": "Alice",
                    "track_id": "aaaa",
                    "decision": "ACCEPT",
                },
                {
                    "bbox": (160, 40, 220, 110),
                    "label": "UNKNOWN",
                    "track_id": "bbbb",
                    "decision": "UNKNOWN",
                },
            ],
        }
    )
    assert page._last_overlays and len(page._last_overlays) == 2
    assert "Alice" in page.status.text() or "faces 2" in page.status.text()
    page.clear_overlays()
    assert page._last_overlays == []
    page.set_running(False)
    win.close()


def test_live_start_stop_controls(qapp, tmp_path):
    page = LivePage()
    assert page.btn_start.isEnabled()
    assert not page.btn_stop.isEnabled()
    page.set_running(True)
    assert not page.btn_start.isEnabled()
    assert page.btn_stop.isEnabled()
    page.set_running(False)
    assert page.btn_start.isEnabled()
