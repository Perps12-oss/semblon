"""Density-aware temporal ribbon for the archive time strip (Phase 2).

The strip is a miniature temporal lens: calendar overview first, then local
hover magnification year → month → day. Visual marks are capped per period so
dense months stay coherent cells — never one mark per photograph.

Acceptance: 10,000 photographs in July and August produce two coherent month
cells under year magnification, not 10,000 competing marks.

Thumbnails and colours come only from existing thumb caches. No new analysis,
indexing, schema columns, or identity work.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Sequence

from semblon.native_shell.sections import month_key

# Fixed sample budgets — density cannot inflate the mark count.
YEAR_SAMPLE_BUDGET = 16
MONTH_SAMPLE_BUDGET = 4
DAY_SAMPLE_BUDGET = 2
# Tiny mosaic tiles inside one month/day cell (Phase 2 colour / Phase 3 preview prep).
CELL_MOSAIC_MAX = 4


@dataclass(frozen=True)
class PeriodCell:
    """One coherent visual cell for a calendar period."""

    kind: str  # "year" | "month" | "day" | "undated"
    key: str  # "YYYY" | "YYYY-MM" | "YYYY-MM-DD" | "undated"
    year: int | None
    month: int | None
    day: int | None
    photo_count: int
    photo_first: int
    sample_ids: tuple[str, ...]
    # Optional #RRGGBB from cached thumbs; None → uniform-track fallback.
    color: str | None = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "key": self.key,
            "year": self.year if self.year is not None else -1,
            "month": self.month if self.month is not None else -1,
            "day": self.day if self.day is not None else -1,
            "photoCount": self.photo_count,
            "photoFirst": self.photo_first,
            "sampleIds": list(self.sample_ids),
            "color": self.color or "",
            "mosaicMax": CELL_MOSAIC_MAX,
        }


def _parse_day(day: str) -> tuple[int, int, int] | None:
    text = str(day or "")
    if len(text) < 10 or text[4] != "-" or text[7] != "-":
        return None
    if not (text[:4].isdigit() and text[5:7].isdigit() and text[8:10].isdigit()):
        return None
    year, month, day_n = int(text[:4]), int(text[5:7]), int(text[8:10])
    if month < 1 or month > 12 or day_n < 1 or day_n > 31:
        return None
    return year, month, day_n


def _stable_sample(indices: Sequence[int], budget: int, salt: str) -> list[int]:
    """Pick up to ``budget`` indices deterministically from a contiguous period.

    Evenly spaced along the period, then stably ordered by a media-keyed hash
    so the same archive always yields the same representatives.
    """
    n = len(indices)
    if n <= 0 or budget <= 0:
        return []
    if n <= budget:
        return list(indices)
    # Even coverage across the period (not a random cluster at one end).
    spaced: list[int] = []
    for i in range(budget):
        at = int(round(i * (n - 1) / max(budget - 1, 1)))
        spaced.append(indices[at])
    # Deduplicate while preserving spread order.
    seen: set[int] = set()
    unique: list[int] = []
    for idx in spaced:
        if idx in seen:
            continue
        seen.add(idx)
        unique.append(idx)
    # Stable tie-break: hash(salt + index) sorts a secondary order for display.
    unique.sort(key=lambda i: (hashlib.sha1(f"{salt}:{i}".encode()).hexdigest(), i))
    return unique[:budget]


def index_periods(days: Sequence[str]) -> dict:
    """Build year / month / day index maps (photo indices only)."""
    years: dict[str, list[int]] = {}
    months: dict[str, list[int]] = {}
    day_map: dict[str, list[int]] = {}
    undated: list[int] = []
    for i, day in enumerate(days):
        parsed = _parse_day(day)
        if parsed is None:
            undated.append(i)
            continue
        year, month, _ = parsed
        years.setdefault(f"{year:04d}", []).append(i)
        months.setdefault(f"{year:04d}-{month:02d}", []).append(i)
        day_map.setdefault(str(day), []).append(i)
    return {
        "years": years,
        "months": months,
        "days": day_map,
        "undated": undated,
    }


def _ids_for(indices: Iterable[int], media_ids: Sequence[str] | None) -> tuple[str, ...]:
    if not media_ids:
        return tuple(f"idx:{i}" for i in indices)
    out: list[str] = []
    for i in indices:
        if 0 <= i < len(media_ids):
            out.append(str(media_ids[i]))
        else:
            out.append(f"idx:{i}")
    return tuple(out)


def year_cells(
    days: Sequence[str],
    *,
    media_ids: Sequence[str] | None = None,
    colors: dict[str, str] | None = None,
) -> list[PeriodCell]:
    """One coherent cell per populated calendar year — ``O(years)``, never ``O(photos)``."""
    index = index_periods(days)
    cells: list[PeriodCell] = []
    # Newest year first (strip reading order).
    for key in sorted(index["years"].keys(), reverse=True):
        idxs = index["years"][key]
        sample = _stable_sample(idxs, YEAR_SAMPLE_BUDGET, key)
        year = int(key)
        cells.append(
            PeriodCell(
                kind="year",
                key=key,
                year=year,
                month=None,
                day=None,
                photo_count=len(idxs),
                photo_first=idxs[0],
                sample_ids=_ids_for(sample, media_ids),
                color=(colors or {}).get(key),
            )
        )
    if index["undated"]:
        idxs = index["undated"]
        sample = _stable_sample(idxs, YEAR_SAMPLE_BUDGET, "undated")
        cells.append(
            PeriodCell(
                kind="undated",
                key="undated",
                year=None,
                month=None,
                day=None,
                photo_count=len(idxs),
                photo_first=idxs[0],
                sample_ids=_ids_for(sample, media_ids),
                color=(colors or {}).get("undated"),
            )
        )
    return cells


def month_cells_for_year(
    days: Sequence[str],
    year: int,
    *,
    media_ids: Sequence[str] | None = None,
    colors: dict[str, str] | None = None,
) -> list[PeriodCell]:
    """Populated months inside one year — at most 12 cells, never one per photo."""
    index = index_periods(days)
    prefix = f"{int(year):04d}-"
    cells: list[PeriodCell] = []
    for key in sorted((k for k in index["months"] if k.startswith(prefix)), reverse=True):
        idxs = index["months"][key]
        sample = _stable_sample(idxs, MONTH_SAMPLE_BUDGET, key)
        month = int(key[5:7])
        cells.append(
            PeriodCell(
                kind="month",
                key=key,
                year=int(year),
                month=month,
                day=None,
                photo_count=len(idxs),
                photo_first=idxs[0],
                sample_ids=_ids_for(sample, media_ids)[:CELL_MOSAIC_MAX],
                color=(colors or {}).get(key),
            )
        )
    return cells


def day_cells_for_month(
    days: Sequence[str],
    month_key_str: str,
    *,
    media_ids: Sequence[str] | None = None,
    colors: dict[str, str] | None = None,
) -> list[PeriodCell]:
    """Populated days inside one month — one cell per day that has photographs."""
    mk = month_key(month_key_str) or str(month_key_str)
    if len(mk) < 7:
        return []
    index = index_periods(days)
    cells: list[PeriodCell] = []
    for key in sorted((k for k in index["days"] if k.startswith(mk)), reverse=True):
        idxs = index["days"][key]
        sample = _stable_sample(idxs, DAY_SAMPLE_BUDGET, key)
        parsed = _parse_day(key)
        if parsed is None:
            continue
        year, month, day_n = parsed
        cells.append(
            PeriodCell(
                kind="day",
                key=key,
                year=year,
                month=month,
                day=day_n,
                photo_count=len(idxs),
                photo_first=idxs[0],
                sample_ids=_ids_for(sample, media_ids)[:CELL_MOSAIC_MAX],
                color=(colors or {}).get(key),
            )
        )
    return cells


def mark_count_for_months(days: Sequence[str], year: int) -> int:
    """How many month visual marks year-magnification must emit (density invariant)."""
    return len(month_cells_for_year(days, year))


def aggregate_color_from_images(images) -> str | None:
    """Mean sRGB of non-null images as ``#RRGGBB``. Empty → ``None`` (fallback)."""
    total_r = total_g = total_b = 0
    n = 0
    for image in images:
        if image is None or getattr(image, "isNull", lambda: True)():
            continue
        # Tiny average: scale to 1×1 via scaled copy when available.
        try:
            tiny = image.scaled(1, 1)
            if tiny.isNull():
                continue
            c = tiny.pixelColor(0, 0)
            total_r += c.red()
            total_g += c.green()
            total_b += c.blue()
            n += 1
        except Exception:
            continue
    if n <= 0:
        return None
    return f"#{total_r // n:02x}{total_g // n:02x}{total_b // n:02x}"
