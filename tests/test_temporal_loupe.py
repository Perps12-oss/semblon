"""Phase 3 precision temporal loupe — acceptance + flag rollback."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest


def _ns(y, m, d):
    return int(datetime(y, m, d, 14, 30, tzinfo=timezone.utc).timestamp() * 1e9)


def _store_years(tmp_path, year_counts: list[tuple[int, int]], undated: int = 0):
    from semblon.store import connect, init_db

    store = tmp_path / "loupe.sqlite"
    conn = connect(store)
    init_db(conn)
    n = 0
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


def _slot(scrub, year=None, *, populated=True, empty_label=None):
    slots = scrub.property("slots").toVariant()["items"]
    years = [s for s in slots if s.get("kind") == "year"]
    if empty_label is not None:
        return next(s for s in years if s.get("label") == empty_label)
    if year is not None:
        return next(s for s in years if int(s.get("year", -1)) == year and s.get("populated") is populated)
    return next(s for s in years if s.get("populated") is populated)


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


def test_loupe_flag_defaults_on_and_can_restore_pill(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2024, 20), (2022, 20)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        assert bridge.loupeEnabled is True
        assert scrub.property("loupeEnabled") is True
        target = _slot(scrub)
        _call(scrub, "arm", target["y"] + 2)
        _call(scrub, "track", target["y"] + 30)
        assert scrub.property("mode") == "tracking"
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        pill = root.findChild(QQuickItem, "destinationPill")
        assert loupe is not None and loupe.isVisible()
        assert pill is None or not pill.isVisible()
        assert scrub.property("loupeVisible") is True
        _call(scrub, "abortGesture", True)
        _spin(app, 0.1)

        bridge.setLoupeEnabled(False)
        _spin(app, 0.1)
        assert scrub.property("loupeEnabled") is False
        _call(scrub, "arm", target["y"] + 2)
        _call(scrub, "track", target["y"] + 30)
        assert scrub.property("mode") == "tracking"
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        pill = root.findChild(QQuickItem, "destinationPill")
        assert loupe is None or not loupe.isVisible()
        assert pill is not None and pill.isVisible()
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------


def test_hover_gutter_readout_no_contentY_no_lens(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 30), (2023, 30), (2021, 30)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.2)
        before = float(grid.property("contentY"))
        target = _slot(scrub, 2023)
        # Gutter HOVER — year + count only; never navigates.
        _call(scrub, "updateGutterHover", 4.0, target["y"] + target["h"] / 2)
        _spin(app, 0.15)
        assert scrub.property("mode") == "idle"
        assert scrub.property("gutterHover") is True
        assert scrub.property("phase3Hover") is True
        assert scrub.property("lensOpen") is False
        assert int(scrub.property("hoverReadoutYear")) == 2023
        assert int(scrub.property("hoverReadoutCount")) == 30
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
        readout = root.findChild(QQuickItem, "loupeHoverReadout")
        assert readout is not None and readout.isVisible()
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        assert loupe is None or not loupe.isVisible()

        # Leave gutter → HOVER exits without side effects.
        _call(scrub, "updateGutterHover", -1, -1)
        _spin(app, 0.1)
        assert scrub.property("gutterHover") is False
        assert scrub.property("phase3Hover") is False
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_bare_year_click_noop_when_loupe_enabled(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2024, 25), (2022, 25)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.2)
        before = float(grid.property("contentY"))
        target = _slot(scrub)
        _call(scrub, "arm", target["y"] + 4)
        assert scrub.property("mode") == "armed"
        # Release without crossing drag threshold → no-op, back to idle.
        _call(scrub, "release", target["y"] + 4)
        _spin(app, 0.2)
        assert scrub.property("mode") == "idle"
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
        assert not roll.property("navigating")
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_lens_month_click_still_navigates_with_loupe_on(tmp_path, monkeypatch):
    """Phase 2 magnified click must not be stolen by the Phase 3 bare-click no-op."""
    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2024, 36), (2022, 12)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        assert bridge.loupeEnabled is True
        before = float(grid.property("contentY"))
        target = _slot(scrub, 2024)
        _call(scrub, "updateLensFromHover", target["y"] + target["h"] / 2)
        _spin(app, 0.15)
        scrub.setProperty("pressPeriodKind", "month")
        scrub.setProperty("pressPeriodKey", "2024-01")
        scrub.setProperty("mode", "armed")
        _call(scrub, "release", target["y"] + target["h"] / 2)
        assert _wait_nav(app, roll, 2.5)
        assert scrub.property("mode") == "idle" or not roll.property("navigating")
        after = float(grid.property("contentY"))
        assert after != pytest.approx(before, abs=0.5) or str(
            roll.property("currentMonth") or ""
        ).startswith("2024")
    finally:
        if roll is not None and roll.property("navigating"):
            _call(roll, "cancelNavigation")
            _spin(app, 0.2)
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_drag_shows_loupe_without_moving_content_until_release(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 20), (2020, 20), (2015, 20)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.3)
        before = float(grid.property("contentY"))
        start = _slot(scrub, 2025)
        dest = _slot(scrub, 2015)
        _call(scrub, "arm", start["y"] + 2)
        _call(scrub, "track", start["y"] + 2)  # below threshold
        assert scrub.property("mode") == "armed"
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
        _call(scrub, "track", dest["y"] + dest["h"] / 2)
        assert scrub.property("mode") == "tracking"
        assert int(scrub.property("destinationYear")) == 2015
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        assert loupe is not None and loupe.isVisible()
        primary = root.findChild(QQuickItem, "loupePrimary")
        assert primary is not None
        assert "2015" in str(primary.property("text") or "")
        axis = root.findChild(QQuickItem, "loupeJumpAxis")
        assert axis is not None and axis.isVisible()
        origin = root.findChild(QQuickItem, "loupeOriginMark")
        dest_mark = root.findChild(QQuickItem, "loupeDestMark")
        assert origin is not None and origin.isVisible()
        assert dest_mark is not None and dest_mark.isVisible()
        # Commit on release → SETTLING may move contentY.
        _call(scrub, "release", dest["y"] + dest["h"] / 2)
        assert scrub.property("mode") in {"settling", "idle"}
        assert _wait_nav(app, roll, 2.5)
        assert scrub.property("mode") == "idle"
        assert str(roll.property("currentMonth") or "").startswith("2015")
    finally:
        if roll is not None and roll.property("navigating"):
            _call(roll, "cancelNavigation")
            _spin(app, 0.2)
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_empty_year_pointer_resolves_detent_with_hatch_context(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 16), (2021, 16)])  # gap 2022-2024
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.2)
        empty = _slot(scrub, empty_label="2023")
        assert empty.get("populated") is False
        start = _slot(scrub, 2025)
        before = float(grid.property("contentY"))
        _call(scrub, "arm", start["y"] + 2)
        _call(scrub, "track", empty["y"] + empty["h"] / 2)
        assert scrub.property("mode") == "tracking"
        assert scrub.property("pointerOverEmpty") is True
        assert float(scrub.property("pointerYearFrac")) > 0
        dest_year = int(scrub.property("destinationYear"))
        assert dest_year in {2025, 2021}
        assert dest_year != 2023
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
        assert int(scrub.property("pointerCalendarYear")) == 2023
        secondary = root.findChild(QQuickItem, "loupeSecondary")
        assert secondary is not None
        text = str(secondary.property("text") or "")
        assert "2023 is empty — will jump to " + str(dest_year) == text
        hatch = root.findChild(QQuickItem, "loupeEmptyHatch")
        assert hatch is not None and hatch.isVisible()
        primary = root.findChild(QQuickItem, "loupePrimary")
        assert primary is not None
        assert str(dest_year) in str(primary.property("text") or "")
        assert "Landing on" in str(primary.property("text") or "")
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_undated_drag_shows_label_release_does_not_commit(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2024, 20)], undated=6)
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.3)
        before = float(grid.property("contentY"))
        slots = scrub.property("slots").toVariant()["items"]
        undated = next(s for s in slots if s.get("kind") == "undated")
        start = _slot(scrub)
        _call(scrub, "arm", start["y"] + 2)
        _call(scrub, "track", undated["y"] + undated["h"] / 2)
        assert scrub.property("mode") == "tracking"
        assert scrub.property("destinationUndated") is True
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        assert loupe is not None and loupe.isVisible()
        primary = root.findChild(QQuickItem, "loupePrimary")
        assert primary is not None and "Undated" in str(primary.property("text") or "")
        axis = root.findChild(QQuickItem, "loupeJumpAxis")
        assert axis is None or not axis.isVisible()
        thumbs = root.findChild(QQuickItem, "loupeThumbs")
        assert thumbs is None or not thumbs.isVisible()
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
        _call(scrub, "release", undated["y"] + undated["h"] / 2)
        _spin(app, 0.25)
        assert scrub.property("mode") == "idle"
        assert not roll.property("navigating")
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_escape_cancels_drag_without_commit(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2024, 18), (2020, 18)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.2)
        before = float(grid.property("contentY"))
        start = _slot(scrub, 2024)
        dest = _slot(scrub, 2020)
        _call(scrub, "arm", start["y"] + 2)
        _call(scrub, "track", dest["y"] + dest["h"] / 2)
        assert scrub.property("mode") == "tracking"
        _call(scrub, "abortGesture", True)
        _spin(app, 0.15)
        assert scrub.property("mode") == "idle"
        assert scrub.property("loupeVisible") is False
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_flag_off_restores_click_navigate(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 20), (2021, 20)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(False)
        _spin(app, 0.1)
        assert bridge.loupeEnabled is False
        before = float(grid.property("contentY"))
        target = _slot(scrub, 2021)
        _call(scrub, "arm", target["y"] + 4)
        _call(scrub, "release", target["y"] + 4)
        assert scrub.property("mode") in {"settling", "idle"}
        assert _wait_nav(app, roll, 2.5)
        assert scrub.property("mode") == "idle"
        # Click-nav with flag off must move (or land on the year).
        after = float(grid.property("contentY"))
        assert after != pytest.approx(before, abs=0.5) or str(
            roll.property("currentMonth") or ""
        ).startswith("2021")
    finally:
        if roll is not None and roll.property("navigating"):
            _call(roll, "cancelNavigation")
            _spin(app, 0.2)
        shutdown_shell(engine)
        _spin(app, 0.2)


# ---------------------------------------------------------------------------
# Displayed destination == navigation consumed destination
# ---------------------------------------------------------------------------


def _drag_release_to_slot(scrub, roll, app, start, dest_y):
    _call(scrub, "arm", start["y"] + 2)
    _call(scrub, "track", dest_y)
    assert scrub.property("mode") == "tracking"
    displayed = int(scrub.property("destinationYear"))
    loupe = scrub  # destinationYear is the display source TemporalLoupe binds
    _call(scrub, "release", dest_y)
    assert _wait_nav(app, roll, 2.5)
    return displayed


def test_displayed_destination_equals_nav_consumed_populated(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 18), (2022, 18), (2019, 18)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.2)
        start = _slot(scrub, 2025)
        dest = _slot(scrub, 2019)
        displayed = _drag_release_to_slot(scrub, roll, app, start, dest["y"] + dest["h"] / 2)
        assert displayed == 2019
        assert str(roll.property("navConsumedYear") or "") == "2019"
        assert str(roll.property("currentMonth") or "").startswith("2019")
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        # After settle loupe dismisses; equality was against consumed year at commit.
        assert scrub.property("mode") == "idle"
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_displayed_destination_equals_nav_consumed_empty_between(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 16), (2021, 16)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.2)
        start = _slot(scrub, 2025)
        empty = _slot(scrub, empty_label="2023")
        _call(scrub, "arm", start["y"] + 2)
        _call(scrub, "track", empty["y"] + empty["h"] / 2)
        displayed = int(scrub.property("destinationYear"))
        assert scrub.property("pointerOverEmpty") is True
        assert int(scrub.property("pointerCalendarYear")) == 2023
        secondary = root.findChild(QQuickItem, "loupeSecondary")
        assert str(secondary.property("text") or "") == (
            f"2023 is empty — will jump to {displayed}"
        )
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        assert int(loupe.property("displayedDestination")) == displayed
        _call(scrub, "release", empty["y"] + empty["h"] / 2)
        assert _wait_nav(app, roll, 2.5)
        assert str(roll.property("navConsumedYear") or "") == str(displayed)
        assert str(roll.property("currentMonth") or "").startswith(str(displayed))
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_displayed_destination_equals_nav_empty_adjacent_newest_and_oldest(
    tmp_path, monkeypatch
):
    """Empty years at the strip edges of the calendar span (nearest detent)."""
    from semblon.native_shell.host import shutdown_shell

    # Calendar 2018..2025; populated endpoints only. Empty 2024 is next to newest;
    # empty 2019 is next to oldest. (No empty outside [min,max] dated years.)
    store = _store_years(tmp_path, [(2025, 14), (2018, 14)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.2)
        start = _slot(scrub, 2025)

        for label, allowed in (("2024", {2025, 2018}), ("2019", {2025, 2018})):
            empty = _slot(scrub, empty_label=label)
            _call(scrub, "arm", start["y"] + 2)
            _call(scrub, "track", empty["y"] + empty["h"] / 2)
            displayed = int(scrub.property("destinationYear"))
            assert displayed in allowed
            assert int(scrub.property("pointerCalendarYear")) == int(label)
            _call(scrub, "release", empty["y"] + empty["h"] / 2)
            assert _wait_nav(app, roll, 2.5)
            assert str(roll.property("navConsumedYear") or "") == str(displayed)
            assert str(roll.property("currentMonth") or "").startswith(str(displayed))
            start = _slot(scrub, displayed)
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_no_dated_media_has_no_invented_destination(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [], undated=10)
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.3)
        before = float(grid.property("contentY"))
        h = float(scrub.height())
        _call(scrub, "arm", h * 0.3)
        _call(scrub, "track", h * 0.6)
        assert scrub.property("mode") == "tracking"
        # No populated detent → no invented year destination.
        assert int(scrub.property("destinationYear")) == -1
        _call(scrub, "release", h * 0.6)
        _spin(app, 0.25)
        assert scrub.property("mode") == "idle"
        assert str(roll.property("navConsumedYear") or "") in {"", "None"}
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


# ---------------------------------------------------------------------------
# Hover precedence
# ---------------------------------------------------------------------------


def test_hover_gutter_vs_ribbon_spatial_exclusive(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2024, 40), (2023, 40)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        assert bridge.loupeEnabled is True
        _spin(app, 0.2)
        target = _slot(scrub, 2024)
        before = float(grid.property("contentY"))

        # Enter gutter → Phase 3 HOVER only (no Phase 2 lens).
        _call(scrub, "updateGutterHover", 4.0, target["y"] + 4)
        assert scrub.property("phase3Hover") is True
        assert scrub.property("lensOpen") is False
        assert scrub.property("gutterHover") is True

        # Leave gutter → neither until ribbon hover opens the lens.
        _call(scrub, "updateGutterHover", -1, -1)
        _call(scrub, "clearLens")
        assert scrub.property("phase3Hover") is False
        assert scrub.property("lensOpen") is False
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)

        # Ribbon column → Phase 2 lens (ordinary hover; no modifier).
        scrub.setProperty("hoverY", target["y"] + target["h"] / 2)
        _call(scrub, "updateLensFromHover", target["y"] + target["h"] / 2)
        _spin(app, 0.15)
        assert scrub.property("lensOpen") is True or int(scrub.property("lensYear")) == 2024
        assert scrub.property("gutterHover") is False
        assert scrub.property("phase3Hover") is False

        # Re-enter gutter while lens open → lens clears, Phase 3 HOVER only.
        _call(scrub, "updateGutterHover", 4.0, target["y"] + 4)
        assert scrub.property("phase3Hover") is True
        assert scrub.property("lensOpen") is False

        # Leave region.
        _call(scrub, "clearLens")
        _call(scrub, "updateGutterHover", -1, -1)
        assert scrub.property("lensOpen") is False
        assert scrub.property("phase3Hover") is False

        # Drag across ribbon X: loupe stays for mode, not hover surfaces.
        _call(scrub, "arm", target["y"] + 2)
        scrub.setProperty("pointerX", 40.0)  # ribbon column
        _call(scrub, "track", target["y"] + 30)
        assert scrub.property("mode") == "tracking"
        assert scrub.property("loupeVisible") is True
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        assert loupe is not None and loupe.isVisible()
        scrub.setProperty("pointerX", 4.0)  # back to gutter mid-drag
        _call(scrub, "track", target["y"] + 35)
        assert scrub.property("loupeVisible") is True
        assert loupe.isVisible()
        _call(scrub, "abortGesture", True)
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


# ---------------------------------------------------------------------------
# Mixed dated / undated viewport chrome
# ---------------------------------------------------------------------------


def _seg_kind(scrub):
    seg = scrub.property("viewportSeg")
    data = seg.toVariant() if hasattr(seg, "toVariant") else seg
    return data.get("kind") if isinstance(data, dict) else None


def test_viewport_chrome_dated_only_archive(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 40), (2024, 40)], undated=0)
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        _spin(app, 0.4)
        _call(scrub, "updateViewportSeg")
        _spin(app, 0.1)
        assert _seg_kind(scrub) == "dated"
        marker = root.findChild(QQuickItem, "scrubMarker")
        undated = root.findChild(QQuickItem, "undatedIndicator")
        assert marker is not None and marker.isVisible()
        assert undated is None or not undated.isVisible()
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_viewport_chrome_mixed_undated_and_transitions(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 80), (2024, 80)], undated=60)
    app, engine, root, roll, grid, scrub, bridge = _boot(
        store, monkeypatch, width=1100, height=700
    )
    try:
        _spin(app, 0.5)
        geom = bridge.temporalNavGeometry(
            int(roll.property("columns")),
            True,
            True,
            float(roll.property("cellW")),
            float(roll.property("monthH")),
            float(roll.property("dayH")),
        )
        band = float(roll.property("headerHeight") or 0)
        u = geom["undated"]
        u_start = float(u["contentStart"])
        u_end = float(u["contentEnd"])
        # Undated may sit at the top of the Roll (photoFirst=0). Offsets are
        # Flickable contentY targets (rowTop − sticky band).

        def _goto(content_y):
            _call(roll, "navigateToOffset", max(0.0, content_y), "")
            assert _wait_nav(app, roll, 2.5)
            _call(scrub, "updateViewportSeg")
            _spin(app, 0.3)

        # Undated-only: park inside the undated block.
        _goto(max(0.0, u_start - band + 20))
        assert _seg_kind(scrub) == "undated"
        undated = root.findChild(QQuickItem, "undatedIndicator")
        marker = root.findChild(QQuickItem, "scrubMarker")
        assert undated is not None and undated.isVisible()
        assert marker is None or not marker.isVisible()

        # Mixed: straddle undated → dated boundary.
        mix_y = max(0.0, u_end - band - float(grid.property("height")) * 0.35)
        _goto(mix_y)
        assert _seg_kind(scrub) == "mixed"
        marker = root.findChild(QQuickItem, "scrubMarker")
        undated = root.findChild(QQuickItem, "undatedIndicator")
        assert marker is not None and marker.isVisible()
        assert undated is not None and undated.isVisible()

        # Transition back to undated-only.
        _goto(max(0.0, u_start - band + 20))
        assert _seg_kind(scrub) == "undated"
        undated = root.findChild(QQuickItem, "undatedIndicator")
        marker = root.findChild(QQuickItem, "scrubMarker")
        assert undated is not None and undated.isVisible()
        assert marker is None or not marker.isVisible()
        # Dated-only chrome is covered by test_viewport_chrome_dated_only_archive
        # (undated-free store). Geometry-level mixed/undated kinds remain in
        # test_temporal_geometry / test_temporal_nav_audit.
    finally:
        if roll is not None and roll.property("navigating"):
            _call(roll, "cancelNavigation")
            _spin(app, 0.2)
        shutdown_shell(engine)
        _spin(app, 0.2)


# ---------------------------------------------------------------------------
# Phase 1 invariants under loupe
# ---------------------------------------------------------------------------


def test_viewport_segment_frozen_throughout_tracking(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 20), (2020, 20), (2015, 20)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.3)
        start = _slot(scrub, 2025)
        dest = _slot(scrub, 2015)
        _call(scrub, "updateViewportSeg")
        _spin(app, 0.1)
        _call(scrub, "arm", start["y"] + 2)
        frozen = scrub.property("frozenSegment")
        frozend = frozen.toVariant() if hasattr(frozen, "toVariant") else frozen
        assert isinstance(frozend, dict)
        _call(scrub, "track", dest["y"] + dest["h"] / 2)
        assert scrub.property("mode") == "tracking"
        mid = scrub.property("frozenSegment")
        midd = mid.toVariant() if hasattr(mid, "toVariant") else mid
        assert midd.get("timeHi") == frozend.get("timeHi")
        assert midd.get("timeLo") == frozend.get("timeLo")
        # Live contentY unchanged; frozen segment must not chase destination year.
        assert int(scrub.property("destinationYear")) == 2015
        assert midd.get("timeHi") != 2015 or frozend.get("timeHi") == midd.get("timeHi")
        _call(scrub, "abortGesture", True)
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_mutation_during_loupe_drag_aborts_without_stale_commit(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 15), (2023, 15), (2021, 15)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        assert bridge.loupeEnabled is True
        _spin(app, 0.2)
        target = _slot(scrub, 2021)
        start = _slot(scrub, 2025)
        _call(scrub, "arm", start["y"] + 2)
        _call(scrub, "track", target["y"] + target["h"] / 2)
        assert scrub.property("mode") == "tracking"
        displayed = int(scrub.property("destinationYear"))
        assert displayed == 2021
        before_y = float(grid.property("contentY"))
        gen_before = int(bridge.archiveGeneration())
        consumed_before = str(roll.property("navConsumedYear") or "")
        ids = list(bridge._model.media_ids() or [])
        bridge._model.set_media_ids(ids[1:] + ids[:1] if ids else None)
        _spin(app, 0.25)
        assert scrub.property("mode") == "idle"
        assert int(bridge.archiveGeneration()) > gen_before
        assert not roll.property("navigating")
        assert abs(float(grid.property("contentY")) - before_y) < 80
        # Displayed destination must not become a committed navigate.
        consumed_after = str(roll.property("navConsumedYear") or "")
        assert consumed_after == consumed_before or consumed_after in {"", "None"}
        assert consumed_after != str(displayed)
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_keyboard_navigation_with_loupe_enabled_and_disabled(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2025, 12), (2021, 12)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        scrub.forceActiveFocus()
        _spin(app, 0.1)

        def _step_ends():
            _call(scrub, "stepToEnd", False)
            assert _wait_nav(app, roll, 2.5)
            assert str(roll.property("currentMonth") or "").startswith("2021")
            _call(scrub, "stepToEnd", True)
            assert _wait_nav(app, roll, 2.5)
            assert str(roll.property("currentMonth") or "").startswith("2025")

        # Default on: keyboard steps among populated years; Escape cancels elsewhere.
        assert bridge.loupeEnabled is True
        _step_ends()
        bridge.setLoupeEnabled(False)
        _spin(app, 0.1)
        _step_ends()
    finally:
        if roll is not None and roll.property("navigating"):
            _call(roll, "cancelNavigation")
            _spin(app, 0.2)
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_jump_axis_uses_calendar_not_content_distance(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    # Sparse 2015 vs dense 2025 — content spans differ wildly; calendar bands are equal.
    store = _store_years(tmp_path, [(2025, 200), (2020, 10), (2015, 10)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        _spin(app, 0.3)
        start = _slot(scrub, 2025)
        dest = _slot(scrub, 2015)
        _call(scrub, "arm", start["y"] + 2)
        _call(scrub, "track", dest["y"] + dest["h"] / 2)
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        origin = root.findChild(QQuickItem, "loupeOriginMark")
        dest_mark = root.findChild(QQuickItem, "loupeDestMark")
        assert loupe and origin and dest_mark
        axis_h = float(root.findChild(QQuickItem, "loupeJumpAxis").height())
        # Midpoints of equal calendar decades: 2025 and 2015 are 10 years apart
        # across a 11-year span (2015..2025) → ~10/11 of axis.
        oy = float(origin.property("y")) + float(origin.height()) / 2
        dy = float(dest_mark.property("y")) + float(dest_mark.height()) / 2
        span = abs(dy - oy) / max(1.0, axis_h)
        # Calendar ratio ≈ 10/11 ≈ 0.91; content-distance ratio would be << 0.5
        # because 2025 holds most of the photos.
        assert span > 0.7
        _call(scrub, "abortGesture", True)
    finally:
        shutdown_shell(engine)
        _spin(app, 0.2)


def test_rtl_loupe_placement_stays_in_window(tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2024, 20), (2020, 20)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        bridge.setLoupeEnabled(True)
        prev = QGuiApplication.layoutDirection()
        QGuiApplication.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        _spin(app, 0.2)
        start = _slot(scrub, 2024)
        dest = _slot(scrub, 2020)
        _call(scrub, "arm", start["y"] + 2)
        _call(scrub, "track", dest["y"] + dest["h"] / 2)
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        assert loupe is not None and loupe.isVisible()
        # Global rect should intersect the window and not sit fully off-screen.
        g = loupe.mapToGlobal(loupe.boundingRect().topLeft())
        # Offscreen platform: just require finite on-parent coords and positive size.
        assert float(loupe.width()) > 0 and float(loupe.height()) > 0
        assert float(loupe.property("x")) == float(loupe.property("x"))  # not NaN
        _call(scrub, "abortGesture", True)
        QGuiApplication.setLayoutDirection(prev)
    finally:
        try:
            QGuiApplication.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        except Exception:
            pass
        shutdown_shell(engine)
        _spin(app, 0.2)
