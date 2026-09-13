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


def test_cli_profile_glued_out_exits_2():
    from semblon.cli import main

    glued = r"docs\runtime.mdC:\Users\S8633\Documents\GITHUB\SEMBRON\semblon\.venv\Scripts"
    # Validation runs before model load — image need not exist.
    assert main(["lab", "profile", "--image", "nope.jpg", "--out", glued]) == 2
