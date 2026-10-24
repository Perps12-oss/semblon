"""One clock for "which day is this picture from".

A picture belongs to the day it was made *where the person is*, so a photo taken at 23:40 on
Saturday evening stays on Saturday and does not slip to Sunday just because that is already Sunday
in UTC. The day comes from the computer's own time zone, daylight saving included.
"""

from __future__ import annotations

from datetime import datetime, tzinfo

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
