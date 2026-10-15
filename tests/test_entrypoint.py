"""Install / entry-point smoke — no InsightFace."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_cli_help_exits_zero():
    from semblon.cli import main

    try:
        main(["--help"])
    except SystemExit as e:
        assert e.code == 0


def test_python_m_semblon_help():
    proc = subprocess.run(
        [sys.executable, "-m", "semblon", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    out = proc.stdout + proc.stderr
    for cmd in (
        "lab",
        "ingest",
        "process",
        "cluster",
        "export",
        "name",
        "merge",
        "split",
        "shell",
        "tracks",
        "memory",
        "identify",
        "inbox",
        "stats",
        "report",
        "search",
    ):
        assert cmd in out, cmd
    assert "home" not in out.split()
    assert "review-ui" not in out.split()
    assert "canvas" not in out.split()
    assert "desktop" not in out.split()
    from semblon.cli import main as _main
    import io
    from unittest.mock import patch

    buf = io.StringIO()
    with patch("sys.stdout", buf):
        try:
            _main(["lab", "--help"])
        except SystemExit as e:
            assert e.code == 0
    lab = buf.getvalue()
    assert "integrity" in lab
    assert "models" in lab
    assert "backup" in lab


def test_main_py_present():
    root = Path(__import__("semblon").__file__).resolve().parent
    assert (root / "__main__.py").is_file()


def test_packaging_hygiene():
    import tomllib

    from semblon import __version__

    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    extras = data["project"].get("optional-dependencies", {})
    assert "cluster" not in extras
    assert "gui" in extras
    scripts = data["project"]["scripts"]
    assert scripts["semblon"] == "semblon.cli:main"
    assert "semblon-desktop" not in scripts
    req = data["project"]["requires-python"]
    assert req.startswith(">=3.11")
    assert "<3.15" in req
    assert "version" in data["project"]["dynamic"]
    assert __version__
    assert not (root / "semblon" / "desktop").exists()
    assert (root / "semblon" / "ui_copy.py").is_file()
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "semblon shell" in readme or "PySide6" in readme
    assert "semblon-desktop" not in readme
    assert "s8_toolkit_spike" in readme and "research spike" in readme
    assert not (root / "tools" / "s8_toolkit_spike" / "__init__.py").exists()
