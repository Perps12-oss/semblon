"""Phase 2 density-aware temporal ribbon — mark budget, stability, diversity."""

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
    months = month_cells_for_year(days, 2024, media_ids=[f"m{i:05d}" for i in range(len(days))])
    assert mark_count_for_months(days, 2024) == 2
    assert len(months) == 2
    assert {m.key for m in months} == {"2024-08", "2024-07"}
    assert sum(m.photo_count for m in months) == 10000
    for cell in months:
        assert len(cell.sample_ids) <= min(MONTH_SAMPLE_BUDGET, CELL_MOSAIC_MAX)
        assert cell.photo_count >= 5000


def test_year_overview_is_one_cell_per_populated_year():
    days = (
        ["2025-01-01"] * 3
        + _july_august_burst(2024, 4000, 4000)
        + ["2021-06-15"] * 10
    )
    ids = [f"m{i:05d}" for i in range(len(days))]
    cells = year_cells(days, media_ids=ids)
    years = [c for c in cells if c.kind == "year"]
    assert [c.year for c in years] == [2025, 2024, 2021]
    dense = next(c for c in years if c.year == 2024)
    assert dense.photo_count == 8000
    assert len(dense.sample_ids) <= YEAR_SAMPLE_BUDGET


def test_day_cells_are_one_per_populated_day_not_per_photo():
    days = []
    for day in range(1, 11):
        days.extend([f"2024-07-{day:02d}"] * 200)
    ids = [f"m{i:05d}" for i in range(len(days))]
    cells = day_cells_for_month(days, "2024-07", media_ids=ids)
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


def test_sample_ids_stable_across_row_reorder_not_db_order():
    """Same media set in a different row order must keep the same sampleIds."""
    days = [f"2024-07-{1 + (i % 10):02d}" for i in range(40)] + [
        f"2024-08-{1 + (i % 10):02d}" for i in range(40)
    ]
    ids = [f"id-{i:03d}" for i in range(len(days))]
    # Reverse the archive order but keep (day, id) pairs together.
    pairs = list(zip(days, ids))
    rev_days = [p[0] for p in reversed(pairs)]
    rev_ids = [p[1] for p in reversed(pairs)]
    a = month_cells_for_year(days, 2024, media_ids=ids)
    b = month_cells_for_year(rev_days, 2024, media_ids=rev_ids)
    assert {c.key: set(c.sample_ids) for c in a} == {c.key: set(c.sample_ids) for c in b}


def test_burst_day_cannot_monopolise_month_preview_slots():
    """9000 on one day + sparse other days → samples span multiple days."""
    days: list[str] = []
    ids: list[str] = []
    # Burst on the 15th.
    for i in range(9000):
        days.append("2024-07-15")
        ids.append(f"burst-{i:05d}")
    # Sparse days with unique ids.
    for day in (1, 2, 3, 4, 5, 20, 21, 22):
        for j in range(20):
            days.append(f"2024-07-{day:02d}")
            ids.append(f"sparse-{day:02d}-{j:02d}")
    cells = month_cells_for_year(days, 2024, media_ids=ids)
    july = next(c for c in cells if c.key == "2024-07")
    assert len(july.sample_ids) == MONTH_SAMPLE_BUDGET
    # Map samples back to days via id prefixes.
    sample_days = set()
    id_to_day = dict(zip(ids, days))
    for mid in july.sample_ids:
        sample_days.add(id_to_day[mid])
    assert len(sample_days) >= 2, f"burst dominated samples: {july.sample_ids}"


def test_empty_months_inside_year_are_omitted():
    days = [f"2024-03-{1 + i:02d}" for i in range(5)] + [f"2024-11-{1 + i:02d}" for i in range(5)]
    months = month_cells_for_year(days, 2024, media_ids=[f"m{i}" for i in range(10)])
    assert [m.key for m in months] == ["2024-11", "2024-03"]
    assert mark_count_for_months(days, 2024) == 2


def test_contextual_preview_budget_stays_at_most_four_representatives():
    days = _july_august_burst(2024, 5000, 5000)
    ids = [f"m{i:05d}" for i in range(len(days))]
    months = month_cells_for_year(days, 2024, media_ids=ids)
    for cell in months:
        assert len(cell.sample_ids) <= CELL_MOSAIC_MAX
    days_cells = day_cells_for_month(days, "2024-07", media_ids=ids)
    for cell in days_cells:
        assert len(cell.sample_ids) <= CELL_MOSAIC_MAX


def test_media_ids_path_keeps_sample_budget_on_100k_without_id_at():
    """100k-scale with a media_ids vector: samples stay capped; no id_at traffic."""
    days = [f"2020-01-{(i % 28) + 1:02d}" for i in range(100_000)]
    ids = [f"big-{i:06d}" for i in range(100_000)]
    seen: list[int] = []

    def id_at(i: int) -> str:
        seen.append(i)
        return ids[i]

    cells = year_cells(days, media_ids=ids, id_at=id_at)
    assert len(cells) == 1
    assert cells[0].photo_count == 100_000
    assert len(cells[0].sample_ids) <= YEAR_SAMPLE_BUDGET
    # media_ids path must not fall back to id_at.
    assert seen == []
