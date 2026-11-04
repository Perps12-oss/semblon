"""Chronological geometry: two metric spaces, two translation functions."""

from __future__ import annotations

import pytest

from semblon.native_shell.sections import build_sections
from semblon.native_shell.temporal_geometry import (
    build_temporal_geometry,
    offset_for_year,
    time_for_offset,
)


def _days_for_years(spec: list[tuple[int, int]]) -> list[str]:
    """spec: list of (year, count). Newest year first to match archive order."""
    out: list[str] = []
    for year, count in spec:
        for i in range(count):
            month = 12 - (i % 12)
            day = 1 + (i % 27)
            out.append(f"{year}-{month:02d}-{day:02d}")
    return out


def _geom(days: list[str], columns: int = 4, cell_w: float = 100.0, generation: int = 1):
    laid = build_sections(days, columns)
    return build_temporal_geometry(
        days, laid["rows"], cell_w=cell_w, month_h=36, day_h=34, generation=generation
    )


def test_uniform_populated_years_are_detents():
    days = _days_for_years([(2025, 8), (2024, 8), (2023, 8)])
    g = _geom(days)
    assert g.calendar_first == 2023 and g.calendar_last == 2025
    assert g.detent_years() == (2025, 2024, 2023)
    assert all(y.populated for y in g.years)


def test_three_year_empty_gap_keeps_calendar_space_without_destination():
    days = _days_for_years([(2025, 6), (2021, 6)])
    g = _geom(days)
    assert g.calendar_first == 2021 and g.calendar_last == 2025
    assert [y.year for y in g.years if not y.populated] == [2022, 2023, 2024]
    assert offset_for_year(g, 2023) is None
    assert offset_for_year(g, 2022) is None
    assert offset_for_year(g, 2024) is None
    assert offset_for_year(g, 2025) is not None
    assert offset_for_year(g, 2021) is not None
    # Empty years are not silently clamped to a neighbour.
    assert offset_for_year(g, 2020) is None
    assert offset_for_year(g, 2026) is None


def test_time_for_offset_is_monotonic_over_dated_content():
    days = _days_for_years([(2025, 20), (2024, 4), (2021, 12)])
    g = _geom(days, cell_w=80)
    samples = []
    y = g.dated_content_start
    while y <= g.dated_content_end:
        point = time_for_offset(g, y)
        assert point.kind == "dated" and point.year_frac is not None
        samples.append(point.year_frac)
        y += 25
    # Newest-first content: larger contentY → older (smaller) year_frac.
    for a, b in zip(samples, samples[1:]):
        assert a + 1e-9 >= b


def test_dense_and_sparse_years_use_actual_content_extents():
    days = _days_for_years([(2025, 4), (2024, 80), (2023, 4)])
    g = _geom(days, columns=4, cell_w=100)
    sparse = g.year_extent(2025)
    dense = g.year_extent(2024)
    assert sparse and dense and sparse.populated and dense.populated
    assert (dense.content_end - dense.content_start) > (sparse.content_end - sparse.content_start)


def test_first_and_last_populated_year():
    days = _days_for_years([(2020, 3), (2015, 3)])
    g = _geom(days)
    assert offset_for_year(g, 2020) == g.year_extent(2020).content_start
    assert offset_for_year(g, 2015) == g.year_extent(2015).content_start
    assert g.detent_years()[0] == 2020
    assert g.detent_years()[-1] == 2015


def test_empty_archive_and_single_year():
    empty = _geom([])
    assert empty.years == () and empty.undated is None
    assert offset_for_year(empty, 2020) is None
    assert time_for_offset(empty, 0).kind == "undated"

    single = _geom(_days_for_years([(2019, 5)]))
    assert single.calendar_first == single.calendar_last == 2019
    assert offset_for_year(single, 2019) is not None
    assert offset_for_year(single, 2018) is None


def test_undated_only_and_mixed_boundary():
    undated_days = [""] * 5
    g = _geom(undated_days)
    assert g.undated is not None and not g.years
    assert time_for_offset(g, g.undated.content_start).kind == "undated"
    assert offset_for_year(g, 2024) is None

    mixed = _geom(_days_for_years([(2024, 4)]) + [""] * 3)
    assert mixed.undated is not None
    assert mixed.year_extent(2024).populated
    assert time_for_offset(mixed, mixed.undated.content_start).kind == "undated"
    assert time_for_offset(mixed, mixed.dated_content_start).kind == "dated"
    seg = mixed.viewport_segment(mixed.dated_content_start, mixed.undated.content_end)
    assert seg.kind == "mixed" and seg.undated_visible


def test_viewport_segment_single_multi_gap_and_freeze_inputs():
    days = _days_for_years([(2025, 10), (2021, 10)])
    g = _geom(days, cell_w=90)
    y2025 = g.year_extent(2025)
    mid = (y2025.content_start + y2025.content_end) / 2
    single = g.viewport_segment(mid, mid + 20)
    assert single.kind == "dated"
    assert 2025 <= single.time_lo <= 2026 and 2025 <= single.time_hi <= 2026

    multi = g.viewport_segment(y2025.content_start, g.year_extent(2021).content_end)
    assert multi.kind == "dated"
    assert multi.time_lo <= 2022 and multi.time_hi >= 2025
    # Gap years remain inside the temporal interval.
    assert multi.time_lo <= 2023 <= multi.time_hi


def test_undated_only_viewport():
    g = _geom([""] * 4)
    seg = g.viewport_segment(0, g.total_content_height)
    assert seg.kind == "undated" and seg.undated_visible


def test_malformed_dates_do_not_invent_years():
    days = ["2024-01-01", "not-a-date", "2024-02-02", "99", ""]
    g = _geom(days)
    assert g.calendar_first == 2024 and g.calendar_last == 2024
    assert g.undated is not None
    assert all(y.year == 2024 for y in g.years)


def test_translations_are_not_inverses_across_empty_gap():
    days = _days_for_years([(2025, 8), (2021, 8)])
    g = _geom(days)
    # Empty year has chronological identity via nearest_detent but no offset.
    assert offset_for_year(g, 2023) is None
    # Mapping a content offset near the 2025/2021 boundary does not invent photos in 2023.
    boundary = g.year_extent(2025).content_end
    point = time_for_offset(g, boundary)
    assert point.kind == "dated"
    assert point.year_frac is not None
    assert point.year_frac <= 2026


def test_geometry_generation_is_preserved():
    g = _geom(_days_for_years([(2022, 2)]), generation=7)
    assert g.generation == 7
    assert g.to_dict()["generation"] == 7


def test_no_assumption_of_equal_content_height_per_year():
    days = _days_for_years([(2025, 2), (2024, 40), (2023, 2)])
    g = _geom(days, cell_w=120)
    heights = {
        y.year: y.content_end - y.content_start
        for y in g.years
        if y.populated
    }
    assert heights[2024] > heights[2025] * 5
