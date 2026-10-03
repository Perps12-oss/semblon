"""MediaGridViewModel + density + virtualization helpers."""

from __future__ import annotations

from semblon.media_grid import (
    DENSITY_COMPACT,
    DENSITY_COMFORTABLE,
    build_media_grid,
    density_geometry,
    visible_index_range,
)


def test_build_viewmodel_rows_only():
    rows = [
        {"media_id": "a", "path": r"C:\lib\x.jpg", "source_type": "folder"},
        {"media_id": "b", "path": r"C:\lib\y.png", "source_type": "folder"},
    ]
    vm = build_media_grid(rows, density=DENSITY_COMPACT, compare_marks={"a"})
    assert vm.filtered_count == 2
    assert vm.density == DENSITY_COMPACT
    assert vm.items[0].label == "x.jpg"
    assert vm.items[0].compare_marked is True
    assert vm.items[1].compare_marked is False
    # No heavy fields — presentation only.
    assert not hasattr(vm.items[0], "embedding")


def test_density_geometry_and_visible_range():
    c = density_geometry(DENSITY_COMFORTABLE)
    k = density_geometry(DENSITY_COMPACT)
    assert k["cell"] < c["cell"]
    start, end = visible_index_range(
        scroll_top=0,
        viewport_h=400,
        cell=156,
        pad=8,
        label_band=18,
        cols=4,
        total=200,
        overscan_rows=2,
    )
    assert start == 0
    assert 0 < end <= 200
    start2, end2 = visible_index_range(
        scroll_top=2000,
        viewport_h=400,
        cell=156,
        pad=8,
        label_band=18,
        cols=4,
        total=200,
        overscan_rows=2,
    )
    assert start2 > 0
    assert end2 > start2
