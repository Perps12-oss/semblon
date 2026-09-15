"""FACE-000 --out path validation (no InsightFace)."""

from __future__ import annotations

from pathlib import Path

import pytest

from semblon.profile import ProfileError, validate_out_path


def test_validate_out_accepts_normal_paths():
    assert validate_out_path(Path("docs/runtime.md")) == Path("docs/runtime.md")
    assert validate_out_path(Path(r"docs\runtime.md")) == Path(r"docs\runtime.md")
    p = Path(r"C:\Users\me\runtime.md")
    assert validate_out_path(p) == p


def test_validate_out_rejects_glued_windows_path():
    glued = Path(r"docs\runtime.mdC:\Users\S8633\Documents\GITHUB\SEMBRON\semblon\.venv\Scripts")
    with pytest.raises(ProfileError, match="glued together"):
        validate_out_path(glued)


def test_rss_mb_on_windows():
    import sys

    from semblon.profile import _rss_mb

    if sys.platform != "win32":
        pytest.skip("windows peak RSS")
    val = _rss_mb()
    assert val is not None and val > 0


def test_write_runtime_md_upserts_sections(tmp_path):
    from semblon.profile import write_runtime_md

    out = tmp_path / "runtime.md"
    write_runtime_md(out, {"os": "windows", "arch": "x64", "execution": "emulated", "n": 1})
    write_runtime_md(out, {"os": "windows", "arch": "arm64", "execution": "native", "n": 2})
    write_runtime_md(out, {"os": "windows", "arch": "x64", "execution": "emulated", "n": 3})
    text = out.read_text(encoding="utf-8")
    assert text.count("## windows x64 emulated") == 1
    assert text.count("## windows arm64 native") == 1
    assert '"n": 3' in text
    assert '"n": 1' not in text


def test_cli_profile_glued_out_exits_2():
    from semblon.cli import main

    glued = r"docs\runtime.mdC:\Users\S8633\Documents\GITHUB\SEMBRON\semblon\.venv\Scripts"
    # Validation runs before model load — image need not exist.
    assert main(["lab", "profile", "--image", "nope.jpg", "--out", glued]) == 2
