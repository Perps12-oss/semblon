"""Which day a picture belongs to: the person's local day, never UTC's, daylight saving included."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo

import pytest

from semblon import clock
from semblon.archive_session import day_key
from semblon.native_shell.model import _when


class UsEastern(tzinfo):
    """US Eastern with its daylight-saving rules (second Sunday of March to first Sunday of November)."""

    def _transitions(self, year):
        march = datetime(year, 3, 8)
        march += timedelta(days=(6 - march.weekday()) % 7)
        nov = datetime(year, 11, 1)
        nov += timedelta(days=(6 - nov.weekday()) % 7)
        return march.replace(hour=2), nov.replace(hour=2)

    def utcoffset(self, dt):
        start, end = self._transitions(dt.year)
        naive = dt.replace(tzinfo=None)
        if start <= naive < end:
            return timedelta(hours=-4)
        return timedelta(hours=-5)

    def dst(self, dt):
        return timedelta(hours=1) if self.utcoffset(dt) == timedelta(hours=-4) else timedelta(0)

    def tzname(self, dt):
        return "EDT" if self.dst(dt) else "EST"

    def fromutc(self, dt):
        start, end = self._transitions(dt.year)
        naive = dt.replace(tzinfo=None)
        start_utc = start + timedelta(hours=5)
        end_utc = end + timedelta(hours=4)
        offset = -4 if start_utc <= naive < end_utc else -5
        return (naive + timedelta(hours=offset)).replace(tzinfo=self)


def _ns(*parts):
    return int(datetime(*parts, tzinfo=timezone.utc).timestamp() * 1e9)


@pytest.fixture
def eastern(monkeypatch):
    monkeypatch.setattr(clock, "LOCAL_ZONE", UsEastern())


def test_late_evening_stays_on_its_own_day(eastern):
    # Sat 8 Feb 2025, 22:30 in New York is already Sunday 03:30 in UTC.
    assert day_key(_ns(2025, 2, 9, 3, 30)) == "2025-02-08"


def test_either_side_of_local_midnight(eastern):
    assert day_key(_ns(2025, 2, 9, 4, 59)) == "2025-02-08"   # 23:59 local
    assert day_key(_ns(2025, 2, 9, 5, 0)) == "2025-02-09"    # 00:00 local
    assert day_key(_ns(2025, 2, 9, 5, 1)) == "2025-02-09"    # 00:01 local


def test_daylight_saving_moves_midnight(eastern):
    # Spring forward, Sun 9 Mar 2025 at 02:00: midnight is 05:00 UTC before it, 04:00 UTC after.
    assert day_key(_ns(2025, 3, 9, 4, 59)) == "2025-03-08"   # 23:59 Sat (still EST)
    assert day_key(_ns(2025, 3, 9, 5, 0)) == "2025-03-09"
    assert day_key(_ns(2025, 3, 10, 3, 59)) == "2025-03-09"  # 23:59 Sun (now EDT)
    assert day_key(_ns(2025, 3, 10, 4, 0)) == "2025-03-10"
    # Fall back, Sun 2 Nov 2025 at 02:00: midnight is 04:00 UTC before it, 05:00 UTC after.
    assert day_key(_ns(2025, 11, 2, 3, 59)) == "2025-11-01"  # 23:59 Sat (still EDT)
    assert day_key(_ns(2025, 11, 2, 4, 0)) == "2025-11-02"
    assert day_key(_ns(2025, 11, 3, 4, 59)) == "2025-11-02"  # 23:59 Sun (now EST)
    assert day_key(_ns(2025, 11, 3, 5, 0)) == "2025-11-03"


def test_the_hover_time_uses_the_same_clock(eastern):
    assert _when(_ns(2025, 2, 9, 3, 30)) == "8 Feb 2025, 22:30"


def test_a_picture_with_no_date_has_no_day():
    assert day_key(None) == "" and day_key(0) == ""


def test_the_machine_zone_is_used_when_none_is_pinned(monkeypatch):
    monkeypatch.setattr(clock, "LOCAL_ZONE", None)
    ns = _ns(2025, 6, 15, 12, 0)
    local = datetime.fromtimestamp(ns / 1e9).strftime("%Y-%m-%d")
    assert day_key(ns) == local


def test_the_command_line_timeline_agrees(eastern):
    from semblon.library_browse import _day_key

    assert _day_key(_ns(2025, 2, 9, 3, 30)) == "2025-02-08"
    assert _day_key(None) == "Unknown day"