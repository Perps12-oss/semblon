"""Load the desktop QSS. Presentation only. No FaceKit."""

from __future__ import annotations

from pathlib import Path

_QSS_PATH = Path(__file__).with_name("theme.qss")


def load_stylesheet() -> str:
    return _QSS_PATH.read_text(encoding="utf-8")


STYLESHEET = load_stylesheet()
