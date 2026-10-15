"""Read-only facts for the editorial archive chrome.

Counts, years, and folders come from media rows already in the store.
Nothing here writes identity or invents a relationship.
"""

from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime
from pathlib import Path

from semblon.library_browse import ALBUMS_DEFERRED_LINES, folder_buckets, timeline_buckets
from semblon.store import connect

SAVED_VIEWS_NOTE = ALBUMS_DEFERRED_LINES[0] if ALBUMS_DEFERRED_LINES else "Saved views are not stored yet."
SPATIAL_NOTE = (
    "Spatial relationships are not available. "
    "No relationship index is connected, so this view draws no thumbnails and no lines. "
    "Nearness would not be evidence."
)
SIMILAR_NOTE = (
    "Similar is not a collection. "
    "Nothing was searched. Open a photo and draw a region in Focus to look for similar images."
)
# Playback is deferred. Tiles are labeled and Focus stays on stills so video
# frames stay out of DBSCAN. Remaining work: a viewer for the URL focusUrl
# already builds, without changing archive_session.open_focus or cluster eligibility.
VIDEO_NOTE = (
    "Videos stay in the library and can be shown on their own. "
    "A video is labeled Video and does not open. Playback is not available."
)
YEAR_NOTE = "Year counts use stored file time. Choosing a year or folder scopes the library to it."


def format_count(n: int | float | None) -> str:
    """Compact display count (``1.3k``). Exact value stays in ``exactCount`` / a11y."""
    try:
        value = int(n or 0)
    except (TypeError, ValueError):
        value = 0
    if value < 0:
        value = 0
    if value < 1000:
        return str(value)
    if value < 10_000:
        tenths = value / 1000
        text = f"{tenths:.1f}k"
        return text.replace(".0k", "k")
    return f"{value // 1000}k"


def format_count_exact(n: int | float | None) -> str:
    """Exact count with thousands separators for tooltips / accessible names."""
    try:
        value = int(n or 0)
    except (TypeError, ValueError):
        value = 0
    return f"{value:,}"


def month_end_day(month_label: str) -> str:
    """Last calendar day of ``YYYY-MM`` as ``YYYY-MM-DD``."""
    parsed = _parse_month(month_label)
    if parsed is None:
        return ""
    year, month = parsed
    last = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-{last:02d}"


def source_counts(store: Path) -> dict[str, int]:
    path = Path(store)
    if not path.is_file():
        return {}
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT source_type, COUNT(*) FROM media GROUP BY source_type"
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
    counts: dict[str, int] = {}
    for row in rows:
        kind = str(row[0] or "")
        counts[kind] = int(row[1] or 0)
    return counts


MEDIA_KINDS = ("all", "photo", "video")


def video_ids(store: Path) -> set[str]:
    path = Path(store)
    if not path.is_file():
        return set()
    conn = connect(path)
    try:
        rows = conn.execute("SELECT media_id FROM media WHERE source_type = 'video'").fetchall()
    except sqlite3.Error:
        return set()
    finally:
        conn.close()
    return {str(row[0]) for row in rows}


def _kind_filter(store: Path, kind: str):
    """Return a predicate keeping ids of one kind; photos are everything that is not a video."""
    if kind not in ("photo", "video"):
        return lambda _mid: True
    videos = video_ids(store)
    if kind == "video":
        return lambda mid: mid in videos
    return lambda mid: mid not in videos


def _month_key(day_label: str) -> str:
    text = str(day_label or "").strip()
    if len(text) >= 7 and text[4:5] == "-" and text[:4].isdigit():
        return text[:7]
    return ""


