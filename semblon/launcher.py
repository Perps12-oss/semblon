"""Windows entry helpers for semblon.cmd (no pipeline logic)."""

from __future__ import annotations

from pathlib import Path


def is_interactive_launch(argv: list[str] | None) -> bool:
    """True when semblon.cmd was double-clicked with no CLI arguments."""
    return not argv


def interactive_script_path(repo_root: Path | str) -> Path:
    return Path(repo_root).resolve() / "tools" / "semblon-interactive.ps1"
