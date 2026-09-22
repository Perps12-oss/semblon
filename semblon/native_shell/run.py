"""Entry for the native production shell."""

from __future__ import annotations

from pathlib import Path


def run_native_shell(store: Path | None = None) -> int:
    """Open the Qt/PySide production shell. Requires optional PySide6."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as e:  # pragma: no cover - env without gui extra
        print(
            "native shell requires PySide6. Install: pip install 'semblon[gui]'",
            flush=True,
        )
        raise SystemExit(2) from e

    from semblon.application import Application
    from semblon.native_shell.window import ShellWindow
    from semblon.process import default_store_path

    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Semblon")
    app.setOrganizationName("Semblon")
    session = Application(store if store is not None else default_store_path())
    window = ShellWindow(session)
    window.show()
    return int(app.exec())
