"""One clock for "which day is this picture from".

A picture belongs to the day it was made *where the person is*, so a photo taken at 23:40 on
Saturday evening stays on Saturday and does not slip to Sunday just because that is already Sunday
in UTC. The day comes from the computer's own time zone, daylight saving included.
"""

from __future__ import annotations

from datetime import datetime, tzinfo
from pathlib import Path

# None means the computer's own zone. Tests (and nothing else) set a fixed one.
LOCAL_ZONE: tzinfo | None = None


def local_datetime(mtime_ns: int | None) -> datetime | None:
    """The picture's moment as a wall-clock time in the local zone, or None if it has no date."""
    if not mtime_ns:
        return None
    try:
        seconds = int(mtime_ns) / 1e9
        if LOCAL_ZONE is not None:
            return datetime.fromtimestamp(seconds, LOCAL_ZONE)
        return datetime.fromtimestamp(seconds).astimezone()
    except (OSError, OverflowError, ValueError):
        return None


def local_day(mtime_ns: int | None) -> str:
    """'2025-02-08' in the local zone, or '' when the picture has no date."""
    stamp = local_datetime(mtime_ns)
    return stamp.strftime("%Y-%m-%d") if stamp else ""


_CAPTURE_CACHE: dict[tuple[str, int], tuple[datetime | None, int | None]] = {}
_STILL_SUFFIXES = {".jpg", ".jpeg", ".jpe", ".jfif"}


def capture_moment(path: str | None, mtime_ns: int | None) -> tuple[datetime | None, int | None]:
    """When the picture was taken: (wall-clock time, sortable instant in ns).

    The camera's own date wins when the file carries one (DateTimeOriginal, with its UTC offset when
    the camera wrote it). The wall-clock time the camera showed decides the day, so a photo taken at
    23:40 abroad stays on that evening. Without a camera date, or when the file is gone, the file's
    saved time is used on the computer's own clock. A copied file keeps its camera date, so a copy
    lands next to the original instead of on the day it was copied.
    """
    key = (str(path or ""), int(mtime_ns or 0))
    cached = _CAPTURE_CACHE.get(key)
    if cached is not None:
        return cached
    result = _capture_uncached(path, mtime_ns)
    if len(_CAPTURE_CACHE) > 200_000:
        _CAPTURE_CACHE.clear()
    _CAPTURE_CACHE[key] = result
    return result


def _capture_uncached(path, mtime_ns):
    if path and str(path).lower().endswith(tuple(_STILL_SUFFIXES)):
        try:
            from .memory import read_still_exif

            exif = read_still_exif(Path(path))
        except Exception:
            exif = {}
        wall_text = exif.get("datetime_original_wall")
        if wall_text:
            try:
                wall = datetime.fromisoformat(wall_text)
            except ValueError:
                wall = None
            if wall is not None:
                if exif.get("datetime_original_ns") is not None:
                    return wall, int(exif["datetime_original_ns"])
                zone = LOCAL_ZONE
                stamp = wall.replace(tzinfo=zone) if zone is not None else wall.astimezone()
                return wall, int(stamp.timestamp() * 1_000_000_000)
    stamp = local_datetime(mtime_ns)
    if stamp is None:
        return None, None
    return stamp.replace(tzinfo=None), int(mtime_ns)


def capture_day(path: str | None, mtime_ns: int | None) -> str:
    wall, _ = capture_moment(path, mtime_ns)
    return wall.strftime("%Y-%m-%d") if wall else ""