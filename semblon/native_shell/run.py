"""Entry for `semblon shell` — one archive, Qt Quick."""

from __future__ import annotations

from pathlib import Path


def run_native_shell(store: Path | None = None) -> int:
    """Open the archive shell. Requires PySide6. This is the forward product UI."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as e:  # pragma: no cover - env without gui extra
        print(
            "native shell requires PySide6. Install: pip install 'semblon[gui]'",
            flush=True,
        )
        raise SystemExit(2) from e

    del QApplication
    from semblon.native_shell.host import build_shell, shutdown_shell

    app, engine = build_shell(store)
    code = int(app.exec())
    shutdown_shell(engine)
    return code
