"""Read-only library counts for the Home status bar and the review badge.

People to name are unconfirmed groups: clusters whose faces have not been
given a person. That is the same queue as the sidebar badge. This module
does not write the store.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from semblon.store import connect_readonly


def people_to_name_text(n: int) -> str:
    """One phrase for the review queue — sidebar, button, and status agree."""
    n = int(n or 0)
    if n <= 0:
        return "No people to name"
    if n == 1:
        return "1 person to name"
    return f"{n} people to name"


def review_people_cta(n: int) -> str:
    """Primary Review button label. Same noun as ``people_to_name_text``."""
    n = int(n or 0)
    if n <= 0:
        return "Review people"
    if n == 1:
        return "Review 1 person to name"
    return f"Review {n} people to name"


def library_summary(store: Path) -> dict | None:
    """Files, faces, unconfirmed groups, and the latest run stamp.

    None when the library file is missing or the tables are not there.
    Counts of zero are real and are returned.
    """
    path = Path(store)
    if not path.is_file():
        return None
    conn = connect_readonly(path.resolve())
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        files = int(conn.execute("SELECT COUNT(*) FROM media").fetchone()[0])
        faces = int(conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0])
        named_people = int(
            conn.execute(
                "SELECT COUNT(*) FROM persons WHERE status='active'"
            ).fetchone()[0]
        )
        unnamed = int(
            conn.execute(
                """
                SELECT COUNT(*) FROM clusters c
                WHERE (c.status IS NULL OR c.status NOT IN ('ignored', 'merged'))
                  AND NOT EXISTS (
                    SELECT 1 FROM faces f
                    WHERE f.cluster_id = c.cluster_id
                      AND f.person_id IS NOT NULL
                  )
                """
            ).fetchone()[0]
        )
        row = conn.execute(
            """
            SELECT finished_at, started_at FROM runs
            ORDER BY COALESCE(finished_at, started_at) DESC, run_id DESC
            LIMIT 1
            """
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()
    stamp = None
    if row is not None:
        stamp = row["finished_at"] or row["started_at"]
        if stamp is not None:
            stamp = str(stamp)
    return {
        "files": files,
        "faces": faces,
        "unnamed_groups": unnamed,
        "named_people": named_people,
        "last_scan": stamp,
    }


def relative_time(stamp: str | None, *, now: datetime | None = None) -> str | None:
    """Short relative phrase. None when the stamp is missing or not a time."""
    if not stamp:
        return None
    text = str(stamp).strip()
    if not text:
        return None
    parsed = _parse_stamp(text)
    if parsed is None:
        return None
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    delta = (clock - parsed).total_seconds()
    if delta < 0:
        delta = 0
    if delta < 45:
        return "just now"
    if delta < 3600:
        minutes = max(1, int(round(delta / 60.0)))
        unit = "minute" if minutes == 1 else "minutes"
        return f"{minutes} {unit} ago"
    if delta < 86400:
        hours = max(1, int(round(delta / 3600.0)))
        unit = "hour" if hours == 1 else "hours"
        return f"{hours} {unit} ago"
    if delta < 172800:
        return "yesterday"
    return parsed.astimezone(timezone.utc).strftime("%d %b %Y")


def status_bar_text(summary: dict | None, *, now: datetime | None = None) -> str:
    """``{n} files · {n} faces · {people_to_name_text} · Last scan {relative}``.

    Empty when there is no library to count. Last scan is omitted when the
    stamp cannot be read.
    """
    if not summary:
        return ""
    files = int(summary.get("files") or 0)
    faces = int(summary.get("faces") or 0)
    unnamed = int(summary.get("unnamed_groups") or 0)
    line = f"{files} files · {faces} faces · {people_to_name_text(unnamed)}"
    rel = relative_time(summary.get("last_scan"), now=now)
    if rel:
        line = f"{line} · Last scan {rel}"
    return line


def _parse_stamp(text: str) -> datetime | None:
    candidate = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
