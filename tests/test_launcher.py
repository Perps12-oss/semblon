"""Windows entry launcher helpers (no native dialog in unit tests)."""

from __future__ import annotations

from pathlib import Path

from semblon.home_ui import HOME_OBSERVERS, format_people_lines, format_progress_line
from semblon.launcher import interactive_script_path, is_interactive_launch, normalize_repo_root
from semblon.progress import KIND_CANCELLED, KIND_QUEUED, KIND_PROGRESS, KIND_STARTED, STAGE_INGEST, STAGE_PROCESS, make_event


def test_is_interactive_launch_empty_argv():
    assert is_interactive_launch([]) is True
    assert is_interactive_launch(None) is True


def test_is_interactive_launch_forwards_cli():
    assert is_interactive_launch(["process", r"D:\photos"]) is False
    assert is_interactive_launch(["--help"]) is False


def test_normalize_repo_root_strips_trailing_backslash():
    """Trailing \\ or / is stripped. Do not compare PosixPath to C:/... literals."""
    got = str(normalize_repo_root("C:\\repo\\SEMBRON\\"))
    assert got.endswith("SEMBRON")
    assert not got.endswith("\\")
    assert not got.endswith("/")
    posix = str(normalize_repo_root("/repo/semblon/"))
    assert posix.endswith("semblon")
    assert not posix.endswith("/")


def test_interactive_script_path(tmp_path):
    p = interactive_script_path(tmp_path)
    assert p == tmp_path.resolve() / "tools" / "semblon-interactive.ps1"


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

    q = make_event(STAGE_PROCESS, KIND_QUEUED, path="D:/photos")
    assert "process:queued" in format_progress_line(q)


def test_home_wires_watchdog_and_optional_observers():
    import inspect

    from semblon import home_ui

    src = inspect.getsource(home_ui)
    assert "Watchdog" in src
    assert "KIND_STALLED" in src
    assert HOME_OBSERVERS == "face,color,object"
    assert "observers=HOME_OBSERVERS" in src
    assert "btn_resume" in src
    assert 'text="Resume"' in src
    assert "StillProgressBar" in src
    assert format_people_lines({"items": []})[0].startswith("No named people")
