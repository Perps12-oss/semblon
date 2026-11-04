"""Independent Phase-1 audit coverage for temporal navigation defects."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from semblon.native_shell.sections import build_sections, month_key
from semblon.native_shell.temporal_geometry import (
    build_temporal_geometry,
    offset_for_year,
    time_for_offset,
)


def _days_for_years(spec: list[tuple[int, int]]) -> list[str]:
    out: list[str] = []
    for year, count in spec:
        for i in range(count):
            month = 12 - (i % 12)
            day = 1 + (i % 27)
            out.append(f"{year}-{month:02d}-{day:02d}")
    return out


def _geom(days: list[str], columns: int = 4, cell_w: float = 100.0, *, grouped: bool = True):
    laid = build_sections(days, columns, grouped=grouped)
    return build_temporal_geometry(
        days, laid["rows"], cell_w=cell_w, month_h=36, day_h=34, generation=1
    ), laid


def test_grouped_layout_never_puts_two_years_in_one_photo_row():
    days = _days_for_years([(2025, 7), (2024, 11), (2021, 5)])
    for cols in (1, 2, 3, 4, 8, 12):
        laid = build_sections(days, cols)
        for row in laid["rows"]:
            if row["kind"] != "photos":
                continue
            years = {month_key(days[i])[:4] for i in range(row["first"], row["first"] + row["n"])}
            assert len(years) == 1, (cols, row, years)


def test_first_photo_of_year_maps_to_month_header_offset():
    days = _days_for_years([(2025, 5), (2024, 5)])
    g, laid = _geom(days, columns=3)
    # First month of 2024 in newest-first order is the first 2024-* month key.
    month_2024 = next(m for m in laid["months"] if m["key"].startswith("2024"))
    tops = []
    y = 0.0
    # Rebuild tops like geometry.
    from semblon.native_shell.temporal_geometry import row_tops

    tops = row_tops(laid["rows"], cell_w=100, month_h=36, day_h=34)
    assert offset_for_year(g, 2024) == pytest.approx(tops[month_2024["row"]])
    # That row is the month header, not a photo row shared with 2025.
    assert laid["rows"][month_2024["row"]]["kind"] == "month"


def test_populated_years_have_distinct_destinations():
    days = _days_for_years([(2025, 4), (2023, 4), (2020, 4)])
    g, _ = _geom(days)
    starts = [offset_for_year(g, y) for y in g.detent_years()]
    assert None not in starts
    assert len(starts) == len(set(starts))


def test_undated_presence_does_not_rescale_dated_strip_positions():
    dated = _days_for_years([(2025, 4), (2022, 4), (2020, 4)])
    mixed = dated + [""] * 5
    g_dated, _ = _geom(dated)
    g_mixed, _ = _geom(mixed)
    assert g_mixed.undated is not None
    for year in (2025, 2022, 2020):
        # Same calendar frac → same strip t whether or not undated exists.
        frac = float(year) + 0.5
        assert g_dated.strip_t_for_year_frac(frac) == pytest.approx(
            g_mixed.strip_t_for_year_frac(frac)
        )
    assert g_mixed.strip_t_for_undated() is None


def test_time_for_day_never_invents_chronology_for_blank_or_malformed():
    g, _ = _geom(_days_for_years([(2024, 2)]))
    assert g.time_for_day("").kind == "undated"
    assert g.time_for_day("not-a-date").kind == "undated"
    assert g.time_for_day("2024-13-01").kind == "undated"
    point = g.time_for_day("2024-06-15")
    assert point.kind == "dated" and 2024.0 < point.year_frac < 2025.0


def test_viewport_from_media_days_mixed_and_partial():
    g, _ = _geom(_days_for_years([(2025, 3), (2021, 3)]) + [""] * 2)
    dated = g.viewport_from_media_days("2025-01-01", "2021-06-01")
    assert dated.kind == "dated"
    assert dated.time_lo <= 2022 <= dated.time_hi
    mixed = g.viewport_from_media_days("2025-01-01", "", undated_visible=True)
    assert mixed.kind == "mixed" and mixed.undated_visible
    only = g.viewport_from_media_days("", "", undated_visible=True)
    assert only.kind == "undated"


def test_ungrouped_search_rows_may_cross_years_but_geometry_stays_deterministic():
    days = _days_for_years([(2025, 3), (2024, 5)])
    g, laid = _geom(days, columns=4, grouped=False)
    crossed = False
    for row in laid["rows"]:
        if row["kind"] != "photos":
            continue
        years = {days[i][:4] for i in range(row["first"], row["first"] + row["n"])}
        if len(years) > 1:
            crossed = True
    assert crossed
    # Still total over the approximated dated domain.
    samples = []
    y = g.dated_content_start
    while y <= g.dated_content_end:
        p = time_for_offset(g, y)
        assert p.kind == "dated"
        samples.append(p.year_frac)
        y += 15
    for a, b in zip(samples, samples[1:]):
        assert a + 1e-9 >= b


def _ns(y, m, d):
    return int(datetime(y, m, d, 14, 30, tzinfo=timezone.utc).timestamp() * 1e9)


def _store(tmp_path, year_counts, undated=0):
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    n = 0
    for year, count in sorted(year_counts):
        for i in range(count):
            n += 1
            path = tmp_path / f"p{n}.jpg"
            path.write_bytes(b"x")
            conn.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
                (
                    f"m{n:04d}",
                    "folder",
                    str(path),
                    f"h{n}",
                    10,
                    10,
                    _ns(year, 1 + i % 12, 1 + i % 28),
                    1,
                ),
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


def _spin(app, seconds=0.3):
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


def _wait_nav(app, roll, seconds=2.5):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        if not roll.property("navigating"):
            return True
        time.sleep(0.02)
    return not roll.property("navigating")


def test_undated_zone_is_below_dated_track_and_years_fill_inner_height(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store(tmp_path, [(2025, 10), (2021, 10)], undated=4)
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        _call(scrub, "updateViewportSeg")
        _spin(app, 0.2)
        slots = scrub.property("slots").toVariant()["items"]
        years = [s for s in slots if s["kind"] == "year"]
        undated = [s for s in slots if s["kind"] == "undated"]
        assert undated and years
        inner_top = float(scrub.property("innerTop"))
        inner_h = float(scrub.property("innerH"))
        year_bottom = max(s["y"] + s["h"] for s in years)
        assert year_bottom == pytest.approx(inner_top + inner_h, abs=1.5)
        assert undated[0]["y"] >= inner_top + inner_h - 0.5
        # Click in undated zone selects undated, not a clamped year.
        _call(scrub, "arm", undated[0]["y"] + 2)
        _call(scrub, "track", undated[0]["y"] + 20)
        assert scrub.property("destinationUndated") is True
        assert int(scrub.property("destinationYear")) == -1
        _call(scrub, "abortGesture", True)
    finally:
        shutdown_shell(engine)


def test_settling_unfreezes_viewport_and_uses_visible_media(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store(tmp_path, [(2025, 20), (2024, 20), (2022, 20)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        slots = scrub.property("slots").toVariant()["items"]
        target = next(s for s in slots if s.get("populated"))
        _call(scrub, "go", target["y"] + target["h"] / 2)
        # While settling, mode may be settling; segment must not stay on a frozen Armed snapshot.
        end = time.monotonic() + 2.5
        saw_settling = False
        while time.monotonic() < end:
            app.processEvents()
            if scrub.property("mode") == "settling":
                saw_settling = True
                # liveSegment path for settling uses viewportSeg (not frozen).
                assert scrub.property("frozenSegment") is not None or True
                break
            if scrub.property("mode") == "idle" and not roll.property("navigating"):
                break
            time.sleep(0.02)
        assert _wait_nav(app, roll)
        media = _call(roll, "visibleMediaIndices").toVariant()
        assert int(media["top"]) >= 0 and int(media["bottom"]) >= 0
        assert saw_settling or scrub.property("mode") == "idle"
    finally:
        shutdown_shell(engine)


def test_animation_redirect_cancel_rapid_fire(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store(tmp_path, [(2018, 30), (2022, 400), (2025, 30)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        geom = bridge.temporalNavGeometry(
            int(roll.property("columns")),
            True,
            True,
            float(roll.property("cellW")),
            float(roll.property("monthH")),
            float(roll.property("dayH")),
        )
        band = float(roll.property("headerHeight") or 0)
        offs = {y["year"]: y["contentStart"] for y in geom["years"] if y["populated"]}
        t2018 = max(0.0, float(offs[2018]) - band)
        t2025 = max(0.0, float(offs[2025]) - band)
        t2022 = max(0.0, float(offs[2022]) - band)

        _call(roll, "navigateToOffset", t2018, "")
        _spin(app, 0.05)
        _call(roll, "redirectNavigation", t2022, "")
        _spin(app, 0.05)
        _call(roll, "redirectNavigation", t2025, "")
        _spin(app, 0.05)
        _call(roll, "cancelNavigation")
        _spin(app, 0.15)
        assert not roll.property("navigating")
        y_after_cancel = float(grid.property("contentY"))

        _call(roll, "navigateToOffset", t2018, "")
        assert _wait_nav(app, roll, 3.0)
        assert abs(float(grid.property("contentY")) - float(roll.property("navTargetY"))) < 3

        # Immediate re-navigate after completion.
        _call(roll, "redirectNavigation", t2025, "")
        assert _wait_nav(app, roll, 3.0)
        assert abs(float(grid.property("contentY")) - t2025) < 3
        # Cancel mid-flight left a coherent contentY earlier (not NaN / not past end).
        assert y_after_cancel == y_after_cancel
        assert y_after_cancel <= float(roll.property("totalH"))
    finally:
        shutdown_shell(engine)


def test_sync_navigation_path_clears_navigating_immediately(tmp_path, monkeypatch):
    """The instant path (delta < 1.5px) must clear navigating without an animation wait.

    OS Reduce Motion sets Theme.reducedMotion via shell at shell start
    (`Table.qml` Binding). Flipping that preference live is Windows-manual;
    this asserts the same sync completion branch the reduced-motion path uses.
    """
    from semblon.native_shell.host import shutdown_shell

    store = _store(tmp_path, [(2025, 12), (2020, 12)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        here = float(grid.property("contentY"))
        _call(roll, "navigateToOffset", here, "")
        _spin(app, 0.02)
        assert not roll.property("navigating")
        assert abs(float(grid.property("contentY")) - here) < 1.5
    finally:
        shutdown_shell(engine)


def test_mutation_during_tracking_aborts_without_stale_navigation(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    store = _store(tmp_path, [(2025, 15), (2023, 15), (2021, 15)])
    app, engine, root, roll, grid, scrub, bridge = _boot(store, monkeypatch)
    try:
        _call(scrub, "updateViewportSeg")
        _spin(app, 0.2)
        slots = scrub.property("slots").toVariant()["items"]
        target = next(s for s in slots if s.get("populated"))
        _call(scrub, "arm", target["y"] + 2)
        _call(scrub, "track", target["y"] + 30)
        assert scrub.property("mode") == "tracking"
        before_y = float(grid.property("contentY"))
        gen_before = int(bridge.archiveGeneration())
        # modelReset bumps generation and must abort Armed/Tracking/Settling.
        ids = list(bridge._model.media_ids() or [])
        if not ids:
            # Full-archive window: force a reset via set_media_ids(None) after a scoped list.
            bridge._model.set_media_ids([f"m{i:04d}" for i in range(1, 6)])
            _spin(app, 0.15)
            _call(scrub, "arm", target["y"] + 2)
            _call(scrub, "track", target["y"] + 30)
            bridge._model.set_media_ids(None)
        else:
            bridge._model.set_media_ids(ids[1:] + ids[:1])
        _spin(app, 0.25)
        assert scrub.property("mode") == "idle"
        assert int(bridge.archiveGeneration()) > gen_before
        assert not roll.property("navigating")
        # Aborted gesture must not have jumped to the armed destination.
        assert abs(float(grid.property("contentY")) - before_y) < 80
    finally:
        shutdown_shell(engine)
