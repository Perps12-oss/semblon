"""Application API contract — Home/Review are JobEngine clients only."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import semblon.application as application
from semblon.home_ui import HomeApp
from semblon.jobs import JobBusy, JobEngine, STATE_CANCELLING
from semblon.review_ui import ReviewApp

ROOT = Path(__file__).resolve().parents[1]


def _module_calls_process_folder(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "process_folder":
            return True
        if isinstance(node, ast.Name) and node.id == "process_folder":
            return True
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(a.name == "process_folder" for a in node.names):
                return True
    return False


def test_application_exports_match_contract_surface():
    required = {
        "JobBusy",
        "JobEngine",
        "JobHandle",
        "JobResult",
        "STATE_IDLE",
        "STATE_RUNNING",
        "STATE_PAUSED",
        "STATE_CANCELLING",
        "board",
        "activity",
        "inbox",
        "load_canvas",
        "search_people",
        "search_person",
        "home_control_states",
        "apply_name",
        "apply_merge",
        "apply_split",
        "apply_ignore",
        "apply_note",
        "apply_rule_out",
        "default_store_path",
        "latest_run_id",
        "resolve_run_id",
    }
    assert required.issubset(set(application.__all__))
    for name in required:
        assert hasattr(application, name), name
    assert application.STATE_CANCELLING == STATE_CANCELLING


def test_home_and_review_never_call_process_folder_directly():
    """No second ingest door in Tk clients — JobEngine owns process_folder."""
    home = ROOT / "semblon" / "home_ui.py"
    review = ROOT / "semblon" / "review_ui.py"
    assert not _module_calls_process_folder(home)
    assert not _module_calls_process_folder(review)
    home_src = inspect.getsource(HomeApp)
    assert "submit_ingest" in home_src
    init = inspect.getsource(HomeApp.__init__)
    assert "Application(" in init
    assert "self.engine = self.app.engine" in init
    assert "JobEngine(" not in init
    review_src = inspect.getsource(ReviewApp)
    assert "submit_ingest" not in review_src
    assert "JobEngine" not in review_src


def test_application_facade_does_not_own_ingest_worker():
    src = Path(application.__file__).read_text(encoding="utf-8")
    assert "process_folder" not in src
    assert "threading.Thread" not in src
    assert "JobEngine" in application.__all__


def test_cli_headless_process_is_separate_from_home_client():
    """CLI process may call process_folder; Home must still go through JobEngine."""
    from semblon import cli

    cli_src = Path(cli.__file__).read_text(encoding="utf-8")
    assert "process_folder" in cli_src
    home = ROOT / "semblon" / "home_ui.py"
    assert not _module_calls_process_folder(home)
    assert "JobEngine" in home.read_text(encoding="utf-8")
    assert "submit_ingest" in home.read_text(encoding="utf-8")
    # JobBusy / single-door behaviour covered in tests/test_jobs.py
    assert issubclass(JobBusy, RuntimeError)
    assert hasattr(JobEngine, "submit_ingest")
