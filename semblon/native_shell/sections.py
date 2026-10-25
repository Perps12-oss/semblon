"""Lay the Roll out as sections: a month, then its days, then rows of pictures.

The archive is one list of pictures, newest first. A person reads it as months and
days, so each month and each day starts on a fresh row under its own divider, and
every count is that section's own count (never the whole library).
"""

from __future__ import annotations

from datetime import date

MONTHS = (
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)
_ABBR = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_WEEK = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def month_key(day: str) -> str:
    text = str(day or "")
    if len(text) >= 7 and text[4] == "-" and text[:4].isdigit() and text[5:7].isdigit():
        if 1 <= int(text[5:7]) <= 12:
            return text[:7]
    return ""


def month_title(key: str) -> str:
    if not key:
        return "Undated"
    return f"{MONTHS[int(key[5:7]) - 1]} {key[:4]}"


def frame_tag(day: str) -> str:
    """Contact-sheet frame label, e.g. ``SAT 8 FEB``."""
    try:
        d = date(int(day[:4]), int(day[5:7]), int(day[8:10]))
    except (ValueError, IndexError):
        return ""
    return f"{_WEEK[d.weekday()]} {d.day} {_ABBR[d.month - 1]}"


def build_sections(days: list[str], columns: int, *, grouped: bool = True, day_rows: bool = True) -> dict:
    """Rows for the Roll plus a summary per month.

    ``days`` is each picture's day key in display order. When ``grouped`` is off (search
    matches) the pictures simply fill rows with no dividers.
    """
    columns = max(1, int(columns))
    rows: list[dict] = []
    months: list[dict] = []

    def photo_rows(first: int, count: int, key: str) -> None:
        at = first
        while at < first + count:
            n = min(columns, first + count - at)
            rows.append({"kind": "photos", "first": at, "n": n, "month": key})
            at += n

    total = len(days)
    if not grouped:
        photo_rows(0, total, "")
        return {"rows": rows, "months": months}

    i = 0
    while i < total:
        key = month_key(days[i])
        j = i
        while j < total and month_key(days[j]) == key:
            j += 1
        month = {"key": key, "title": month_title(key), "count": j - i, "first": i, "row": len(rows)}
        months.append(month)
        rows.append({"kind": "month", "first": i, "month": key, "title": month["title"], "count": j - i})
        if day_rows:
            k = i
            while k < j:
                day = days[k]
                m = k
                while m < j and days[m] == day:
                    m += 1
                tag = frame_tag(day)
                if tag:
                    rows.append({"kind": "day", "first": k, "month": key, "day": day, "tag": tag, "count": m - k})
                photo_rows(k, m - k, key)
                k = m
        else:
            photo_rows(i, j - i, key)
        i = j
    return {"rows": rows, "months": months}
