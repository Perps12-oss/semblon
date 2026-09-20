"""Qt application bootstrap. DPI-aware; no work on the UI thread."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from semblon.desktop.service import StoreLibraryService
from semblon.desktop.theme import load_stylesheet
from semblon.desktop.window import MainWindow


def run(store: Path | None = None) -> int:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Semblon")
    app.setOrganizationName("Semblon")
    app.setStyleSheet(load_stylesheet())
    service = StoreLibraryService(store)
    win = MainWindow(service=service)
    win.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="semblon-desktop")
    p.add_argument(
        "--store",
        type=Path,
        default=None,
        help="SQLite store (default: %%LOCALAPPDATA%%\\Semblon\\store.sqlite)",
    )
    args = p.parse_args(argv)
    return run(store=args.store)


if __name__ == "__main__":
    raise SystemExit(main())
