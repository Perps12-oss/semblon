"""Visual memory timeline: density, month/range scopes, and shell chrome."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from semblon.native_shell.editorial import (
    calendar_month_cells,
    day_section_short_label,
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
    year_matrix,
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
    assert bridge.libraryWorkspace == "calendar"
    bridge.selectDay("2024-01-10")
    assert bridge.scopeKind == "day"
    assert bridge.scopeLabel == "2024-01-10"
    assert bridge.libraryWorkspace == "calendar"
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
    assert bridge.libraryWorkspace == "calendar"
    assert bridge.calendarMonth == "2024-01"

    bridge.openDay("2024-01-10")
    assert bridge.libraryWorkspace == "grid"
    assert bridge.scopeKind == "day"
    assert bridge.scopeLabel == "2024-01-10"
    assert bridge._model.rowCount() == 2
    bridge.openDay("2024-01-10")
    assert bridge.scopeKind == "day"
    assert bridge.libraryWorkspace == "grid"
    bridge.openDay("2024-01-02")
    assert bridge.scopeLabel == "2024-01-02"
    assert bridge._model.rowCount() == 0
    assert bridge.gridTitle
    bridge.showCalendar()
    assert bridge.libraryWorkspace == "calendar"
    assert bridge.scopeKind == ""
    assert bridge.revealedDay == "2024-01-02"
    assert bridge.calendarMonth == "2024-01"
    assert bridge.timeScopeActive is False

    bridge.openDay("2024-01-10")
    bridge.openFocus("a")
    assert bridge.focusId == "a"
    assert bridge.libraryWorkspace == "grid"
    bridge.openTasks()
    bridge.escape()
    assert bridge.tasksOpen is False
    assert bridge.focusId == "a"
    bridge.escape()
    assert bridge.focusId == ""
    assert bridge.scopeKind == "day"
    assert bridge.libraryWorkspace == "grid"
    bridge.escape()
    assert bridge.libraryWorkspace == "calendar"
    assert bridge.scopeKind == ""
    assert bridge.revealedDay == "2024-01-10"
    assert bridge.calendarMonth == "2024-01"

    folder = next(iter(bridge._scope_ids["folder"]))
    bridge.selectFolder(folder)
    assert bridge.scopeKind == "folder"
    assert bridge.libraryWorkspace == "grid"
    bridge.showCalendar()
    assert bridge.libraryWorkspace == "calendar"
    assert bridge.scopeKind == ""
    bridge.showEverything()
    assert bridge.libraryWorkspace == "grid"
    assert bridge.scopeKind == ""
    assert bridge._model.rowCount() == 4
    bridge.showCalendar()
    assert bridge.libraryWorkspace == "calendar"
    bridge.showUndated()
    assert bridge.libraryWorkspace == "grid"
    assert bridge.scopeLabel == "Unknown day"
    assert bridge._model.rowCount() == 0
    bridge.showCalendar()
    assert bridge.libraryWorkspace == "calendar"
    assert bridge.calendarMonth == "2024-01"

    bridge.selectYear("2024")
    assert bridge.scopeKind == "year"
    assert bridge.libraryWorkspace == "calendar"
    assert bridge.calendarMonth == "2024-06"
    bridge.selectMonth("2024-01")
    assert bridge.calendarMonth == "2024-01"
    assert bridge.libraryWorkspace == "calendar"
    bridge.selectRange("2024-01-10", "2024-06-01")
    assert bridge.calendarMonth == "2024-01"
    assert bridge.libraryWorkspace == "calendar"
    bridge.clearScope()
    assert bridge.calendarMonth == "2024-01"
    assert bridge.timeScopeActive is False

    bridge.revealDay("not-a-date")
    assert bridge.revealedDay == ""
    assert bridge.calendarMonth == "2024-01"
    bridge.revealDay("2024-06-01")
    assert bridge.revealedDay == "2024-06-01"
    assert bridge.calendarMonth == "2024-06"
    assert bridge.scopeKind == ""
    bridge.selectYear("2024")
    bridge.setStickyDay("2024-01-20")
    assert bridge.calendarMonth == "2024-01"
    assert bridge.scopeKind == "year"
    bridge.setCalendarView("days")
    assert bridge.calendarView == "days"
    bridge.setCalendarView("nope")
    assert bridge.calendarView == "days"
    bridge.setArchiveSplit(0.55)
    assert abs(bridge.archiveSplit - 0.55) < 1e-6
    bridge.openFocus("a")
    facts = bridge.focusFileFacts
    assert facts["name"] == "a.jpg"
    assert "2024" in facts["date"]
    assert facts["camera"] == "Not in this file"
    assert facts["location"] == "No location stored"
    bridge.shutdown()


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
    assert len(cell["previewIds"]) == 6
    assert cell["overflow"] == 1276
    assert cell["video"] is False
    assert cell["emphasized"] is False
    assert "1,282" in cell["accessibleName"]
    marked = calendar_month_cells(
        "2024-07",
        day_map,
        video_ids={"p0"},
        emphasis_days={"2024-07-04"},
    )
    picked = {c["day"]: c for c in marked}["2024-07-04"]
    assert picked["video"] is True
    assert picked["emphasized"] is True
    sections = field_sections({"2024-10-15": ["a"]}, ["a"])
    assert sections[0]["shortLabel"] == "Oct 15, 2024"
    assert sections[0]["label"] != sections[0]["shortLabel"]
    assert day_section_short_label("") == "Unknown date"
    matrix = year_matrix("2024", {"2024-07-04": ["p0", "p1"]})
    assert len(matrix) == 12
    july = next(row for row in matrix if row["label"] == "2024-07")
    assert july["count"] == 2
    assert any(dot["heat"] == 2 for dot in july["cells"] if dot["day"] == "2024-07-04")


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


def _ctrl_wheel(window, delta_y: int) -> None:
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication

    local = QPointF(window.width() / 2, window.height() / 2)
    global_pos = QPointF(window.mapToGlobal(QPoint(int(local.x()), int(local.y()))))
    event = QWheelEvent(
        local,
        global_pos,
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ControlModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(window, event)



def test_roll_keyboard_opens_a_photo_and_zooms(tmp_path, monkeypatch):
    """The Roll is keyboard-first: arrows move, Enter opens, Escape returns, Ctrl+wheel zooms."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    store = tmp_path / "s.sqlite"
    _seed_days(
        store,
        tmp_path,
        [("a", 2024, 5, 1), ("b", 2024, 5, 2), ("c", 2024, 6, 3), ("d", 2025, 1, 4)],
    )
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    try:
        for _ in range(30):
            app.processEvents()
        roll = root.findChild(QQuickItem, "roll")
        grid = root.findChild(QQuickItem, "rollGrid")
        assert roll is not None and grid is not None
        assert int(roll.property("count")) == 4
        grid.forceActiveFocus()
        app.processEvents()
        assert grid.hasActiveFocus()
        start = int(roll.property("currentPhoto"))
        QTest.keyClick(root, Qt.Key.Key_Right)
        app.processEvents()
        assert int(roll.property("currentPhoto")) == start + 1

        before = float(roll.property("cellTarget"))
        for _ in range(3):
            _ctrl_wheel(root, 240)
            app.processEvents()
        assert float(roll.property("cellTarget")) > before
        QTest.keyClick(root, Qt.Key.Key_Minus)
        app.processEvents()

        QTest.keyClick(root, Qt.Key.Key_Return)
        for _ in range(10):
            app.processEvents()
        assert bridge.focusId != ""
        QTest.keyClick(root, Qt.Key.Key_Escape)
        for _ in range(10):
            app.processEvents()
        assert bridge.focusId == ""
    finally:
        shutdown_shell(engine)


def test_roll_shows_a_welcome_when_there_are_no_photos(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(tmp_path / "empty.sqlite", app=app)
    root = engine.rootObjects()[0]
    try:
        for _ in range(10):
            app.processEvents()
        assert root.findChild(QObject, "emptyState").property("visible") is True
        assert root.findChild(QObject, "addFolder") is not None
    finally:
        shutdown_shell(engine)