def scope_ids(store: Path, kind: str = "all") -> dict[str, dict[str, list[str]]]:
    """Media ids behind each year, month, day, and folder row.

    ``kind`` is all, photo or video. Groups left empty by the filter are dropped.
    ``everything`` holds every id of that kind. Months are unions of day buckets —
    never fabricated empty calendar months. ``range`` is filled on demand by the bridge.
    """
    keep = _kind_filter(store, kind)
    years: dict[str, list[str]] = {}
    months: dict[str, list[str]] = {}
    days: dict[str, list[str]] = {}
    everything: list[str] = []
    for bucket in timeline_buckets(store):
        label = str(bucket.get("label") or "")
        year = label[:4] if len(label) >= 4 and label[:4].isdigit() else "Unknown"
        ids = [str(i) for i in bucket.get("media_ids") or [] if keep(str(i))]
        if ids:
            years.setdefault(year, []).extend(ids)
            days[label] = ids
            month = _month_key(label)
            if month:
                months.setdefault(month, []).extend(ids)
            everything.extend(ids)
    folders: dict[str, list[str]] = {}
    for bucket in folder_buckets(store):
        ids = [str(i) for i in bucket.get("media_ids") or [] if keep(str(i))]
        if ids:
            folders[str(bucket.get("label") or "")] = ids
    return {
        "year": years,
        "month": months,
        "day": days,
        "folder": folders,
        "range": {},
        "everything": {"": everything},
    }


def rows_from_scope(ids: dict[str, list[str]], *, newest_first: bool = False) -> list[dict]:
    labels = sorted(ids, reverse=True) if newest_first else list(ids)
    rows: list[dict] = []
    for label in labels:
        count = len(ids[label])
        rows.append(
            {
                "label": label,
                "displayName": label,
                "count": count,
                "countLabel": format_count(count),
                "exactCount": count,
                "countNoun": "photos",
                "accessibleName": f"{label}, {format_count_exact(count)} photos",
            }
        )
    return rows


def year_rows(store: Path, kind: str = "all") -> list[dict]:
    return rows_from_scope(scope_ids(store, kind)["year"], newest_first=True)


def month_rows(store: Path, kind: str = "all") -> list[dict]:
    return rows_from_scope(scope_ids(store, kind)["month"], newest_first=True)


def day_rows(store: Path, kind: str = "all") -> list[dict]:
    return rows_from_scope(scope_ids(store, kind)["day"], newest_first=True)


def folder_rows(store: Path, kind: str = "all") -> list[dict]:
    return rows_from_scope(scope_ids(store, kind)["folder"])


def range_media_ids(day_map: dict[str, list[str]], start: str, end: str) -> list[str]:
    """Inclusive union of day buckets between two ``YYYY-MM-DD`` keys."""
    a = str(start or "").strip()[:10]
    b = str(end or "").strip()[:10]
    if len(a) < 10 or len(b) < 10:
        return []
    if a > b:
        a, b = b, a
    out: list[str] = []
    for day, ids in day_map.items():
        key = str(day)[:10]
        if len(key) >= 10 and a <= key <= b:
            out.extend(ids)
    return out


def sort_ids_newest_first(day_map: dict[str, list[str]], media_ids: list[str]) -> list[str]:
    """Order ids by day key descending, stable within a day."""
    day_of: dict[str, str] = {}
    for day, ids in day_map.items():
        for mid in ids:
            day_of[str(mid)] = str(day)
    return sorted(
        [str(m) for m in media_ids],
        key=lambda mid: (day_of.get(mid, ""), mid),
        reverse=True,
    )


def timeline_density(store: Path, kind: str = "all") -> list[dict]:
    """Year → month density rows for the hero strip. Shares sum to 1.0 across years."""
    scopes = scope_ids(store, kind)
    years = scopes["year"]
    months = scopes["month"]
    total = sum(len(v) for v in years.values()) or 1
    rows: list[dict] = []
    for year in sorted(years, reverse=True):
        y_ids = years[year]
        y_count = len(y_ids)
        year_months = {
            m: months[m]
            for m in sorted(months, reverse=True)
            if m.startswith(f"{year}-")
        }
        m_total = sum(len(v) for v in year_months.values()) or 1
        month_rows_out = []
        for month, m_ids in year_months.items():
            m_count = len(m_ids)
            month_rows_out.append(
                {
                    "label": month,
                    "count": m_count,
                    "share": m_count / m_total,
                    "accessibleName": f"{month_heading(month + '-01') or month}, {m_count} photos",
                    "previewIds": list(m_ids[:3]),
                }
            )
        rows.append(
            {
                "label": year,
                "count": y_count,
                "share": y_count / total,
                "accessibleName": f"Year {year}, {y_count} photos",
                "previewIds": list(y_ids[:3]),
                "months": month_rows_out,
            }
        )
    return rows


