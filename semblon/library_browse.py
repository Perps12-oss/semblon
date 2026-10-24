"""Library browse facets — Timeline / Folders / Moments (presentation + read-only queries).

No album schema. No identity writes. Filters Memory Canvas via media_ids.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from semblon.memory import _folder_name, events
from semblon.store import connect

__all__ = [
    "BROWSE_FACETS",
    "ALBUMS_DEFERRED_LINES",
    "timeline_buckets",
    "folder_buckets",
    "moment_buckets",
    "bucket_lines",
    "albums_empty_lines",
]

# Compact chrome keys alongside All / Photos / Videos.
BROWSE_FACETS: tuple[tuple[str, str], ...] = (
    ("timeline", "Timeline"),
    ("folders", "Folders"),
    ("moments", "Moments"),
)

ALBUMS_DEFERRED_LINES = (
    "User Collections / Albums are not stored yet.",
    "",
    "Semblon keeps files where they are. Named Moments (people + time) "
    "are available under Moments. A durable album model needs an explicit "
    "schema contract — deferred on purpose.",
)


def _media_rows(store: Path) -> list[dict]:
    path = Path(store)
    if not path.is_file():
        return []
    con = connect(path)
    try:
        rows = con.execute(
            "SELECT media_id, path, mtime_ns, source_type, width, height "
            "FROM media ORDER BY mtime_ns DESC, path"
        ).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        out.append(
            {
                "media_id": r["media_id"] if hasattr(r, "keys") else r[0],
                "path": r["path"] if hasattr(r, "keys") else r[1],
                "mtime_ns": r["mtime_ns"] if hasattr(r, "keys") else r[2],
                "source_type": r["source_type"] if hasattr(r, "keys") else r[3],
                "width": r["width"] if hasattr(r, "keys") else r[4],
                "height": r["height"] if hasattr(r, "keys") else r[5],
            }
        )
    return out


def _day_key(mtime_ns: int | None) -> str:
    from .clock import local_day

    return local_day(mtime_ns) or "Unknown day"


def timeline_buckets(store: Path) -> list[dict]:
    """Day buckets over all media via mtime_ns (not identity)."""
    by_day: dict[str, list[str]] = defaultdict(list)
    for row in _media_rows(store):
        mid = str(row.get("media_id") or "")
        if not mid:
            continue
        by_day[_day_key(row.get("mtime_ns"))].append(mid)
    buckets = []
    for day in sorted(by_day.keys(), reverse=True):
        ids = by_day[day]
        buckets.append(
            {
                "kind": "timeline",
                "key": day,
                "label": day,
                "count": len(ids),
                "media_ids": ids,
            }
        )
    return buckets


def folder_buckets(store: Path) -> list[dict]:
    """Group by parent folder name; filter Canvas via media_ids."""
    by_folder: dict[str, list[str]] = defaultdict(list)
    for row in _media_rows(store):
        mid = str(row.get("media_id") or "")
        if not mid:
            continue
        folder = _folder_name(str(row.get("path") or "")) or "(root)"
        by_folder[folder].append(mid)
    buckets = []
    for name in sorted(by_folder.keys(), key=lambda s: s.lower()):
        ids = by_folder[name]
        buckets.append(
            {
                "kind": "folder",
                "key": name,
                "label": name,
                "count": len(ids),
                "media_ids": ids,
            }
        )
    return buckets


def moment_buckets(store: Path, *, run_id: str | None = None) -> list[dict]:
    """Named-person event groups (bursts / days / folders) with media_ids."""
    ev = events(Path(store), run_id=run_id)
    buckets: list[dict] = []
    for b in ev.get("bursts") or []:
        mids = list(b.get("media_ids") or [])
        if not mids and isinstance(b.get("media"), int):
            continue
        label = b.get("when") or "Moment"
        folder = b.get("folder")
        if folder:
            label = f"{folder} · {label}"
        buckets.append(
            {
                "kind": "moment",
                "key": f"burst:{b.get('folder')}:{b.get('when')}:{b.get('until')}",
                "label": label,
                "count": len(mids) or int(b.get("media") or 0),
                "media_ids": mids,
                "person_ids": list(b.get("person_ids") or []),
            }
        )
    for d in ev.get("days") or []:
        mids = list(d.get("media_ids") or [])
        buckets.append(
            {
                "kind": "moment",
                "key": f"day:{d.get('day')}",
                "label": f"Day {d.get('day')}",
                "count": len(mids) or int(d.get("media") or 0),
                "media_ids": mids,
                "person_ids": list(d.get("person_ids") or []),
            }
        )
    return buckets


def bucket_lines(buckets: list[dict] | None, *, facet: str) -> list[str]:
    buckets = list(buckets or [])
    title = {
        "timeline": "Timeline",
        "folders": "Folders",
        "moments": "Moments",
    }.get(facet, "Browse")
    if not buckets:
        if facet == "moments":
            return [
                title,
                "",
                "No named Moments yet.",
                "Name people in photos to see day and burst groups here.",
                "",
                *ALBUMS_DEFERRED_LINES,
            ]
        return [title, "", "No media to group yet.", "Add a photo folder to begin."]
    lines = [title, "", f"{len(buckets)} group{'s' if len(buckets) != 1 else ''}.", ""]
    for i, b in enumerate(buckets[:16], start=1):
        lines.append(f"{i}. {b.get('label')} — {b.get('count')} photo(s)")
    if len(buckets) > 16:
        lines.append(f"…and {len(buckets) - 16} more.")
    if facet == "moments":
        lines.extend(["", *ALBUMS_DEFERRED_LINES])
    return lines


def albums_empty_lines() -> list[str]:
    return list(ALBUMS_DEFERRED_LINES)
