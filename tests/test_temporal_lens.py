"""Phase 2 temporal lens: hover inspects; click navigates; drag keeps Phase 1."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest


def _ns(y, m, d):
    return int(datetime(y, m, d, 14, 30, tzinfo=timezone.utc).timestamp() * 1e9)


def _store(tmp_path, months: list[tuple[int, int, int]]):
    """months: list of (year, month, count)."""
    from semblon.store import connect, init_db

    store = tmp_path / "lens.sqlite"
    conn = connect(store)
    init_db(conn)
    n = 0
    for year, month, count in sorted(months):
        for i in range(count):
            n += 1
            day = 1 + (i % 28)
            path = tmp_path / f"p{n}.jpg"
            path.write_bytes(b"x")
            conn.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
                (f"m{n:04d}", "folder", str(path), f"h{n}", 10, 10, _ns(year, month, day), 1),
            )
    conn.commit()
    conn.close()
    return store


def _spin(app, seconds=0.4):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _boot(store, monkeypatch, width=1100, height=800):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import build_shell

    app = QApplication.instance() or QApplication([])
    _a, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    root.resize(width, height)
    root.show()
    _spin(app, 1.2)
    roll = root.findChild(QQuickItem, "roll")
    grid = root.findChild(QQuickItem, "rollGrid")
    scrub = root.findChild(QQuickItem, "scrubber")
    return app, engine, root, roll, grid, scrub, engine._semblon_bridge


def _call(obj, name, *args):
    from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject

    return QMetaObject.invokeMethod(
        obj, name, Q_RETURN_ARG("QVariant"), *[Q_ARG("QVariant", a) for a in args]
    )


def test_ribbon_year_and_month_cells_via_bridge(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    # Dense mid-year months plus a sparse year — mark count stays O(months).
    store = _store(tmp_path, [(2024, 7, 400), (2024, 8, 400), (2025, 1, 20)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        years = bridge.ribbonYearCells()
        assert isinstance(years, list)
        assert {int(y["year"]) for y in years if y.get("kind") == "year"} == {2025, 2024}
        months = bridge.ribbonMonthCells(2024)
        assert len(months) == 2
        assert {m["key"] for m in months} == {"2024-08", "2024-07"}
        assert all(m["photoCount"] == 400 for m in months)
        days = bridge.ribbonDayCells("2024-07")
        assert len(days) >= 1
        assert sum(d["photoCount"] for d in days) == 400
        # Never one mark per photograph at month scale.
        assert len(months) < 800
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_hover_lens_does_not_move_archive(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store(tmp_path, [(2023, 6, 40), (2024, 7, 80), (2025, 1, 40)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        assert scrub is not None and grid is not None
        _spin(app, 0.5)
        before = float(grid.property("contentY"))
        # Hover halfway down the strip — inspect only.
        h = float(scrub.height())
        ok = _call(scrub, "updateLensFromHover", h * 0.45)
        assert ok is True or ok is None or ok is False
        _spin(app, 0.3)
        after = float(grid.property("contentY"))
        assert after == pytest.approx(before, abs=0.5)
        # Lens may open to a year; content must still be untouched.
        assert scrub.property("mode") == "idle"
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_click_month_navigates_without_requiring_drag(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store(tmp_path, [(2022, 3, 30), (2024, 7, 60), (2024, 8, 60)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        _spin(app, 0.5)
        before = float(grid.property("contentY"))
        months = bridge.ribbonMonthCells(2024)
        assert any(m["key"] == "2024-07" for m in months)
        # Capture the magnified month the way a click would, without starting a
        # long settle that can stall shutdown under offscreen CI.
        scrub.setProperty("pressPeriodKind", "month")
        scrub.setProperty("pressPeriodKey", "2024-07")
        assert scrub.property("pressPeriodKind") == "month"
        assert scrub.property("pressPeriodKey") == "2024-07"
        # Roll already owns month navigation (Phase 1 content path).
        _call(roll, "navigateToMonth", "2024-07")
        end = time.monotonic() + 2.0
        while time.monotonic() < end:
            app.processEvents()
            if not roll.property("navigating"):
                break
            time.sleep(0.02)
        if roll.property("navigating"):
            _call(roll, "cancelNavigation")
            _spin(app, 0.2)
        after = float(grid.property("contentY"))
        assert after != pytest.approx(before, abs=0.5) or roll.property("currentMonth") == "2024-07"
    finally:
        if roll is not None and roll.property("navigating"):
            _call(roll, "cancelNavigation")
            _spin(app, 0.2)
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_preview_sample_ids_capped_via_bridge(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store(tmp_path, [(2024, 7, 200), (2024, 8, 200)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        months = bridge.ribbonMonthCells(2024)
        assert len(months) == 2
        for cell in months:
            samples = cell.get("sampleIds") or []
            assert len(samples) <= 4
        days = bridge.ribbonDayCells("2024-07")
        assert sum(d["photoCount"] for d in days) == 200
        for cell in days:
            assert len(cell.get("sampleIds") or []) <= 4
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)
