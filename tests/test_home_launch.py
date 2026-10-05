"""Legacy Tk launch does not monkeypatch HomeApp."""

from __future__ import annotations

import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_home_launch_does_not_install_lens():
    import semblon.cli as cli
    import semblon.home_ui as home_ui

    src = inspect.getsource(cli.main)
    home_block = src.split('cmd == "home"', 1)[1].split('cmd == "shell"', 1)[0]
    assert "run_home_ui" in home_block
    assert "lens_home" not in home_block
    assert "install(" not in home_block
    assert not (ROOT / "semblon" / "lens_home.py").exists()
    app = (ROOT / "semblon" / "application.py").read_text(encoding="utf-8")
    assert "home_ui" not in app
    assert "lens_home" not in app
    assert "_install_lens_home" not in app
    region = inspect.getsource(home_ui.HomeApp._open_region_select)
    assert "remember_selection" in region
    assert "on_rect" in region
    # The method is the implementation. Nothing assigns over it.
    text = (ROOT / "semblon" / "home_ui.py").read_text(encoding="utf-8")
    assert "HomeApp._open_region_select =" not in text
    assert "lens_home" not in text


def test_shell_is_the_forward_gui_command():
    import semblon.cli as cli

    src = inspect.getsource(cli.main)
    shell = src.split('cmd == "shell"', 1)[1].split('cmd == "stats"', 1)[0]
    assert "run_native_shell" in shell
    assert "forward" in src.lower() or "PySide6" in src
