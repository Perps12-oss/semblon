"""Canonical path rules (ported from dedup ``path_policy`` + discovery path normalisation)."""

from __future__ import annotations

import os
from pathlib import Path


def canonical_path(path: Path | str) -> Path:
    p = Path(path)
    try:
        return p.resolve()
    except (OSError, RuntimeError):
        try:
            return p.absolute()
        except (OSError, RuntimeError):
            return p


def path_key(path: Path | str) -> str:
    """Case/separator-normalised key for comparison (case-insensitive on Windows)."""
    return os.path.normcase(os.path.normpath(str(path)))


def is_fs_root(directory: Path | str) -> bool:
    d = canonical_path(directory)
    return d.parent == d


def is_hidden_name(name: str) -> bool:
    return name.startswith(".")


def build_exclusion_keys(paths: set[str]) -> set[str]:
    return {path_key(canonical_path(p)) for p in paths if p}


def is_excluded(path: Path | str, exclusion_keys: set[str]) -> bool:
    """True if ``path`` equals or lies below any excluded path."""
    if not exclusion_keys:
        return False
    key = path_key(canonical_path(path))
    for ex in exclusion_keys:
        if key == ex or key.startswith(ex.rstrip(os.sep) + os.sep):
            return True
    return False
