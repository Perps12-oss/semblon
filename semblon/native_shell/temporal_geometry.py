"""Chronological geometry for the archive time strip.

Two metric spaces stay separate:

* calendar time — uniform years, including empty ones
* content layout — actual Roll ``contentY`` offsets from row geometry

Translation is only through ``time_for_offset`` and ``offset_for_year``.
They are not inverses. Empty years keep chronological space but have no
navigation destination.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from semblon.native_shell.sections import month_key

UNDATED = "undated"


@dataclass(frozen=True)
class YearExtent:
    """One calendar year on the chronological scale and (if populated) in content."""

    year: int
    populated: bool
    content_start: float
    content_end: float
    photo_first: int | None
    photo_count: int


@dataclass(frozen=True)
class UndatedExtent:
    content_start: float
    content_end: float
    photo_first: int
    photo_count: int


@dataclass(frozen=True)
class TemporalPoint:
    """A point on the chronological axis, or an explicit undated result."""

    kind: Literal["dated", "undated"]
    # Fractional year: 2024.0 = 1 Jan 2024, 2025.0 = 1 Jan 2025.
    # Newer dates have larger values. Newest-first content maps larger contentY
    # toward smaller (older) fractional years within the dated domain.
    year_frac: float | None = None


@dataclass(frozen=True)
class ViewportSegment:
    kind: Literal["empty", "dated", "undated", "mixed"]
    # Older edge of the dated coverage (smaller year_frac).
    time_lo: float | None = None
    # Newer edge of the dated coverage (larger year_frac).
    time_hi: float | None = None
    undated_visible: bool = False


@dataclass(frozen=True)
class TemporalGeometry:
    """Immutable snapshot of dated archive structure vs content offsets."""

    generation: int
    calendar_first: int  # oldest year inclusive
    calendar_last: int  # newest year inclusive
    years: tuple[YearExtent, ...]  # chronological ascending, every year in span
    undated: UndatedExtent | None
    dated_content_start: float
    dated_content_end: float
    total_content_height: float

    @property
    def empty(self) -> bool:
        return self.calendar_first > self.calendar_last and self.undated is None

    def year_extent(self, year: int) -> YearExtent | None:
        if year < self.calendar_first or year > self.calendar_last:
            return None
        return self.years[year - self.calendar_first]

    def detent_years(self) -> tuple[int, ...]:
        """Populated years only, newest first (strip reading order)."""
        return tuple(y.year for y in reversed(self.years) if y.populated)

    def offset_for_year(self, year: int) -> float | None:
        """Content destination for a populated year, else ``None`` (never clamps)."""
        extent = self.year_extent(year)
        if extent is None or not extent.populated:
            return None
        return extent.content_start

    def time_for_offset(self, content_offset: float) -> TemporalPoint:
        """Map a contentY into chronological time or an explicit undated result."""
        populated = [y for y in self.years if y.populated]

        # Terminal undated section — outside the dated temporal domain.
        if self.undated is not None and content_offset >= self.undated.content_start - 1e-9:
            return TemporalPoint(kind="undated")

        if not populated:
            return TemporalPoint(kind="undated")

        if content_offset <= self.dated_content_start:
            return TemporalPoint(kind="dated", year_frac=float(populated[-1].year) + 1.0)

        if content_offset >= self.dated_content_end - 1e-9:
            return TemporalPoint(kind="dated", year_frac=float(populated[0].year))

        # Walk newest → oldest (content order).
        for extent in reversed(populated):
            start, end = extent.content_start, extent.content_end
            span = max(end - start, 1e-9)
            if content_offset < start - 1e-9 or content_offset > end + 1e-9:
                continue
            progress = (content_offset - start) / span
            progress = 0.0 if progress < 0 else (1.0 if progress > 1 else progress)
            # content_start → end of calendar year; content_end → start of year.
            return TemporalPoint(kind="dated", year_frac=float(extent.year) + 1.0 - progress)

        # Shared boundary between adjacent populated blocks in content space.
        for newer, older in zip(reversed(populated[:-1]), list(reversed(populated))[1:]):
            if abs(content_offset - newer.content_end) <= 1e-6 or abs(
                content_offset - older.content_start
            ) <= 1e-6:
                return TemporalPoint(kind="dated", year_frac=float(older.year) + 1.0)

        best = min(
            populated,
            key=lambda y: min(abs(content_offset - y.content_start), abs(content_offset - y.content_end)),
        )
        return TemporalPoint(kind="dated", year_frac=float(best.year) + 0.5)

    def viewport_segment(self, top_y: float, bottom_y: float) -> ViewportSegment:
        """Temporal extent of the visible content band [top_y, bottom_y]."""
        if bottom_y < top_y:
            top_y, bottom_y = bottom_y, top_y
        if self.empty:
            return ViewportSegment(kind="empty")

        samples = [top_y, bottom_y]
        # Midpoints help multi-year viewports report coverage without inventing media.
        if bottom_y - top_y > 1e-6:
            samples.append((top_y + bottom_y) * 0.5)

        dated: list[float] = []
        undated_visible = False
        for y in samples:
            point = self.time_for_offset(y)
            if point.kind == "undated":
                undated_visible = True
            elif point.year_frac is not None:
                dated.append(point.year_frac)

        # Also sample at each populated year's content edges that fall inside the viewport.
        for extent in self.years:
            if not extent.populated:
                continue
            for edge in (extent.content_start, extent.content_end):
                if top_y - 1e-6 <= edge <= bottom_y + 1e-6:
                    point = self.time_for_offset(edge)
                    if point.kind == "dated" and point.year_frac is not None:
                        dated.append(point.year_frac)

        if self.undated is not None:
            u = self.undated
            if not (bottom_y < u.content_start or top_y > u.content_end):
                undated_visible = True

        if dated and undated_visible:
            return ViewportSegment(
                kind="mixed",
                time_lo=min(dated),
                time_hi=max(dated),
                undated_visible=True,
            )
        if dated:
            return ViewportSegment(
                kind="dated",
                time_lo=min(dated),
                time_hi=max(dated),
                undated_visible=False,
            )
        if undated_visible:
            return ViewportSegment(kind="undated", undated_visible=True)
        return ViewportSegment(kind="empty")

    def nearest_detent(self, year_frac: float) -> int | None:
        """Nearest populated year to a chronological position."""
        detents = [y.year for y in self.years if y.populated]
        if not detents:
            return None
        # Compare to year centres (year + 0.5).
        return min(detents, key=lambda y: abs((y + 0.5) - year_frac))

    def year_frac_for_strip_t(self, t: float) -> float | TemporalPoint:
        """Map strip parameter t in [0,1] (0=newest top) to year_frac or undated."""
        t = 0.0 if t < 0 else (1.0 if t > 1 else t)
        undated_share = 0.08 if self.undated is not None else 0.0
        dated_span = 1.0 - undated_share
        if self.calendar_first > self.calendar_last:
            return TemporalPoint(kind="undated") if self.undated else TemporalPoint(kind="undated")
        if undated_share > 0 and t >= dated_span:
            return TemporalPoint(kind="undated")
        years = self.calendar_last - self.calendar_first + 1
        # t=0 → calendar_last+1, t=dated_span → calendar_first
        local = 0.0 if dated_span <= 0 else t / dated_span
        return float(self.calendar_last) + 1.0 - local * years

    def strip_t_for_year_frac(self, year_frac: float) -> float:
        """Map a dated year_frac to strip t in [0, dated_span]."""
        undated_share = 0.08 if self.undated is not None else 0.0
        dated_span = 1.0 - undated_share
        years = max(1, self.calendar_last - self.calendar_first + 1)
        # year_frac calendar_last+1 → 0; calendar_first → dated_span
        top = float(self.calendar_last) + 1.0
        bottom = float(self.calendar_first)
        if top == bottom:
            return 0.0
        local = (top - year_frac) / (top - bottom)
        local = 0.0 if local < 0 else (1.0 if local > 1 else local)
        return local * dated_span

    def strip_t_for_undated(self) -> float:
        return 1.0 - (0.04 if self.undated is not None else 0.0)

    def to_dict(self) -> dict:
        return {
            "generation": self.generation,
            "calendarFirst": self.calendar_first,
            "calendarLast": self.calendar_last,
            "datedContentStart": self.dated_content_start,
            "datedContentEnd": self.dated_content_end,
            "totalContentHeight": self.total_content_height,
            "detents": list(self.detent_years()),
            "years": [
                {
                    "year": y.year,
                    "populated": y.populated,
                    "contentStart": y.content_start,
                    "contentEnd": y.content_end,
                    "photoFirst": y.photo_first,
                    "photoCount": y.photo_count,
                }
                for y in self.years
            ],
            "undated": None
            if self.undated is None
            else {
                "contentStart": self.undated.content_start,
                "contentEnd": self.undated.content_end,
                "photoFirst": self.undated.photo_first,
                "photoCount": self.undated.photo_count,
            },
        }


def row_tops(
    rows: list[dict],
    *,
    cell_w: float,
    month_h: float,
    day_h: float,
) -> list[float]:
    """Cumulative contentY tops matching ``Roll.qml`` rowTop arithmetic."""
    tops = [0.0]
    y = 0.0
    for row in rows:
        kind = row.get("kind")
        if kind == "photos":
            y += float(cell_w)
        elif kind == "month":
            y += float(month_h)
        else:
            y += float(day_h)
        tops.append(y)
    return tops


def _year_of_month_key(key: str) -> int | None:
    if len(key) >= 4 and key[:4].isdigit():
        return int(key[:4])
    return None


def build_temporal_geometry(
    days: list[str],
    rows: list[dict],
    *,
    cell_w: float,
    month_h: float = 36.0,
    day_h: float = 34.0,
    generation: int = 0,
) -> TemporalGeometry:
    """Build an immutable geometry snapshot from Roll layout inputs."""
    tops = row_tops(rows, cell_w=cell_w, month_h=month_h, day_h=day_h)
    total_h = tops[-1] if tops else 0.0

    # Collect populated years and undated from month rows.
    month_rows = [(i, r) for i, r in enumerate(rows) if r.get("kind") == "month"]
    populated: dict[int, dict] = {}
    undated_meta: dict | None = None
    for idx, row in month_rows:
        key = str(row.get("month") or "")
        y0 = tops[idx]
        # Content runs until the next month row (or end).
        end_idx = len(rows)
        for j in range(idx + 1, len(rows)):
            if rows[j].get("kind") == "month":
                end_idx = j
                break
        y1 = tops[end_idx]
        first = int(row.get("first") or 0)
        count = int(row.get("count") or 0)
        year = _year_of_month_key(key)
        if year is None:
            if undated_meta is None:
                undated_meta = {
                    "content_start": y0,
                    "content_end": y1,
                    "photo_first": first,
                    "photo_count": count,
                }
            else:
                undated_meta["content_end"] = y1
                undated_meta["photo_count"] += count
            continue
        if year not in populated:
            populated[year] = {
                "content_start": y0,
                "content_end": y1,
                "photo_first": first,
                "photo_count": count,
            }
        else:
            populated[year]["content_end"] = y1
            populated[year]["photo_count"] += count

    # Also derive years from day keys when layout has no month rows (search mode).
    if not populated and not undated_meta:
        for i, day in enumerate(days):
            key = month_key(day)
            year = _year_of_month_key(key)
            if year is None:
                continue
            # Without section headers, approximate equal photo height.
            # Prefer calling with grouped layout in production.
            y0 = (tops[0] if tops else 0.0) + (total_h * i / max(len(days), 1))
            y1 = (tops[0] if tops else 0.0) + (total_h * (i + 1) / max(len(days), 1))
            if year not in populated:
                populated[year] = {
                    "content_start": y0,
                    "content_end": y1,
                    "photo_first": i,
                    "photo_count": 1,
                }
            else:
                populated[year]["content_end"] = y1
                populated[year]["photo_count"] += 1

    if not populated and undated_meta is None:
        return TemporalGeometry(
            generation=generation,
            calendar_first=1,
            calendar_last=0,
            years=(),
            undated=None,
            dated_content_start=0.0,
            dated_content_end=0.0,
            total_content_height=total_h,
        )

    if populated:
        first_year = min(populated)
        last_year = max(populated)
    else:
        first_year, last_year = 1, 0

    years: list[YearExtent] = []
    for year in range(first_year, last_year + 1):
        meta = populated.get(year)
        if meta is None:
            years.append(
                YearExtent(
                    year=year,
                    populated=False,
                    content_start=0.0,
                    content_end=0.0,
                    photo_first=None,
                    photo_count=0,
                )
            )
        else:
            years.append(
                YearExtent(
                    year=year,
                    populated=True,
                    content_start=float(meta["content_start"]),
                    content_end=float(meta["content_end"]),
                    photo_first=int(meta["photo_first"]),
                    photo_count=int(meta["photo_count"]),
                )
            )

    undated = None
    if undated_meta is not None:
        undated = UndatedExtent(
            content_start=float(undated_meta["content_start"]),
            content_end=float(undated_meta["content_end"]),
            photo_first=int(undated_meta["photo_first"]),
            photo_count=int(undated_meta["photo_count"]),
        )

    dated_start = min((y.content_start for y in years if y.populated), default=0.0)
    dated_end = max((y.content_end for y in years if y.populated), default=0.0)

    return TemporalGeometry(
        generation=generation,
        calendar_first=first_year,
        calendar_last=last_year,
        years=tuple(years),
        undated=undated,
        dated_content_start=dated_start,
        dated_content_end=dated_end,
        total_content_height=total_h,
    )


def time_for_offset(geometry: TemporalGeometry, content_offset: float) -> TemporalPoint:
    return geometry.time_for_offset(content_offset)


def offset_for_year(geometry: TemporalGeometry, year: int) -> float | None:
    return geometry.offset_for_year(year)