def month_heading(day: str) -> str:
    text = str(day or "").strip()
    if len(text) >= 7 and text[4:5] == "-" and len(text) < 10:
        text = text[:7] + "-01"
    if len(text) < 10:
        return ""
    try:
        stamp = datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return stamp.strftime("%B, %Y")


def day_section_label(day: str) -> str:
    """Human day heading for Field sections (e.g. ``Wednesday 10 January 2024``)."""
    text = str(day or "").strip()[:10]
    if len(text) < 10:
        return text or "Unknown date"
    try:
        stamp = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return text
    return f"{stamp.strftime('%A')} {stamp.day} {stamp.strftime('%B %Y')}"


def field_sections(day_map: dict[str, list[str]], media_ids: list[str]) -> list[dict]:
    """Group already-ordered media ids into day sections (order preserved).

    Used for year / month / range Field browsing. Empty ``media_ids`` → [].
    Ids with no day bucket land in a trailing ``unknown`` section.
    """
    day_of: dict[str, str] = {}
    for day, ids in day_map.items():
        key = str(day)[:10]
        for mid in ids:
            day_of[str(mid)] = key
    order: list[str] = []
    buckets: dict[str, list[str]] = {}
    for mid in media_ids:
        media_id = str(mid)
        day = day_of.get(media_id) or "unknown"
        if day not in buckets:
            buckets[day] = []
            order.append(day)
        buckets[day].append(media_id)
    out: list[dict] = []
    for day in order:
        ids = buckets[day]
        out.append(
            {
                "day": day,
                "label": day_section_label(day) if day != "unknown" else "Unknown date",
                "count": len(ids),
                "mediaIds": ids,
            }
        )
    return out


def _parse_month(label: str) -> tuple[int, int] | None:
    text = str(label or "").strip()[:7]
    if len(text) < 7 or text[4:5] != "-":
        return None
    try:
        year = int(text[:4])
        month = int(text[5:7])
    except ValueError:
        return None
    if month < 1 or month > 12:
        return None
    return year, month


def shift_month(label: str, delta: int) -> str:
    """Move ``YYYY-MM`` by ``delta`` months."""
    parsed = _parse_month(label)
    if parsed is None:
        today = date.today()
        year, month = today.year, today.month
    else:
        year, month = parsed
    month += int(delta)
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}"


def default_calendar_month(day_map: dict[str, list[str]]) -> str:
    """Newest day with media, else the current local month."""
    dated = [str(k)[:10] for k in day_map if len(str(k)) >= 10 and str(k)[4:5] == "-"]
    if dated:
        newest = max(dated)
        return newest[:7]
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}"


def calendar_month_cells(
    month_label: str, day_map: dict[str, list[str]]
) -> list[dict]:
    """Monday-first month grid cells (usually 35 or 42) from real day buckets.

    Empty calendar days are present with count 0 and no fabricated thumb.
    Days outside the displayed month are marked ``inMonth=False``.
    """
    parsed = _parse_month(month_label)
    if parsed is None:
        return []
    year, month = parsed
    today = date.today().isoformat()
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    cells: list[dict] = []
    for day in cal.itermonthdates(year, month):
        key = day.isoformat()
        ids = [str(i) for i in day_map.get(key, [])]
        count = len(ids)
        cells.append(
            {
                "day": key,
                "dayNum": day.day,
                "inMonth": day.month == month,
                "count": count,
                "countLabel": format_count(count),
                "exactCount": count,
                "isToday": key == today,
                "thumbId": ids[0] if ids else "",
                "previewIds": ids[:3],
                "accessibleName": (
                    f"{day.strftime('%A')} {day.day} {day.strftime('%B %Y')}, "
                    f"{format_count_exact(count)} photos"
                    if ids
                    else f"{day.strftime('%A')} {day.day} {day.strftime('%B %Y')}, empty"
                ),
            }
        )
    return cells
