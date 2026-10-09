"""User presentation preferences beside the library (and machine continuity).

Single JSON surface — ``appearance.json`` — not a schema column and not a
second settings stack. Library-scoped keys live next to the active store.
Machine continuity keys (last library, window geometry) live next to the
default store path under ``%LOCALAPPDATA%\\Semblon`` (or the POSIX equivalent).

Missing or damaged files fall back to canonical defaults. Corrupt prefs must
never prevent launch.

Canonical defaults (absent file / absent key):
  theme            → mica_dark
  grid_density     → comfortable
  search_mode      → people
  library_filter   → all
  prefer_gpu       → unset (product_prefer_gpu at runtime)
  window_geometry  → unset (WINDOW_DEFAULT)
  last_store       → unset (default_store_path)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from semblon.atmosphere import (
    ATMOSPHERES,
    DEFAULT_DARK_ATMOSPHERE,
    THEME_MODES,
    palette_for,
)
from semblon.process import default_store_path
from semblon.ui_tokens import Palette

_FILE_NAME = "appearance.json"


class _SystemDarkUnset:
    pass


_SYSTEM_DARK_UNSET = _SystemDarkUnset()

# Library-scoped keys (cleared when Reset removes appearance.json beside store).
KEY_THEME = "theme"
KEY_GRID_DENSITY = "grid_density"
KEY_SEARCH_MODE = "search_mode"
KEY_LIBRARY_FILTER = "library_filter"
KEY_PREFER_GPU = "prefer_gpu"

# Machine-scoped keys (default Semblon data dir). Cleared when that file is
# removed — including Reset of the default library.
KEY_WINDOW_GEOMETRY = "window_geometry"
KEY_LAST_STORE = "last_store"

GRID_DENSITIES = ("comfortable", "cozy", "compact")
SEARCH_MODES = ("people", "text", "whole", "region")
LIBRARY_FILTERS = ("all", "photos", "videos")

_GEOM_RE = re.compile(r"^(\d+)x(\d+)(?:([+-]\d+)([+-]\d+))?$")

__all__ = [
    "THEME_MODES",
    "GRID_DENSITIES",
    "SEARCH_MODES",
    "LIBRARY_FILTERS",
    "KEY_THEME",
    "KEY_GRID_DENSITY",
    "KEY_SEARCH_MODE",
    "KEY_LIBRARY_FILTER",
    "KEY_PREFER_GPU",
    "KEY_WINDOW_GEOMETRY",
    "KEY_LAST_STORE",
    "appearance_path",
    "machine_prefs_path",
    "load_prefs",
    "update_prefs",
    "load_theme_mode",
    "save_theme_mode",
    "load_grid_density",
    "save_grid_density",
    "load_search_mode",
    "save_search_mode",
    "load_library_filter",
    "save_library_filter",
    "load_prefer_gpu",
    "save_prefer_gpu",
    "load_window_geometry",
    "save_window_geometry",
    "load_last_store",
    "save_last_store",
    "resolve_home_store",
    "resolve_atmosphere_id",
    "resolve_palette",
    "system_is_dark",
]


def appearance_path(store: Path | None = None) -> Path:
    """User-local appearance file. Same directory as the library SQLite file."""
    lib = Path(store) if store is not None else default_store_path()
    return lib.parent / _FILE_NAME


def machine_prefs_path() -> Path:
    """Machine continuity file next to the default store location."""
    return appearance_path(default_store_path())


def _read_json(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def load_prefs(store: Path | None = None) -> dict:
    """Raw library-scoped prefs dict. Empty on missing/corrupt file."""
    return _read_json(appearance_path(store))


def update_prefs(store: Path | None = None, **updates: object) -> dict:
    """Merge keys into library appearance.json. ``None`` removes a key."""
    path = appearance_path(store)
    data = _read_json(path)
    for key, value in updates.items():
        if value is None:
            data.pop(str(key), None)
        else:
            data[str(key)] = value
    _write_json(path, data)
    return data


def _update_machine(**updates: object) -> dict:
    path = machine_prefs_path()
    data = _read_json(path)
    for key, value in updates.items():
        if value is None:
            data.pop(str(key), None)
        else:
            data[str(key)] = value
    _write_json(path, data)
    return data


def load_theme_mode(store: Path | None = None) -> str:
    """Return a stored theme mode. Missing or damaged files are Mica Dark."""
    mode = str(load_prefs(store).get(KEY_THEME) or "").strip().lower()
    return mode if mode in THEME_MODES else "mica_dark"


def save_theme_mode(mode: str, store: Path | None = None) -> str:
    """Persist theme without wiping other preference keys."""
    kept = mode.strip().lower() if isinstance(mode, str) else ""
    if kept not in THEME_MODES:
        kept = "mica_dark"
    update_prefs(store, **{KEY_THEME: kept})
    return kept


def load_grid_density(store: Path | None = None) -> str:
    dens = str(load_prefs(store).get(KEY_GRID_DENSITY) or "").strip().lower()
    return dens if dens in GRID_DENSITIES else "comfortable"


def save_grid_density(density: str, store: Path | None = None) -> str:
    dens = (density or "comfortable").strip().lower()
    if dens not in GRID_DENSITIES:
        dens = "comfortable"
    update_prefs(store, **{KEY_GRID_DENSITY: dens})
    return dens


def load_search_mode(store: Path | None = None) -> str:
    mode = str(load_prefs(store).get(KEY_SEARCH_MODE) or "").strip().lower()
    return mode if mode in SEARCH_MODES else "people"


def save_search_mode(mode: str, store: Path | None = None) -> str:
    key = (mode or "people").strip().lower()
    if key not in SEARCH_MODES:
        key = "people"
    update_prefs(store, **{KEY_SEARCH_MODE: key})
    return key


def load_library_filter(store: Path | None = None) -> str:
    key = str(load_prefs(store).get(KEY_LIBRARY_FILTER) or "").strip().lower()
    return key if key in LIBRARY_FILTERS else "all"


def save_library_filter(filter_key: str, store: Path | None = None) -> str:
    key = (filter_key or "all").strip().lower()
    if key not in LIBRARY_FILTERS:
        key = "all"
    update_prefs(store, **{KEY_LIBRARY_FILTER: key})
    return key


def load_prefer_gpu(store: Path | None = None) -> bool | None:
    """User override. ``None`` means follow product_prefer_gpu()."""
    raw = load_prefs(store).get(KEY_PREFER_GPU, None)
    if raw is None:
        return None
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return None


def save_prefer_gpu(value: bool | None, store: Path | None = None) -> bool | None:
    if value is None:
        update_prefs(store, **{KEY_PREFER_GPU: None})
        return None
    kept = bool(value)
    update_prefs(store, **{KEY_PREFER_GPU: kept})
    return kept


def _parse_geometry(raw: object) -> str | None:
    text = str(raw or "").strip()
    match = _GEOM_RE.match(text)
    if not match:
        return None
    w, h = int(match.group(1)), int(match.group(2))
    if w < 640 or h < 480 or w > 10000 or h > 10000:
        return None
    return text


def load_window_geometry() -> str | None:
    """Machine-scoped window geometry. ``None`` → use WINDOW_DEFAULT."""
    return _parse_geometry(_read_json(machine_prefs_path()).get(KEY_WINDOW_GEOMETRY))


def save_window_geometry(geometry: str | None) -> str | None:
    kept = _parse_geometry(geometry)
    _update_machine(**{KEY_WINDOW_GEOMETRY: kept})
    return kept


def load_last_store() -> Path | None:
    """Machine-scoped last library path when the file still exists."""
    raw = str(_read_json(machine_prefs_path()).get(KEY_LAST_STORE) or "").strip()
    if not raw:
        return None
    path = Path(raw)
    try:
        if path.is_file():
            return path.resolve()
    except OSError:
        return None
    return None


def save_last_store(store: Path | None) -> Path | None:
    if store is None:
        _update_machine(**{KEY_LAST_STORE: None})
        return None
    path = Path(store)
    try:
        text = str(path.resolve())
    except OSError:
        text = str(path)
    _update_machine(**{KEY_LAST_STORE: text})
    return path


def resolve_home_store(store: Path | None = None) -> Path:
    """Active library: explicit arg, else last_store if present, else default."""
    if store is not None:
        return Path(store)
    remembered = load_last_store()
    if remembered is not None:
        return remembered
    return default_store_path()


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


def resolve_atmosphere_id(
    mode: str, *, system_dark: bool | None | _SystemDarkUnset = _SYSTEM_DARK_UNSET
) -> str:
    """Map a stored mode to an atmosphere id."""
    picked = mode.strip().lower() if isinstance(mode, str) else "system"
    if picked == "dark":
        return DEFAULT_DARK_ATMOSPHERE
    if picked in ATMOSPHERES:
        return picked
    if picked == "light":
        return "light"
    if picked != "system":
        # Unknown explicit names match load_theme_mode: Mica Dark, not light.
        return DEFAULT_DARK_ATMOSPHERE
    dark = system_is_dark() if system_dark is _SYSTEM_DARK_UNSET else system_dark
    # Unknown (registry unreadable) stays Mica Dark. Explicit light Windows stays light.
    if dark is False:
        return "light"
    return DEFAULT_DARK_ATMOSPHERE


def resolve_palette(
    mode: str, *, system_dark: bool | None | _SystemDarkUnset = _SYSTEM_DARK_UNSET
) -> Palette:
    """Map a stored mode to a resting palette."""
    return palette_for(resolve_atmosphere_id(mode, system_dark=system_dark))
