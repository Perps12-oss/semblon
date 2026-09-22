"""Native production shell — Application API client. Optional PySide6."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from semblon.native_shell import run_native_shell


def test_native_shell_package_has_no_identity_or_ingest_imports():
    root = Path(__file__).resolve().parents[1] / "semblon" / "native_shell"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "from semblon.process import process_folder" not in text
        assert "from semblon.ingest" not in text
        assert "insightface" not in text.lower()
        assert "FaceAnalysis" not in text


def test_native_shell_uses_application_pause_commands():
    pytest.importorskip("PySide6")
    from semblon.native_shell import window as win_mod

    src = inspect.getsource(win_mod.ShellWindow)
    assert "pause_job" in src
    assert "unpause_job" in src
    assert "cancel_job" in src
    assert "submit_ingest" in src
    assert "from semblon.process import process_folder" not in src


def test_run_native_shell_exits_when_pyside_missing(tmp_path, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "PySide6" or name.startswith("PySide6."):
            raise ImportError("test: no pyside")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(SystemExit) as ei:
        run_native_shell(store=tmp_path / "s.sqlite")
    assert ei.value.code == 2


def test_cli_registers_shell_command():
    from semblon.cli import main
    import io
    from contextlib import redirect_stderr, redirect_stdout

    buf = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        try:
            main(["shell", "--help"])
        except SystemExit as e:
            assert e.code == 0
    text = buf.getvalue() + err.getvalue()
    assert "native production shell" in text.lower() or "JobEngine" in text or "--store" in text
