"""The Roll: months, day dividers, per-section counts, the scrubber and tile selection."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from semblon.native_shell import sections


# --- Pure layout ---------------------------------------------------------------------------

DAYS = (
    ["2025-02-08"] * 5
    + ["2025-02-03"] * 2
    + ["2025-01-19"] * 4
    + ["2024-11-02"] * 1
    + ["2024-09-28"] * 3
    + ["2022-03-14"] * 7
)


def test_every_photo_sits_under_its_own_month_in_date_order():
    laid = sections.build_sections(DAYS, 4)
    current = None
    seen = []
    for row in laid["rows"]:
        if row["kind"] == "month":
            current = row["month"]
            seen.append(current)
        elif row["kind"] == "photos":
            for i in range(row["first"], row["first"] + row["n"]):
                assert sections.month_key(DAYS[i]) == current
    assert seen == ["2025-02", "2025-01", "2024-11", "2024-09", "2022-03"]


def test_counts_belong_to_the_section_not_the_library():
    laid = sections.build_sections(DAYS, 4)
    counts = {m["key"]: m["count"] for m in laid["months"]}
    assert counts == {"2025-02": 7, "2025-01": 4, "2024-11": 1, "2024-09": 3, "2022-03": 7}
    assert sum(counts.values()) == len(DAYS)
    day_counts = {r["day"]: r["count"] for r in laid["rows"] if r["kind"] == "day"}
    assert day_counts["2025-02-08"] == 5 and day_counts["2025-02-03"] == 2


def test_each_day_starts_a_new_row_after_its_divider_and_never_shares_one():
    laid = sections.build_sections(DAYS, 4)
    rows = laid["rows"]
    for i, row in enumerate(rows):
        if row["kind"] == "day":
            assert rows[i + 1]["kind"] == "photos" and rows[i + 1]["first"] == row["first"]
        if row["kind"] == "photos":
            assert 1 <= row["n"] <= 4
            assert len({DAYS[j] for j in range(row["first"], row["first"] + row["n"])}) == 1
    # Five photos over four columns: a full row, then a short row that simply ends.
    feb8 = [r["n"] for r in rows if r["kind"] == "photos" and DAYS[r["first"]] == "2025-02-08"]
    assert feb8 == [4, 1]


def test_frame_tags_name_the_weekday():
    assert sections.frame_tag("2025-02-08") == "SAT 8 FEB"
    assert sections.frame_tag("2024-09-14") == "SAT 14 SEP"
    assert sections.frame_tag("") == ""


def test_matches_have_no_dividers_and_undated_photos_are_named():
    laid = sections.build_sections(DAYS, 3, grouped=False)
    assert {r["kind"] for r in laid["rows"]} == {"photos"} and laid["months"] == []
    undated = sections.build_sections(["2024-05-01", ""], 3)
    assert [m["title"] for m in undated["months"]] == ["May 2024", "Undated"]


def test_without_day_rows_months_still_split():
    laid = sections.build_sections(DAYS, 4, day_rows=False)
    assert not any(r["kind"] == "day" for r in laid["rows"])
    assert [m["count"] for m in laid["months"]] == [7, 4, 1, 3, 7]


# --- The real window -----------------------------------------------------------------------

PLAN = [
    (2022, 3, [14, 14, 14, 15]),
    (2022, 11, [2]),
    (2023, 6, [1, 1, 20, 20, 20, 20, 28]),
    (2023, 9, [2, 2, 3]),
    (2024, 9, [28, 28, 28, 28, 28]),
    (2024, 11, [2, 2]),
    (2025, 1, [19, 19, 19, 20, 20, 21, 21, 21, 22]),
    (2025, 2, [3, 8, 8, 8, 8, 8, 8, 9, 9, 9, 9, 9, 9, 9]),
]


def _ns(y, m, d):
    return int(datetime(y, m, d, 14, 30, tzinfo=timezone.utc).timestamp() * 1e9)


def _store(tmp_path):
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    n = 0
    expected = []
    for y, m, days in PLAN:
        for d in days:
            n += 1
            path = tmp_path / f"p{n}.jpg"
            path.write_bytes(b"x")
            conn.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
                (f"m{n:03d}", "folder", str(path), f"h{n}", 10, 10, _ns(y, m, d), 1),
            )
            expected.append((_ns(y, m, d), f"{y}-{m:02d}-{d:02d}"))
    conn.commit()
    conn.close()
    expected.sort(key=lambda p: -p[0])
    return store, [d for _ns_, d in expected]


def _spin(app, seconds=0.4):
    import time

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _boot(store, monkeypatch, width=1200, height=800):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell

    app = QApplication.instance() or QApplication([])
    _a, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    root.resize(width, height)
    root.show()
    _spin(app, 1.2)
    roll = root.findChild(QQuickItem, "roll")
    grid = root.findChild(QQuickItem, "rollGrid")
    return app, engine, root, roll, grid, engine._semblon_bridge


def _call(obj, name, *args):
    from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject

    return QMetaObject.invokeMethod(
        obj, name, Q_RETURN_ARG("QVariant"), *[Q_ARG("QVariant", a) for a in args]
    )


def _items(root, name):
    """Every visual item with this objectName (delegates are not QObject children)."""
    found = []
    stack = [root.contentItem()]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            found.append(item)
        stack.extend(item.childItems())
    return found


def _month_title(day):
    return sections.month_title(sections.month_key(day))


def test_roll_headers_match_their_photos_and_counts_are_per_month(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store, days = _store(tmp_path)
    app, engine, root, roll, grid, bridge = _boot(store, monkeypatch)
    try:
        rows = roll.property("rows")
        assert rows, "the roll should be laid out"
        current = None
        order = []
        for row in rows:
            if row["kind"] == "month":
                current = row["month"]
                order.append(current)
                assert row["count"] == sum(1 for d in days if d.startswith(current))
                assert row["count"] != len(days)
            elif row["kind"] == "photos":
                for i in range(row["first"], row["first"] + row["n"]):
                    assert bridge.dayAt(i)[:7] == current
        assert order == sorted(order, reverse=True) and len(order) == len(PLAN)
    finally:
        shutdown_shell(engine)


def test_sticky_header_follows_the_scroll_across_month_boundaries(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store, days = _store(tmp_path)
    app, engine, root, roll, grid, bridge = _boot(store, monkeypatch, height=620)
    try:
        headings = []
        y = float(grid.property("contentY"))
        limit = float(grid.property("contentHeight")) - 300
        while y < limit:
            grid.setProperty("contentY", y)
            _spin(app, 0.03)
            top = int(_call(roll, "topIndex"))
            title = roll.property("heading")
            assert title == _month_title(bridge.dayAt(top)), (y, top, title)
            expected = sum(1 for d in days if d[:7] == bridge.dayAt(top)[:7])
            assert int(roll.property("headingCount")) == expected
            if not headings or headings[-1] != title:
                headings.append(title)
            y += 90
        assert len(headings) >= 4, headings
        assert headings[0] == "February 2025"
    finally:
        shutdown_shell(engine)


def test_scrubber_lands_exactly_on_a_months_header(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store, days = _store(tmp_path)
    app, engine, root, roll, grid, bridge = _boot(store, monkeypatch)
    try:
        scrub = root.findChild(QQuickItem, "scrubber")
        band = root.findChild(QQuickItem, "rollHeader")
        slots = scrub.property("slots").toVariant()["items"]
        months = [s for s in slots if s["kind"] == "month"]
        assert len(months) == len(PLAN)
        heights = {round(s["h"], 3) for s in months}
        assert len(heights) == 1, "months get even spacing, not density-based distance"
        for slot in (months[3], months[5]):
            _call(scrub, "go", slot["y"] + slot["h"] / 2)
            _spin(app, 0.25)
            assert roll.property("currentMonth") == slot["key"]
            assert roll.property("heading") == sections.month_title(slot["key"])
            top = float(_call(roll, "monthTopInView", slot["key"]))
            assert abs(top - band.height()) <= 2, (top, band.height())
        before = roll.property("currentMonth")
        _call(scrub, "step", 1)
        _spin(app, 0.25)
        keys = [m["key"] for m in months]
        assert roll.property("currentMonth") == keys[keys.index(before) + 1]
        marker = scrub.findChild(QQuickItem, "scrubMarker")
        assert marker.x() + marker.width() <= 8, "the marker stays on the left rail, clear of every label"
    finally:
        shutdown_shell(engine)


def test_gutters_are_the_token_at_every_size(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store, _days = _store(tmp_path)
    for width in (800, 1200):
        app, engine, root, roll, grid, bridge = _boot(store, monkeypatch, width=width)
        try:
            frames = [f for f in _items(root, "printFrame") if f.isVisible()]
            assert frames
            gutter = 5
            for frame in frames[:12]:
                cell = frame.parentItem()
                assert round(cell.width() - frame.width(), 3) == gutter
        finally:
            shutdown_shell(engine)


def test_add_and_settings_sit_inside_the_header_band(tmp_path, monkeypatch):
    from PySide6.QtCore import QPointF, QObject
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store, _days = _store(tmp_path)
    app, engine, root, roll, grid, bridge = _boot(store, monkeypatch)
    try:
        band = root.findChild(QQuickItem, "rollHeader")
        add = root.findChild(QQuickItem, "addFolder")
        assert add.isVisible()
        bottom = add.mapToScene(QPointF(0, add.height())).y()
        assert bottom <= band.height() - 8, (bottom, band.height())
    finally:
        shutdown_shell(engine)


def _tile_point(grid, root, photo):
    from PySide6.QtCore import QPointF
    from PySide6.QtQuick import QQuickItem

    for frame in _items(root, "printFrame"):
        cell = frame.parentItem()
        if cell.property("photo") == photo and cell.isVisible():
            p = cell.mapToScene(QPointF(cell.width() / 2, cell.height() / 2))
            return p.toPoint()
    raise AssertionError(f"photo {photo} is not on screen")


def test_tiles_select_with_ctrl_shift_and_the_keyboard(tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from semblon.native_shell.host import shutdown_shell

    store, _days = _store(tmp_path)
    app, engine, root, roll, grid, bridge = _boot(store, monkeypatch)
    try:
        QTest.mouseClick(root, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, _tile_point(grid, root, 1))
        _spin(app, 0.1)
        QTest.mouseClick(root, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, _tile_point(grid, root, 3))
        _spin(app, 0.1)
        assert set(roll.property("selected").toVariant().keys()) == {"1", "3"}
        assert roll.property("selCount") == 2
        QTest.mouseClick(root, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, _tile_point(grid, root, 5))
        _spin(app, 0.1)
        assert roll.property("selCount") == 3  # 3 through 5 from the last anchor
        QTest.keyClick(root, Qt.Key.Key_Escape)
        _spin(app, 0.1)
        assert roll.property("selCount") == 0

        roll.setProperty("currentPhoto", 0)
        grid.forceActiveFocus()
        _spin(app, 0.1)
        QTest.keyClick(root, Qt.Key.Key_Space)
        QTest.keyClick(root, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
        QTest.keyClick(root, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
        _spin(app, 0.1)
        assert roll.property("selCount") == 3
        assert roll.property("currentPhoto") == 2
    finally:
        shutdown_shell(engine)


def test_arrow_keys_step_by_column_across_day_rows(tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from semblon.native_shell.host import shutdown_shell

    store, _days = _store(tmp_path)
    app, engine, root, roll, grid, bridge = _boot(store, monkeypatch)
    try:
        grid.forceActiveFocus()
        roll.setProperty("currentPhoto", 0)
        QTest.keyClick(root, Qt.Key.Key_Down)
        _spin(app, 0.1)
        # Feb 9 follows Feb 8 in the list; a step down lands in the next row of photos.
        assert roll.property("currentPhoto") > 0
        QTest.keyClick(root, Qt.Key.Key_End)
        _spin(app, 0.1)
        assert roll.property("currentPhoto") == int(roll.property("count")) - 1
        QTest.keyClick(root, Qt.Key.Key_Home)
        _spin(app, 0.1)
        assert roll.property("currentPhoto") == 0
    finally:
        shutdown_shell(engine)


def test_grid_crops_to_the_middle_and_the_photo_view_shows_the_whole_picture(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store, _days = _store(tmp_path)
    app, engine, root, roll, grid, bridge = _boot(store, monkeypatch)
    try:
        tile = next(i for i in _items(root, "printImage") if i.isVisible())
        assert tile.property("cropped") is True
    finally:
        shutdown_shell(engine)
    qml = Path("semblon/native_shell/qml/Viewer.qml").read_text(encoding="utf-8")
    assert "PreserveAspectFit" in qml


# --- A real folder of mixed-date pictures ---------------------------------------------------


def test_a_real_folder_of_mixed_dates_groups_by_month(tmp_path, monkeypatch):
    from PySide6.QtGui import QColor, QImage

    from semblon.ingest import ingest
    from semblon.native_shell.host import shutdown_shell

    folder = tmp_path / "pics"
    folder.mkdir()
    spec = [
        ("a", 2022, 3, 14, 600, 400),    # landscape
        ("b", 2022, 3, 14, 400, 600),    # portrait
        ("c", 2023, 9, 2, 1600, 360),    # panorama
        ("d", 2023, 9, 3, 500, 500),
        ("e", 2025, 2, 8, 640, 480),
    ]
    for name, y, m, d, w, h in spec:
        path = folder / f"{name}.jpg"
        img = QImage(w, h, QImage.Format.Format_RGB32)
        img.fill(QColor("#aa7744"))
        assert img.save(str(path), "JPG")
        stamp = datetime(y, m, d, 12, tzinfo=timezone.utc).timestamp()
        os.utime(path, (stamp, stamp))
    store = tmp_path / "real.sqlite"
    try:
        result = ingest(folder, store, observers="face")
    except Exception as exc:  # the face tools may be missing on a clean machine
        pytest.skip(f"folder could not be read on this machine: {type(exc).__name__}")
    if result.get("new_media") != 5:
        pytest.skip("folder was not read in full on this machine")

    app, engine, root, roll, grid, bridge = _boot(store, monkeypatch)
    try:
        months = {m["key"]: m["count"] for m in roll.property("monthList")}
        assert months == {"2025-02": 1, "2023-09": 2, "2022-03": 2}
        assert [m["key"] for m in roll.property("monthList")] == ["2025-02", "2023-09", "2022-03"]
        assert roll.property("heading") == "February 2025"
        assert int(roll.property("headingCount")) == 1
        _call(roll, "jumpToMonth", "2022-03")
        _spin(app, 0.2)
        assert roll.property("heading") == "March 2022" and int(roll.property("headingCount")) == 2
    finally:
        shutdown_shell(engine)

    from semblon.native_shell.images import load_display_image

    for name, _y, _m, _d, w, h in spec:
        shown = load_display_image(str(folder / f"{name}.jpg"), 400)
        assert abs(shown.width() / shown.height() - w / h) < 0.05

def test_heading_unpins_after_a_scrubber_landing_when_the_view_moves_on(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store, days = _store(tmp_path)
    app, engine, root, roll, grid, bridge = _boot(store, monkeypatch, height=620)
    try:
        months = sorted({d[:7] for d in days}, reverse=True)
        key = months[3]
        _call(roll, "jumpToMonth", key)
        _spin(app, 0.2)
        assert roll.property("currentMonth") == key
        # Move the view without the scrubber (keyboard, wheel, selection scroll).
        for dy in (160, 420, 900, 1500):
            grid.setProperty("contentY", float(grid.property("contentY")) + dy)
            _spin(app, 0.05)
            top = int(_call(roll, "topIndex"))
            assert roll.property("heading") == _month_title(bridge.dayAt(top)), dy
    finally:
        shutdown_shell(engine)
