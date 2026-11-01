"""Local rotating log. Paths under the user profile are redacted. No person names."""

from __future__ import annotations

import faulthandler
import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG = logging.getLogger("semblon")
_READY = False
_NAME_RE = re.compile(r"(display_name|person_name)(['\"]?\s*[:=]\s*)(['\"]).*?\3", re.I)


def log_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "Semblon" / "logs"
    return Path.home() / ".semblon" / "logs"


def redact(text: str) -> str:
    if not text:
        return text
    home = str(Path.home())
    if home:
        text = text.replace(home, "~")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        text = text.replace(local, "%LOCALAPPDATA%")
    return _NAME_RE.sub(r"\1\2\3[redacted]\3", text)


class _RedactFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def configure_logging(directory: Path | None = None) -> Path | None:
    """Attach one rotating file. Skipped under pytest unless directory is passed."""
    global _READY
    if directory is None and os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    if directory is None and os.environ.get("SEMBLON_LOG") == "0":
        return None
    if _READY and directory is None:
        return log_dir() / "semblon.log"
    dest_dir = Path(directory) if directory is not None else log_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / "semblon.log"
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(_RedactFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    _LOG.setLevel(logging.INFO)
    _LOG.handlers.clear()
    _LOG.addHandler(handler)
    _LOG.propagate = False

    def _hook(exc_type, exc, tb):
        try:
            _LOG.error(
                "unhandled %s",
                getattr(exc_type, "__name__", "error"),
                exc_info=(exc_type, exc, tb),
            )
        except Exception:
            # Never let logging (e.g. Windows rotate lock) hide the real crash.
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _hook
    # faulthandler must not hold the rotating log open — on Windows that blocks
    # rollover (WinError 32) and then masks the real exception with a Logging error.
    fault_path = dest_dir / "semblon-fault.log"
    try:
        fault_handle = fault_path.open("a", encoding="utf-8")
        faulthandler.enable(file=fault_handle, all_threads=True)
    except OSError:
        faulthandler.enable(all_threads=True)
    _READY = True
    _LOG.info("log opened")
    return path
