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


def test_loupe_flag_defaults_off_and_restores_pill(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem

    from semblon.native_shell.host import shutdown_shell

    store = _store_years(tmp_path, [(2024, 20), (2022, 20)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        assert bridge.loupeEnabled is False
        assert scrub.property("loupeEnabled") is False
        target = _slot(scrub)
        _call(scrub, "arm", target["y"] + 2)
        _call(scrub, "track", target["y"] + 30)
        assert scrub.property("mode") == "tracking"
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        pill = root.findChild(QQuickItem, "destinationPill")
        assert loupe is None or not loupe.isVisible()
        assert pill is not None and pill.isVisible()
        _call(scrub, "abortGesture", True)
        _spin(app, 0.1)

        bridge.setLoupeEnabled(True)
        _spin(app, 0.1)
        assert scrub.property("loupeEnabled") is True
        _call(scrub, "arm", target["y"] + 2)
        _call(scrub, "track", target["y"] + 30)
        assert scrub.property("mode") == "tracking"
        loupe = root.findChild(QQuickItem, "temporalLoupe")
        pill = root.findChild(QQuickItem, "destinationPill")
        assert loupe is not None and loupe.isVisible()
        assert pill is None or not pill.isVisible()
        assert scrub.property("loupeVisible") is True
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


def test_click_without_drag_noop_when_loupe_enabled(tmp_path, monkeypatch):
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
        secondary = root.findChild(QQuickItem, "loupeSecondary")
        assert secondary is not None
        text = str(secondary.property("text") or "")
        assert "empty" in text.lower() or "2023" in text
        hatch = root.findChild(QQuickItem, "loupeEmptyHatch")
        assert hatch is not None and hatch.isVisible()
        primary = root.findChild(QQuickItem, "loupePrimary")
        assert primary is not None
        assert str(dest_year) in str(primary.property("text") or "")
        assert "2023" not in str(primary.property("text") or "")
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
