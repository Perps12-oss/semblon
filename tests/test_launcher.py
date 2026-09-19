"""Windows entry launcher helpers (no native dialog in unit tests)."""

from __future__ import annotations

from pathlib import Path

from semblon.home_ui import format_progress_line
from semblon.launcher import interactive_script_path, is_interactive_launch, normalize_repo_root
from semblon.progress import KIND_CANCELLED, KIND_PROGRESS, KIND_STARTED, STAGE_INGEST, make_event


def test_is_interactive_launch_empty_argv():
    assert is_interactive_launch([]) is True
    assert is_interactive_launch(None) is True


def test_is_interactive_launch_forwards_cli():
    assert is_interactive_launch(["process", r"D:\photos"]) is False
    assert is_interactive_launch(["--help"]) is False


def test_normalize_repo_root_strips_trailing_backslash():
    assert normalize_repo_root("C:\\repo\\SEMBRON\\") == Path("C:/repo/SEMBRON")


def test_interactive_script_path():
    root = Path(r"C:\repo\SEMBRON")
    p = interactive_script_path(root)
    assert p == Path(r"C:\repo\SEMBRON\tools\semblon-interactive.ps1")


def test_install_windows_script_present():
    repo = Path(__file__).resolve().parents[1]
    script = repo / "tools" / "install-windows.ps1"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "pip install -e" in text
    assert "buffalo_l" in text


def test_interactive_script_opens_home():
    repo = Path(__file__).resolve().parents[1]
    script = interactive_script_path(repo)
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "Invoke-SemblonHome" in text
    assert " home" in text
    assert "FolderBrowserDialog" not in text
    assert "process" in text  # -Folder smoke path still processes
    assert "UseDescriptionForTitle" not in text


def test_format_progress_line_does_not_invent_percent():
    ev = make_event(STAGE_INGEST, KIND_STARTED, message="reading stills")
    line = format_progress_line(ev)
    assert "ingest:started" in line
    assert "reading stills" in line
    assert "%" not in line

    ev2 = make_event(
        STAGE_INGEST,
        KIND_PROGRESS,
        files_processed=3,
        files_total=10,
        percent=30.0,
    )
    line2 = format_progress_line(ev2)
    assert "files 3/10" in line2
    assert "30%" in line2

    ev3 = make_event(STAGE_INGEST, KIND_CANCELLED, message="cancelled", outcome="cancelled")
    line3 = format_progress_line(ev3)
    assert "ingest:cancelled" in line3
    assert "%" not in line3
