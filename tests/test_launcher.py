"""Windows entry launcher helpers (no native dialog in unit tests)."""

from __future__ import annotations

from pathlib import Path

from semblon.launcher import interactive_script_path, is_interactive_launch


def test_is_interactive_launch_empty_argv():
    assert is_interactive_launch([]) is True
    assert is_interactive_launch(None) is True


def test_is_interactive_launch_forwards_cli():
    assert is_interactive_launch(["process", r"D:\photos"]) is False
    assert is_interactive_launch(["--help"]) is False


def test_interactive_script_path():
    root = Path(r"C:\repo\SEMBRON")
    p = interactive_script_path(root)
    assert p == Path(r"C:\repo\SEMBRON\tools\semblon-interactive.ps1")


def test_interactive_script_exists_in_repo():
    repo = Path(__file__).resolve().parents[1]
    script = interactive_script_path(repo)
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "FolderBrowserDialog" in text
    assert "process" in text
