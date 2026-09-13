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
    for cmd in ("lab", "ingest", "cluster", "export", "name", "merge", "split"):
        assert cmd in out


def test_main_py_present():
    root = Path(__import__("semblon").__file__).resolve().parent
    assert (root / "__main__.py").is_file()
