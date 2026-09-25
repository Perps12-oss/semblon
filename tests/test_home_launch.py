"""Production Home launch installs lens_home before Tk."""

from __future__ import annotations

import inspect

from semblon.lens_home import install, open_region_select, run_product_home


def test_product_home_installs_handler():
    src = inspect.getsource(run_product_home)
    assert "install(HomeApp)" in src
    assert "run_home_ui" in src


def test_cli_home_uses_product_launch():
    import semblon.cli as cli

    src = inspect.getsource(cli.main)
    assert "run_product_home" in src
    assert "from semblon.lens_home import run_product_home" in src
    # The raw Home constructor path must not be the production command.
    home_block = src.split('cmd == "home"', 1)[1].split('cmd == "shell"', 1)[0]
    assert "run_product_home" in home_block
    assert "return run_home_ui" not in home_block


def test_install_replaces_region_select():
    class Fake:
        _open_region_select = None

    install(Fake)
    assert Fake._open_region_select is open_region_select
