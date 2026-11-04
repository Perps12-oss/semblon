"""Navigation spike + temporal strip interaction on the production Roll."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from semblon.native_shell import sections


def _ns(y, m, d):
    return int(datetime(y, m, d, 14, 30, tzinfo=timezone.utc).timestamp() * 1e9)


def _store_years(tmp_path, year_counts: list[tuple[int, int]], undated: int = 0):
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    n = 0
    # Insert older years first so newest-first timeline still orders correctly by sort_ns.
    for year, count in sorted(year_counts):
        for i in range(count):
            n += 1
            month = 1 + (i % 12)
            day = 1 + (i % 28)
            path = tmp_path / f"p{n}.jpg"
            path.write_bytes(b"x")
            conn.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
                (f"m{n:04d}", "folder", str(path), f"h{n}", 10, 10, _ns(year, month, day), 1),
            )
    for i in range(undated):
        n += 1
        path = tmp_path / f"u{n}.jpg"
        path.write_bytes(b"x")
        # taken_ns=0 → undated in browse path
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (f"u{n:04d}", "folder", str(path), f"u{n}", 10, 10, 0, 1),
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


def _wait_nav(app, roll, seconds=2.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        if not roll.property("navigating"):
            return True
        time.sleep(0.02)
    return not roll.property("navigating")


def test_navigation_spike_distant_redirect_cancel(tmp_path, monkeypatch):
    """Mandatory spike: content-owned navigate / redirect / cancel with real contentY."""
    from semblon.native_shell.host import shutdown_shell

    # ~8k photos in one dense year plus distant years.
    store = _store_years(tmp_path, [(2018, 40), (2022, 8000), (2025, 40)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        assert int(roll.property("photoCount")) >= 8000
        geom = bridge.temporalNavGeometry(
            int(roll.property("columns")),
            True,
            True,
            float(roll.property("cellW")),
            float(roll.property("monthH")),
            float(roll.property("dayH")),
        )
        off_2018 = None
        off_2025 = None
        for y in geom["years"]:
            if y["year"] == 2018 and y["populated"]:
                off_2018 = y["contentStart"]
            if y["year"] == 2025 and y["populated"]:
                off_2025 = y["contentStart"]
        assert off_2018 is not None and off_2025 is not None

        # contentStart is absolute rowTop; Roll subtracts the sticky band when landing months,
        # so strip navigation targets the same placeRow convention.
        band = float(roll.property("headerHeight") or 0)
        target_2018 = max(0.0, float(off_2018) - band)
        target_2025 = max(0.0, float(off_2025) - band)

        start_y = float(grid.property("contentY"))
        _call(roll, "navigateToOffset", target_2018, "")
        _spin(app, 0.15)
        mid_y = float(grid.property("contentY"))
        assert roll.property("navigating") or abs(mid_y - target_2018) < 5
        # Visible offset must move toward the destination (not only the requested target).
        if abs(start_y - target_2018) > 5:
            assert abs(mid_y - target_2018) <= abs(start_y - target_2018) + 1

        # Redirect in flight to 2025.
        _call(roll, "redirectNavigation", target_2025, "")
        assert _wait_nav(app, roll, 3.0)
        assert abs(float(grid.property("contentY")) - float(roll.property("navTargetY"))) < 3

        # Start toward 2018 again, then cancel mid-flight.
        _call(roll, "navigateToOffset", target_2018, "")
        _spin(app, 0.12)
        before_cancel = float(grid.property("contentY"))
        _call(roll, "cancelNavigation")
        _spin(app, 0.2)
        assert not roll.property("navigating")
        after_cancel = float(grid.property("contentY"))
        # Cancel leaves the actual position (no jump to the abandoned target).
        assert abs(after_cancel - before_cancel) < 80
        assert abs(after_cancel - target_2018) > 2 or abs(before_cancel - target_2018) < 2
    finally:
        shutdown_shell(engine)


def test_empty_year_has_slot_but_go_lands_on_populated_neighbour(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 12), (2021, 12)])  # gap 2022-2024
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        slots = scrub.property("slots").toVariant()["items"]
        years = [s for s in slots if s.get("kind") == "year"]
        labels = [s["label"] for s in years]
        assert "2025" in labels and "2021" in labels
        assert "2023" in labels
        empty = next(s for s in years if s["label"] == "2023")
        assert empty.get("populated") is False
        # Click in the empty-year gap → nearest populated detent, not a fake 2023 destination.
        _call(scrub, "go", empty["y"] + empty["h"] / 2)
        assert _wait_nav(app, roll, 2.5)
        month = str(roll.property("currentMonth") or "")
        assert month[:4] in {"2025", "2021"}
        assert month[:4] != "2023"
        pill = root.findChild(QQuickItem, "destinationPill")
        # After settle, pill is gone.
        assert pill is None or not pill.isVisible()
    finally:
        shutdown_shell(engine)


def test_strip_interaction_armed_tracking_settling(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2024, 20), (2023, 20), (2022, 20)], undated=3)
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        assert scrub.property("mode") == "idle"
        slots = scrub.property("slots").toVariant()["items"]
        target = next(s for s in slots if s.get("kind") == "year" and s.get("populated"))
        _call(scrub, "arm", target["y"] + 2)
        assert scrub.property("mode") == "armed"
        # Below threshold stays armed.
        _call(scrub, "track", target["y"] + 2 + 2)
        assert scrub.property("mode") == "armed"
        _call(scrub, "track", target["y"] + 2 + 20)
        assert scrub.property("mode") == "tracking"
        assert int(scrub.property("destinationYear")) == int(target["year"])
        _call(scrub, "release", target["y"] + 22)
        assert scrub.property("mode") in {"settling", "idle"}
        assert _wait_nav(app, roll, 2.5)
        assert scrub.property("mode") == "idle"
    finally:
        shutdown_shell(engine)


def test_viewport_segment_and_undated_indicator(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 30), (2024, 30)], undated=8)
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        marker = root.findChild(QQuickItem, "scrubMarker")
        assert marker is not None
        # Jump to undated terminal.
        geom = bridge.temporalNavGeometry(
            int(roll.property("columns")), True, True,
            float(roll.property("cellW")), float(roll.property("monthH")), float(roll.property("dayH")),
        )
        assert geom["undated"] is not None
        band = float(roll.property("headerHeight") or 0)
        _call(roll, "navigateToOffset", max(0.0, float(geom["undated"]["contentStart"]) - band), "")
        assert _wait_nav(app, roll, 2.5)
        _spin(app, 0.3)
        # Force a passive segment refresh after navigation.
        _call(scrub, "updateViewportSeg")
        _spin(app, 0.1)
        undated = root.findChild(QQuickItem, "undatedIndicator")
        assert undated is not None and undated.isVisible()
    finally:
        shutdown_shell(engine)


def test_keyboard_steps_populated_years_only(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 10), (2021, 10)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        scrub.forceActiveFocus()
        _spin(app, 0.1)
        _call(scrub, "stepToEnd", False)
        assert _wait_nav(app, roll, 2.5)
        assert str(roll.property("currentMonth") or "").startswith("2021")
        _call(scrub, "stepToEnd", True)
        assert _wait_nav(app, roll, 2.5)
        assert str(roll.property("currentMonth") or "").startswith("2025")
    finally:
        shutdown_shell(engine)
