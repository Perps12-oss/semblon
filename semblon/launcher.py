"""Windows entry helpers for semblon.cmd (no pipeline logic)."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath


def is_interactive_launch(argv: list[str] | None) -> bool:
    """True when semblon.cmd was double-clicked with no CLI arguments."""
    return not argv


def _looks_windows_path(path: Path | str) -> bool:
    s = str(path)
    return ("\\" in s) or (len(s) >= 2 and s[1] == ":")


def interactive_script_path(repo_root: Path | str) -> Path:
    if _looks_windows_path(repo_root):
        root = PureWindowsPath(str(repo_root).rstrip("\\/"))
        return Path(str(root / "tools" / "semblon-interactive.ps1"))
    return Path(repo_root) / "tools" / "semblon-interactive.ps1"


def normalize_repo_root(path: Path | str) -> Path:
    """Strip trailing slashes (batch %~dp0 must not be passed as ...\\" to PowerShell)."""
    raw = str(path).rstrip("\\/")
    if _looks_windows_path(raw):
        return Path(raw.replace("\\", "/"))
    return Path(raw)
