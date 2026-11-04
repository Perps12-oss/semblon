"""Density-aware temporal ribbon for the archive time strip (Phase 2).

The strip is a miniature temporal lens: calendar overview first, then local
hover magnification year → month → day. Visual marks are capped per period so
dense months stay coherent cells — never one mark per photograph.

Acceptance: 10,000 photographs in July and August produce two coherent month
cells under year magnification, not 10,000 competing marks.

Thumbnails and colours come only from existing thumb caches. No new analysis,
indexing, schema columns, or identity work.

``sampleIds`` are keyed by media id (not row index / DB order) and stratified
across finer periods so a single burst day cannot fill every preview slot.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from semblon.native_shell.sections import month_key

# Fixed sample budgets — density cannot inflate the mark count.
YEAR_SAMPLE_BUDGET = 16
MONTH_SAMPLE_BUDGET = 4
DAY_SAMPLE_BUDGET = 2
# Tiny mosaic tiles inside one month/day cell (Phase 2 colour / preview).
CELL_MOSAIC_MAX = 4

IdAt = Callable[[int], str]


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


def _media_rank(media_id: str, salt: str) -> str:
    """Stable order key for a media id within a period — independent of row index."""
    return hashlib.sha1(f"{salt}\0{media_id}".encode("utf-8")).hexdigest()


def _resolve_ids(
    indices: Sequence[int],
    *,
    media_ids: Sequence[str] | None,
    id_at: IdAt | None,
) -> list[str]:
    out: list[str] = []
    for i in indices:
        if media_ids is not None and 0 <= i < len(media_ids):
            mid = str(media_ids[i] or "")
            if mid:
                out.append(mid)
                continue
        if id_at is not None:
            mid = str(id_at(i) or "")
            if mid and not mid.startswith("idx:"):
                out.append(mid)
                continue
        out.append(f"idx:{i}")
    return out


def _stratify_sample(
    strata: Sequence[Sequence[str]],
    budget: int,
    salt: str,
) -> list[str]:
    """Round-robin across strata; within a stratum pick by media-id hash.

    A dense burst that occupies one stratum cannot monopolise every slot while
    other strata still have photographs. Selection is stable for a fixed set of
    media ids regardless of database / row order.
    """
    if budget <= 0 or not strata:
        return []
    ranked: list[list[str]] = []
    for stratum in strata:
        ids = [mid for mid in stratum if mid and not str(mid).startswith("idx:")]
        if not ids:
            # Keep placeholder indices only when nothing else exists in the stratum.
            ids = [mid for mid in stratum if mid]
        if not ids:
            continue
        ranked.append(sorted(set(ids), key=lambda mid: (_media_rank(mid, salt), mid)))
    if not ranked:
        return []
    # Round-robin so each stratum contributes before any gets a second pick.
    picked: list[str] = []
    seen: set[str] = set()
    cursor = [0] * len(ranked)
    while len(picked) < budget:
        progressed = False
        for s, bucket in enumerate(ranked):
            if len(picked) >= budget:
                break
            at = cursor[s]
            if at >= len(bucket):
                continue
            mid = bucket[at]
            cursor[s] = at + 1
            progressed = True
            if mid in seen:
                continue
            seen.add(mid)
            picked.append(mid)
        if not progressed:
            break
    return picked[:budget]


def _stratum_ids(
    idxs: Sequence[int],
    budget: int,
    salt: str,
    *,
    media_ids: Sequence[str] | None,
    id_at: IdAt | None,
) -> list[str]:
    """Resolve stratum media ids for ranking.

    Prefer a full ``media_ids`` vector (stable under reorder and small inserts).
    When only ``id_at`` is available, keep an online top-k by media-id hash while
    scanning — inserting one photograph changes membership by at most one id,
    unlike evenly-spaced index probes.
    """
    if not idxs:
        return []
    if media_ids is not None:
        return _resolve_ids(idxs, media_ids=media_ids, id_at=None)
    if id_at is None:
        return [f"idx:{i}" for i in idxs]
    # Online top-k by media-id rank (k = max(budget*4, budget)).
    # Sorted (rank, mid) list — inserting one id changes membership by ≤1.
    import bisect

    k = max(budget * 4, budget, 1)
    best: list[tuple[str, str]] = []
    for i in idxs:
        mid = str(id_at(i) or "")
        if not mid or mid.startswith("idx:"):
            continue
        item = (_media_rank(mid, salt), mid)
        if len(best) < k:
            bisect.insort(best, item)
        elif item < best[-1]:
            best.pop()
            bisect.insort(best, item)
    return [mid for _rank, mid in best]


def _sample_from_groups(
    groups: dict[str, list[int]],
    group_keys: Sequence[str],
    budget: int,
    salt: str,
    *,
    media_ids: Sequence[str] | None,
    id_at: IdAt | None,
) -> list[str]:
    strata: list[list[str]] = []
    for key in group_keys:
        idxs = groups.get(key) or []
        if not idxs:
            continue
        strata.append(
            _stratum_ids(idxs, budget, salt, media_ids=media_ids, id_at=id_at)
        )
    return _stratify_sample(strata, budget, salt)


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


def year_cells(
    days: Sequence[str],
    *,
    media_ids: Sequence[str] | None = None,
    id_at: IdAt | None = None,
    colors: dict[str, str] | None = None,
    index: dict | None = None,
) -> list[PeriodCell]:
    """One coherent cell per populated calendar year — ``O(years)``, never ``O(photos)``."""
    index = index if index is not None else index_periods(days)
    cells: list[PeriodCell] = []
    for key in sorted(index["years"].keys(), reverse=True):
        idxs = index["years"][key]
        # Stratify by month inside the year so one busy month cannot own every slot.
        month_keys = sorted(
            (mk for mk in index["months"] if mk.startswith(f"{key}-")),
            reverse=True,
        )
        sample = _sample_from_groups(
            index["months"],
            month_keys,
            YEAR_SAMPLE_BUDGET,
            f"year:{key}",
            media_ids=media_ids,
            id_at=id_at,
        )
        cells.append(
            PeriodCell(
                kind="year",
                key=key,
                year=int(key),
                month=None,
                day=None,
                photo_count=len(idxs),
                photo_first=idxs[0],
                sample_ids=tuple(sample),
                color=(colors or {}).get(key),
            )
        )
    if index["undated"]:
        idxs = index["undated"]
        sample = _stratify_sample(
            [
                _stratum_ids(
                    idxs,
                    YEAR_SAMPLE_BUDGET,
                    "undated",
                    media_ids=media_ids,
                    id_at=id_at,
                )
            ],
            YEAR_SAMPLE_BUDGET,
            "undated",
        )
        cells.append(
            PeriodCell(
                kind="undated",
                key="undated",
                year=None,
                month=None,
                day=None,
                photo_count=len(idxs),
                photo_first=idxs[0],
                sample_ids=tuple(sample),
                color=(colors or {}).get("undated"),
            )
        )
    return cells


def month_cells_for_year(
    days: Sequence[str],
    year: int,
    *,
    media_ids: Sequence[str] | None = None,
    id_at: IdAt | None = None,
    colors: dict[str, str] | None = None,
    index: dict | None = None,
) -> list[PeriodCell]:
    """Populated months inside one year — at most 12 cells, never one per photo."""
    index = index if index is not None else index_periods(days)
    prefix = f"{int(year):04d}-"
    cells: list[PeriodCell] = []
    for key in sorted((k for k in index["months"] if k.startswith(prefix)), reverse=True):
        idxs = index["months"][key]
        day_keys = sorted((dk for dk in index["days"] if dk.startswith(key)), reverse=True)
        sample = _sample_from_groups(
            index["days"],
            day_keys,
            MONTH_SAMPLE_BUDGET,
            f"month:{key}",
            media_ids=media_ids,
            id_at=id_at,
        )[:CELL_MOSAIC_MAX]
        cells.append(
            PeriodCell(
                kind="month",
                key=key,
                year=int(year),
                month=int(key[5:7]),
                day=None,
                photo_count=len(idxs),
                photo_first=idxs[0],
                sample_ids=tuple(sample),
                color=(colors or {}).get(key),
            )
        )
    return cells


def day_cells_for_month(
    days: Sequence[str],
    month_key_str: str,
    *,
    media_ids: Sequence[str] | None = None,
    id_at: IdAt | None = None,
    colors: dict[str, str] | None = None,
    index: dict | None = None,
) -> list[PeriodCell]:
    """Populated days inside one month — one cell per day that has photographs."""
    mk = month_key(month_key_str) or str(month_key_str)
    if len(mk) < 7:
        return []
    index = index if index is not None else index_periods(days)
    cells: list[PeriodCell] = []
    for key in sorted((k for k in index["days"] if k.startswith(mk)), reverse=True):
        idxs = index["days"][key]
        parsed = _parse_day(key)
        if parsed is None:
            continue
        year, month, day_n = parsed
        sample = _stratify_sample(
            [
                _stratum_ids(
                    idxs,
                    DAY_SAMPLE_BUDGET,
                    f"day:{key}",
                    media_ids=media_ids,
                    id_at=id_at,
                )
            ],
            DAY_SAMPLE_BUDGET,
            f"day:{key}",
        )[:CELL_MOSAIC_MAX]
        cells.append(
            PeriodCell(
                kind="day",
                key=key,
                year=year,
                month=month,
                day=day_n,
                photo_count=len(idxs),
                photo_first=idxs[0],
                sample_ids=tuple(sample),
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
