"""Production Home launch starts Tk without patching HomeApp."""

from __future__ import annotations

import inspect

from semblon.lens_home import open_region_select, run_product_home


def test_product_home_does_not_patch_home():
    src = inspect.getsource(run_product_home)
    assert "install(" not in src
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


def test_region_select_calls_similar_search_directly():
    import semblon.application as application
    import semblon.home_ui as home_ui

    method = inspect.getsource(home_ui.HomeApp._open_region_select)
    assert "open_region_select(self)" in method
    assert "run_lens_query" not in method
    handler = inspect.getsource(open_region_select)
    assert "remember_selection" in handler
    assert "run_lens_query" not in handler
    init = inspect.getsource(application.Application.__init__)
    assert "install(" not in init
    assert "_install_lens_home" not in init
    ask = inspect.getsource(home_ui.HomeApp._lens_ask_whole)
    assert "run_lens_query" in ask
    assert "remember_selection" not in ask
    assert "x=" not in ask
