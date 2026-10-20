from __future__ import annotations

import pytest

from semblon.native_shell.screen_query_overlay import _union_bounds


def test_union_bounds_handles_multi_monitor_layout():
    # primary (0,0), left monitor, and one below
    bounds = [
        (0, 0, 1920, 1080),
        (-1600, 100, 1600, 900),
        (100, 1080, 1280, 1024),
    ]
    assert _union_bounds(bounds) == (-1600, 0, 3520, 2104)


def test_union_bounds_requires_at_least_one_screen():
    with pytest.raises(ValueError):
        _union_bounds([])

