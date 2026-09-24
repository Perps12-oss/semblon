"""Appearance preference. A JSON file beside the library, not a schema column.

Modes: system, light, dark. System follows the Windows app theme when the
registry value is readable. Otherwise system resolves to light — this
process does not guess a dark theme it cannot see.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from semblon.process import default_store_path
from semblon.ui_tokens import DARK, LIGHT, Palette

THEME_MODES = ("system", "light", "dark")
_FILE_NAME = "appearance.json"


def appearance_path(store: Path | None = None) -> Path:
    """User-local appearance file. Same directory as the library SQLite file."""
    lib = Path(store) if store is not None else default_store_path()
    return lib.parent / _FILE_NAME


def load_theme_mode(store: Path | None = None) -> str:
    """Return system, light, or dark. Missing or damaged files are system."""
    path = appearance_path(store)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "system"
    if not isinstance(raw, dict):
        return "system"
    mode = str(raw.get("theme") or "").strip().lower()
    if mode in THEME_MODES:
        return mode
    return "system"


def save_theme_mode(mode: str, store: Path | None = None) -> str:
    """Persist theme. Unknown values are stored as system. Returns the mode kept."""
    kept = mode.strip().lower() if isinstance(mode, str) else ""
    if kept not in THEME_MODES:
        kept = "system"
    path = appearance_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"theme": kept}, indent=2) + "\n"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)
    return kept


def system_is_dark() -> bool | None:
    """True/False on Windows when the personalize key is readable. Else None."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except OSError:
        return None
    try:
        return int(value) == 0
    except (TypeError, ValueError):
        return None


def resolve_palette(mode: str, *, system_dark: bool | None = None) -> Palette:
    """Map a stored mode to a palette. Unknown system theme stays light."""
    picked = mode.strip().lower() if isinstance(mode, str) else "system"
    if picked == "dark":
        return DARK
    if picked == "light":
        return LIGHT
    dark = system_is_dark() if system_dark is None else system_dark
    if dark is True:
        return DARK
    return LIGHT
