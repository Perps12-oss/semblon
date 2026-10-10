"""Read-only facts for the editorial archive chrome.

Counts, years, and folders come from media rows already in the store.
Nothing here writes identity or invents a relationship.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
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
VIDEO_NOTE = (
    "Videos stay in the store. The time contact sheet lists photos only, "
    "so this does not pretend to filter them in."
)
YEAR_NOTE = "Year counts use stored file time. The contact sheet is not filtered by year."


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


def year_rows(store: Path) -> list[dict]:
    counts: dict[str, int] = {}
    for bucket in timeline_buckets(store):
        label = str(bucket.get("label") or "")
        year = label[:4] if len(label) >= 4 and label[:4].isdigit() else "Unknown"
        counts[year] = counts.get(year, 0) + int(bucket.get("count") or 0)
    return [{"label": year, "count": counts[year]} for year in sorted(counts, reverse=True)]


def folder_rows(store: Path) -> list[dict]:
    rows = []
    for bucket in folder_buckets(store):
        rows.append(
            {
                "label": str(bucket.get("label") or ""),
                "count": int(bucket.get("count") or 0),
            }
        )
    return rows


def scope_ids(store: Path) -> dict[str, dict[str, list[str]]]:
    """Media ids behind each year and folder row, kept out of the QML-facing rows."""
    years: dict[str, list[str]] = {}
    for bucket in timeline_buckets(store):
        label = str(bucket.get("label") or "")
        year = label[:4] if len(label) >= 4 and label[:4].isdigit() else "Unknown"
        years.setdefault(year, []).extend(str(i) for i in bucket.get("media_ids") or [])
    folders = {
        str(bucket.get("label") or ""): [str(i) for i in bucket.get("media_ids") or []]
        for bucket in folder_buckets(store)
    }
    return {"year": years, "folder": folders}


def month_heading(day: str) -> str:
    text = str(day or "").strip()
    if len(text) < 10:
        return ""
    try:
        stamp = datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return stamp.strftime("%B, %Y")
