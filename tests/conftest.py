import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SEMBLON_SEARCH_SYNC", "1")
# Must precede QApplication / Controls registration (Linux CI QQuickStyle ordering).
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

import sys

import pytest
from PySide6.QtWidgets import QApplication


def pytest_sessionstart(session):  # noqa: ARG001
    """Report required pin gaps. Does not install and does not probe model packs."""
    if os.environ.get("SEMBLON_PREFLIGHT", "1") == "0":
        return
    try:
        from semblon.preflight import required_gaps

        gaps = required_gaps()
    except Exception as exc:  # noqa: BLE001 — a status print must not stop the suite
        print(
            f"preflight: could not check required packages ({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )
        return
    if gaps:
        names = "; ".join(
            f"{row['id']} ({row.get('detail') or row.get('status') or 'not ready'})"
            for row in gaps
        )
        print(f"preflight: required packages not ready: {names}", file=sys.stderr)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Semblon")
    app.setOrganizationName("Semblon")
    yield app
    app.processEvents()
    app.quit()
