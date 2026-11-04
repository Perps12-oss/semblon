"""Phase 2 density-aware temporal ribbon — mark budget and sampling."""

from __future__ import annotations

from semblon.native_shell.temporal_ribbon import (
    CELL_MOSAIC_MAX,
    MONTH_SAMPLE_BUDGET,
    YEAR_SAMPLE_BUDGET,
    day_cells_for_month,
    mark_count_for_months,
    month_cells_for_year,
    year_cells,
)


def _july_august_burst(year: int = 2024, july: int = 5000, august: int = 5000) -> list[str]:
    """10k photographs in July and August of one year (newest-first day keys)."""
    days: list[str] = []
    # Newest first: August then July, matching archive browse order.
    for i in range(august):
        day = 1 + (i % 31)
        days.append(f"{year}-08-{day:02d}")
    for i in range(july):
        day = 1 + (i % 31)
        days.append(f"{year}-07-{day:02d}")
    return days


def test_ten_thousand_july_august_yield_two_month_cells_not_ten_thousand_marks():
    """Acceptance: 10k Jul+Aug → two coherent month cells, not 10k competing marks."""
    days = _july_august_burst(2024, 5000, 5000)
    assert len(days) == 10000
    months = month_cells_for_year(days, 2024)
    assert mark_count_for_months(days, 2024) == 2
    assert len(months) == 2
    assert {m.key for m in months} == {"2024-08", "2024-07"}
    assert sum(m.photo_count for m in months) == 10000
    # Sample budget is capped — mosaic tiles cannot explode with density.
    for cell in months:
        assert len(cell.sample_ids) <= min(MONTH_SAMPLE_BUDGET, CELL_MOSAIC_MAX)
        assert cell.photo_count >= 5000


def test_year_overview_is_one_cell_per_populated_year():
    days = (
        ["2025-01-01"] * 3
        + _july_august_burst(2024, 4000, 4000)
        + ["2021-06-15"] * 10
    )
    cells = year_cells(days)
    years = [c for c in cells if c.kind == "year"]
    assert [c.year for c in years] == [2025, 2024, 2021]
    dense = next(c for c in years if c.year == 2024)
    assert dense.photo_count == 8000
    assert len(dense.sample_ids) <= YEAR_SAMPLE_BUDGET


def test_day_cells_are_one_per_populated_day_not_per_photo():
    days = []
    for day in range(1, 11):
        days.extend([f"2024-07-{day:02d}"] * 200)  # 2000 photos, 10 days
    cells = day_cells_for_month(days, "2024-07")
    assert len(cells) == 10
    assert sum(c.photo_count for c in cells) == 2000
    for cell in cells:
        assert cell.photo_count == 200
        assert len(cell.sample_ids) <= CELL_MOSAIC_MAX


def test_sampling_is_deterministic_for_same_archive():
    days = _july_august_burst(2023, 1200, 800)
    ids = [f"m{i:05d}" for i in range(len(days))]
    a = month_cells_for_year(days, 2023, media_ids=ids)
    b = month_cells_for_year(days, 2023, media_ids=ids)
    assert [c.sample_ids for c in a] == [c.sample_ids for c in b]
    assert [c.key for c in a] == [c.key for c in b]


def test_empty_months_inside_year_are_omitted():
    days = [f"2024-03-{1 + i:02d}" for i in range(5)] + [f"2024-11-{1 + i:02d}" for i in range(5)]
    months = month_cells_for_year(days, 2024)
    assert [m.key for m in months] == ["2024-11", "2024-03"]
    assert mark_count_for_months(days, 2024) == 2


def test_contextual_preview_budget_stays_at_most_four_representatives():
    """Preview panel may show ≤4 actual photographs — never a dense gallery."""
    days = _july_august_burst(2024, 5000, 5000)
    ids = [f"m{i:05d}" for i in range(len(days))]
    months = month_cells_for_year(days, 2024, media_ids=ids)
    for cell in months:
        assert len(cell.sample_ids) <= CELL_MOSAIC_MAX
    days_cells = day_cells_for_month(days, "2024-07", media_ids=ids)
    for cell in days_cells:
        assert len(cell.sample_ids) <= CELL_MOSAIC_MAX
