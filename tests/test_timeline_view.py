"""Visual memory timeline: density, month/range scopes, and shell chrome."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from semblon.native_shell.editorial import (
    calendar_month_cells,
    default_calendar_month,
    field_sections,
    format_count,
    format_count_exact,
    month_end_day,
    month_rows,
    range_media_ids,
    scope_ids,
    shift_month,
    sort_ids_newest_first,
    timeline_density,
    year_rows,
)
from semblon.store import connect, init_db


def _ns(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1_000_000_000)


def _seed_days(store, tmp_path, rows: list[tuple[str, int, int, int]]) -> None:
    conn = connect(store)
    try:
        init_db(conn)
        payload = []
        for mid, y, m, d in rows:
            path = tmp_path / f"{mid}.jpg"
            path.write_bytes(b"x")
            payload.append(
                (mid, "folder", str(path), f"h-{mid}", 10, 10, _ns(y, m, d), 1)
            )
        conn.executemany(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            payload,
        )
        conn.commit()
    finally:
        conn.close()


def test_month_and_range_derive_from_day_buckets(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_days(
        store,
        tmp_path,
        [
            ("a", 2024, 1, 10),
            ("b", 2024, 1, 20),
            ("c", 2024, 6, 1),
            ("d", 2025, 3, 15),
        ],
    )
    scopes = scope_ids(store)
    assert set(scopes["month"]) == {"2024-01", "2024-06", "2025-03"}
    assert len(scopes["month"]["2024-01"]) == 2
    months = {row["label"]: row["count"] for row in month_rows(store)}
    assert months["2024-01"] == 2
    density = timeline_density(store)
    years = {row["label"]: row["count"] for row in density}
    assert years["2024"] == 3
    assert years["2025"] == 1
    assert abs(sum(row["share"] for row in density) - 1.0) < 1e-9
    y2024 = next(row for row in density if row["label"] == "2024")
    assert {m["label"] for m in y2024["months"]} == {"2024-06", "2024-01"}
    ids = range_media_ids(scopes["day"], "2024-01-01", "2024-06-30")
    assert set(ids) == {"a", "b", "c"}


def test_bridge_select_month_and_range(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    store = tmp_path / "s.sqlite"
    _seed_days(
        store,
        tmp_path,
        [
            ("a", 2024, 1, 10),
            ("b", 2024, 1, 20),
            ("c", 2024, 6, 1),
            ("d", 2025, 3, 15),
        ],
    )
    app = QApplication.instance() or QApplication([])
    del app
    jobs = Application(store)
    bridge = ShellBridge(ArchiveModel(jobs), jobs)
    assert bridge.timelineLoading is False
    assert len(bridge.timelineDensity) == 2

    bridge.selectMonth("2024-01")
    assert bridge.scopeKind == "month"
    assert bridge.scopeLabel == "2024-01"
    assert bridge.timeScopeActive is True
    assert bridge._model.rowCount() == 2
    assert set(bridge.timelinePreviewIds("2024-01")) <= {"a", "b"}

    bridge.selectRange("2024-01-10", "2024-06-01")
    assert bridge.scopeKind == "range"
    assert bridge.scopeLabel == "2024-01-10:2024-06-01"
    assert bridge._model.rowCount() == 3

    bridge.selectYear("2025")
    assert bridge._model.rowCount() == 1
    bridge.clearScope()
    assert bridge.timeScopeActive is False
    assert bridge._model.rowCount() == 4
    bridge.shutdown()


def _find_visual(item, name: str):
    """Walk QQuickItem.childItems — timeline delegates are visual-only for findChild."""
    if item is None:
        return None
    if item.objectName() == name:
        return item
    for child in item.childItems():
        found = _find_visual(child, name)
        if found is not None:
            return found
    return None


def test_timeline_chrome_object_names(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    store = tmp_path / "s.sqlite"
    _seed_days(store, tmp_path, [("a", 2024, 5, 1), ("b", 2025, 1, 2)])
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    for _ in range(20):
        app.processEvents()
    bridge.showLibrary()
    for _ in range(20):
        app.processEvents()
    assert bridge.timelineDensity
    hero = root.findChild(QQuickItem, "timelineHero")
    assert hero is not None
    assert root.findChild(QObject, "timelineRail") is None
    assert _find_visual(hero, "timelineYear_2024") is not None
    assert _find_visual(hero, "timelineMonth_2024-05") is not None
    assert root.findChild(QObject, "stickyHeader") is not None
    assert root.findChild(QObject, "zeroResultFilter") is not None
    assert root.findChild(QObject, "archiveSidebar") is not None
    assert root.findChild(QObject, "contextSidebarSearch") is not None
    assert root.findChild(QObject, "libraryButton") is not None
    assert root.findChild(QObject, "homeButton") is not None
    assert root.findChild(QObject, "sidebarSectionMedia") is not None
    assert root.findChild(QObject, "sidebarSectionFolders") is not None
    assert root.findChild(QQuickItem, "memoryCalendar") is not None
    header = root.findChild(QQuickItem, "archiveHeaderBand")
    assert header is not None
    viewport = root.findChild(QQuickItem, "fieldViewport")
    assert viewport is not None
    assert viewport.clip() is True
    grid = root.findChild(QQuickItem, "fieldGrid")
    assert grid is not None
    assert grid.clip() is True
    # Field viewport must start below the calendar/timeline band.
    assert viewport.y() >= header.y() + header.height() - 1
    assert root.findChild(QObject, "sidebarYear_2024") is None
    assert root.findChild(QObject, "sidebarDay_2024-05-01") is None
    bridge.selectMonth("2024-05")
    assert bridge.scopeKind == "month"
    assert bridge.calendarMonth == "2024-05"
    assert bridge.fieldSectionsActive is True
    for _ in range(20):
        app.processEvents()
    assert root.findChild(QQuickItem, "fieldSections") is not None
    shutdown_shell(engine)


def test_density_counts_match_year_rows(tmp_path):
    store = tmp_path / "s.sqlite"
    _seed_days(
        store,
        tmp_path,
        [("a", 2017, 8, 1), ("b", 2017, 8, 2), ("c", 2018, 1, 1)],
    )
    years = {row["label"]: row["count"] for row in year_rows(store)}
    dens = {row["label"]: row["count"] for row in timeline_density(store)}
    assert dens == years


def test_calendar_month_cells_monday_first_and_counts():
    day_map = {
        "2024-01-10": ["a", "b"],
        "2024-01-15": ["c"],
        "2023-12-31": ["old"],
    }
    cells = calendar_month_cells("2024-01", day_map)
    assert len(cells) in (35, 42)
    assert cells[0]["day"] == "2024-01-01"  # 2024-01-01 was a Monday
    assert all(cells[i]["day"] for i in range(7))
    by_day = {c["day"]: c for c in cells}
    assert by_day["2024-01-10"]["count"] == 2
    assert by_day["2024-01-10"]["thumbId"] == "a"
    assert by_day["2024-01-10"]["inMonth"] is True
    assert by_day["2024-01-15"]["count"] == 1
    empty = by_day["2024-01-02"]
    assert empty["count"] == 0
    assert empty["thumbId"] == ""
    # Outside-month cells present when grid spills; Feb 2024 starts Thursday.
    feb = {c["day"]: c for c in calendar_month_cells("2024-02", day_map)}
    assert feb["2024-01-31"]["inMonth"] is False
    assert feb["2024-02-01"]["inMonth"] is True
    assert shift_month("2024-01", -1) == "2023-12"
    assert shift_month("2024-01", 1) == "2024-02"
    assert default_calendar_month(day_map) == "2024-01"


def test_bridge_calendar_browse_does_not_change_scope(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    store = tmp_path / "s.sqlite"
    _seed_days(
        store,
        tmp_path,
        [
            ("a", 2024, 1, 10),
            ("b", 2024, 1, 10),
            ("c", 2024, 6, 1),
            ("d", 2025, 3, 15),
        ],
    )
    app = QApplication.instance() or QApplication([])
    del app
    jobs = Application(store)
    bridge = ShellBridge(ArchiveModel(jobs), jobs)

    assert bridge.calendarMonth == "2025-03"
    bridge.selectDay("2024-01-10")
    assert bridge.scopeKind == "day"
    assert bridge.scopeLabel == "2024-01-10"
    assert bridge.calendarMonth == "2024-01"
    assert bridge._model.rowCount() == 2
    assert any(c["day"] == "2024-01-10" and c["count"] == 2 for c in bridge.calendarCells)

    bridge.calendarNextMonth()
    assert bridge.calendarMonth == "2024-02"
    assert bridge.scopeKind == "day"
    assert bridge.scopeLabel == "2024-01-10"
    assert bridge._model.rowCount() == 2

    bridge.calendarPrevMonth()
    assert bridge.calendarMonth == "2024-01"
    assert bridge.scopeKind == "day"

    bridge.selectDay("2024-01-10")
    assert bridge.scopeKind == ""
    assert bridge.timeScopeActive is False
    assert bridge.calendarMonth == "2024-01"

    bridge.selectYear("2024")
    assert bridge.scopeKind == "year"
    assert bridge.calendarMonth == "2024-06"
    bridge.selectMonth("2024-01")
    assert bridge.calendarMonth == "2024-01"
    bridge.selectRange("2024-01-10", "2024-06-01")
    assert bridge.calendarMonth == "2024-01"
    bridge.clearScope()
    assert bridge.calendarMonth == "2024-01"
    assert bridge.timeScopeActive is False
    bridge.shutdown()


def test_calendar_chrome_object_names(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    store = tmp_path / "s.sqlite"
    _seed_days(store, tmp_path, [("a", 2024, 5, 1), ("b", 2024, 5, 1), ("c", 2025, 1, 2)])
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    for _ in range(30):
        app.processEvents()
    bridge.showLibrary()
    for _ in range(20):
        app.processEvents()
    cal = root.findChild(QQuickItem, "memoryCalendar")
    assert cal is not None
    assert root.findChild(QObject, "calendarTitle") is not None
    assert root.findChild(QObject, "calendarPrev") is not None
    assert root.findChild(QObject, "calendarNext") is not None
    assert bridge.calendarMonth == "2025-01"
    bridge.setCalendarMonth("2024-05")
    for _ in range(20):
        app.processEvents()
    assert bridge.calendarMonth == "2024-05"
    assert _find_visual(cal, "calendarDay_2024-05-01") is not None
    bridge.selectDay("2024-05-01")
    assert bridge.scopeKind == "day"
    assert bridge._model.rowCount() == 2
    bridge.clearScope()
    assert bridge.scopeKind == ""
    shutdown_shell(engine)


def test_calendar_large_day_map_cells_are_bounded():
    day_map = {f"2020-06-{d:02d}": [f"m{d}"] for d in range(1, 31)}
    cells = calendar_month_cells("2020-06", day_map)
    assert len(cells) in (35, 42)
    assert sum(c["count"] for c in cells if c["inMonth"]) == 30
    assert all(c["thumbId"] for c in cells if c["inMonth"] and c["count"])


def test_format_count_and_high_volume_day_cell():
    assert format_count(12) == "12"
    assert format_count(1282) == "1.3k"
    assert format_count_exact(1282) == "1,282"
    assert month_end_day("2024-02") == "2024-02-29"
    assert month_end_day("2023-02") == "2023-02-28"
    day_map = {"2024-07-04": [f"p{i}" for i in range(1282)]}
    cells = {c["day"]: c for c in calendar_month_cells("2024-07", day_map)}
    cell = cells["2024-07-04"]
    assert cell["count"] == 1282
    assert cell["countLabel"] == "1.3k"
    assert cell["thumbId"] == "p0"
    assert len(cell["previewIds"]) == 3
    assert "1,282" in cell["accessibleName"]


def test_range_selection_reverse_and_month_not_day(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    store = tmp_path / "s.sqlite"
    _seed_days(
        store,
        tmp_path,
        [
            ("a", 2024, 1, 10),
            ("b", 2024, 3, 15),
            ("c", 2024, 6, 1),
        ],
    )
    app = QApplication.instance() or QApplication([])
    del app
    jobs = Application(store)
    bridge = ShellBridge(ArchiveModel(jobs), jobs)
    bridge.selectRange("2024-06-01", "2024-01-10")
    assert bridge.scopeKind == "range"
    assert bridge.scopeLabel == "2024-01-10:2024-06-01"
    assert bridge._model.rowCount() == 3
    bridge.selectMonth("2024-03")
    assert bridge.scopeKind == "month"
    assert bridge.scopeLabel == "2024-03"
    assert bridge.scopeKind != "day"
    bridge.calendarNextMonth()
    assert bridge.calendarMonth == "2024-04"
    assert bridge.scopeKind == "month"
    assert bridge.scopeLabel == "2024-03"
    bridge.shutdown()


def test_field_sections_group_ordered_ids_by_day():
    day_map = {
        "2024-01-20": ["b"],
        "2024-01-10": ["a", "a2"],
        "2024-06-01": ["c"],
    }
    ordered = sort_ids_newest_first(day_map, ["a", "a2", "b", "c"])
    sections = field_sections(day_map, ordered)
    assert [s["day"] for s in sections] == ["2024-06-01", "2024-01-20", "2024-01-10"]
    assert sections[2]["mediaIds"] == ["a2", "a"] or sections[2]["mediaIds"] == ["a", "a2"]
    assert sections[2]["count"] == 2
    assert "January" in sections[2]["label"]
    assert field_sections(day_map, []) == []


def test_bridge_field_sections_for_month_and_range(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    store = tmp_path / "s.sqlite"
    _seed_days(
        store,
        tmp_path,
        [
            ("a", 2024, 1, 10),
            ("b", 2024, 1, 20),
            ("c", 2024, 6, 1),
            ("d", 2025, 3, 15),
        ],
    )
    app = QApplication.instance() or QApplication([])
    del app
    jobs = Application(store)
    bridge = ShellBridge(ArchiveModel(jobs), jobs)

    assert bridge.fieldSectionsActive is False
    bridge.selectMonth("2024-01")
    assert bridge.fieldSectionsActive is True
    days = [s["day"] for s in bridge.fieldSections]
    assert days == ["2024-01-20", "2024-01-10"]
    assert sum(s["count"] for s in bridge.fieldSections) == 2

    bridge.selectRange("2024-01-10", "2024-06-01")
    assert bridge.fieldSectionsActive is True
    assert [s["day"] for s in bridge.fieldSections] == [
        "2024-06-01",
        "2024-01-20",
        "2024-01-10",
    ]

    bridge.selectDay("2024-01-10")
    assert bridge.fieldSectionsActive is False
    bridge.selectFolder(next(iter(bridge._scope_ids["folder"])))
    assert bridge.fieldSectionsActive is False
    bridge.clearScope()
    assert bridge.fieldSectionsActive is False
    bridge.shutdown()


def test_field_sections_chrome(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    store = tmp_path / "s.sqlite"
    _seed_days(
        store,
        tmp_path,
        [("a", 2024, 5, 1), ("b", 2024, 5, 10), ("c", 2024, 5, 10)],
    )
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    for _ in range(30):
        app.processEvents()
    bridge.showLibrary()
    for _ in range(20):
        app.processEvents()
    bridge.selectMonth("2024-05")
    for _ in range(30):
        app.processEvents()
    assert bridge.fieldSectionsActive is True
    sections = root.findChild(QQuickItem, "fieldSections")
    assert sections is not None
    assert sections.isVisible()
    assert _find_visual(sections, "fieldSection_2024-05-10") is not None
    assert _find_visual(sections, "fieldSection_2024-05-01") is not None
    grid = root.findChild(QQuickItem, "fieldGrid")
    assert grid is not None
    assert grid.isVisible() is False
    bridge.clearScope()
    for _ in range(20):
        app.processEvents()
    assert bridge.fieldSectionsActive is False
    assert grid.isVisible() is True
    shutdown_shell(engine)
