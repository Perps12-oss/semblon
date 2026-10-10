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
    "Videos stay in the store. Year and folder scopes use the media the library "
    "already groups; videos are not separated from photos."
)
YEAR_NOTE = "Year counts use stored file time. Choosing a year or folder scopes the library to it."


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


def scope_ids(store: Path, kind: str = "all") -> dict[str, dict[str, list[str]]]:
    """Media ids behind each year and folder row, kept out of the QML-facing rows.

    ``kind`` is all, photo or video. Groups left empty by the filter are dropped.
    ``everything`` holds every id of that kind.
    """
    keep = _kind_filter(store, kind)
    years: dict[str, list[str]] = {}
    everything: list[str] = []
    for bucket in timeline_buckets(store):
        label = str(bucket.get("label") or "")
        year = label[:4] if len(label) >= 4 and label[:4].isdigit() else "Unknown"
        ids = [str(i) for i in bucket.get("media_ids") or [] if keep(str(i))]
        if ids:
            years.setdefault(year, []).extend(ids)
            everything.extend(ids)
    folders: dict[str, list[str]] = {}
    for bucket in folder_buckets(store):
        ids = [str(i) for i in bucket.get("media_ids") or [] if keep(str(i))]
        if ids:
            folders[str(bucket.get("label") or "")] = ids
    return {"year": years, "folder": folders, "everything": {"": everything}}


def rows_from_scope(ids: dict[str, list[str]], *, newest_first: bool = False) -> list[dict]:
    labels = sorted(ids, reverse=True) if newest_first else list(ids)
    return [{"label": label, "count": len(ids[label])} for label in labels]


def year_rows(store: Path, kind: str = "all") -> list[dict]:
    return rows_from_scope(scope_ids(store, kind)["year"], newest_first=True)


def folder_rows(store: Path, kind: str = "all") -> list[dict]:
    return rows_from_scope(scope_ids(store, kind)["folder"])


def month_heading(day: str) -> str:
    text = str(day or "").strip()
    if len(text) < 10:
        return ""
    try:
        stamp = datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return stamp.strftime("%B, %Y")
