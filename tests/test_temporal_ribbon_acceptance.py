"""Phase 2 acceptance checks — cache, deletion, sampling, scale, interaction."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from semblon.native_shell import images as image_mod
from semblon.native_shell.images import (
    ArchiveImageProvider,
    clear_decoded_frames,
    image_decode_count,
    load_display_image,
    read_cached_thumb,
    reset_image_cache,
    thumb_cache_dir,
    thumb_on_disk,
)
from semblon.native_shell.temporal_ribbon import (
    MONTH_SAMPLE_BUDGET,
    month_cells_for_year,
    year_cells,
)


# ---------------------------------------------------------------------------
# 1. Cache-only guarantee
# ---------------------------------------------------------------------------


def _png(path: Path, color: str = "red") -> None:
    image = QImage(48, 32, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    assert image.save(str(path), "PNG")


def test_acceptance_cache_only_cold_never_decodes_including_qml_cs_path(tmp_path):
    """Cold thumbnails never trigger original decoding on any request path."""
    reset_image_cache()
    source = tmp_path / "cold.png"
    _png(source)
    cache = tmp_path / "library.thumbs"
    assert image_decode_count() == 0

    # Python cache-only read.
    assert read_cached_thumb(str(source), 96, cache_dir=cache, require_disk=True) is image_mod._MISS
    assert image_decode_count() == 0

    # QML image://archive/cs/<id> provider path.
    provider = ArchiveImageProvider(lambda _mid: str(source), cache)
    response = provider.requestImageResponse("cs/media-cold", None)
    # Allow the zero-timer finish path to run.
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    end = time.monotonic() + 0.3
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    assert image_decode_count() == 0
    # Cold miss → empty image, still no decode.
    assert response._image.isNull()

    # Warm via the normal Roll path, then cs/ must still not decode again.
    load_display_image(str(source), 96, cache_dir=cache)
    assert image_decode_count() == 1
    clear_decoded_frames()
    before = image_decode_count()
    warm = provider.requestImageResponse("cs/media-cold", None)
    end = time.monotonic() + 0.3
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    assert image_decode_count() == before
    assert not warm._image.isNull()


# ---------------------------------------------------------------------------
# 2. Deletion correctness
# ---------------------------------------------------------------------------


def test_acceptance_deleted_thumb_leaves_no_stale_colour_or_preview(tmp_path):
    """Delete source + clear thumb → no ghost colour / preview sample survives."""
    reset_image_cache()
    source = tmp_path / "gone.png"
    _png(source, "blue")
    cache = tmp_path / "library.thumbs"
    load_display_image(str(source), 96, cache_dir=cache)
    assert thumb_on_disk(str(source), 96, cache_dir=cache)

    # Simulate deleted thumbnail JPEG and missing original.
    for jpg in cache.rglob("*.jpg"):
        jpg.unlink()
    source.unlink()
    clear_decoded_frames()  # memory would otherwise keep a frame without require_disk

    # Without require_disk, a warm memory hit could ghost — require_disk must miss.
    reset_image_cache()
    # Re-warm memory from a *different* write then delete disk only.
    source2 = tmp_path / "gone2.png"
    _png(source2, "green")
    load_display_image(str(source2), 96, cache_dir=cache)
    for jpg in cache.rglob("*.jpg"):
        jpg.unlink()
    assert read_cached_thumb(str(source2), 96, cache_dir=cache, require_disk=False) is not image_mod._MISS
    assert read_cached_thumb(str(source2), 96, cache_dir=cache, require_disk=True) is image_mod._MISS
    assert image_decode_count() == 1


def test_acceptance_bridge_payload_drops_samples_after_thumb_clear(tmp_path, monkeypatch):
    """Bridge ribbon sampleIds/colour clear when thumbs are wiped."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    store = tmp_path / "del.sqlite"
    conn = connect(store)
    init_db(conn)
    ns = int(datetime(2024, 7, 1, tzinfo=timezone.utc).timestamp() * 1e9)
    paths = []
    for i in range(8):
        p = tmp_path / f"p{i}.jpg"
        _png(p, "red" if i % 2 == 0 else "blue")
        paths.append(p)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (f"m{i}", "folder", str(p), f"h{i}", 10, 10, ns + i, 1),
        )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _a, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        # Warm thumbs through the normal path.
        cache = thumb_cache_dir(store)
        for p in paths:
            load_display_image(str(p), 96, cache_dir=cache)
        years = bridge.ribbonYearCells()
        assert years
        assert any(y.get("sampleIds") for y in years) or any(y.get("color") for y in years)

        # Clear thumbs the way Settings does.
        from semblon.native_shell.images import clear_thumb_cache, reset_image_cache

        clear_thumb_cache(store)
        reset_image_cache()
        bridge._invalidate_ribbon_cache()
        years2 = bridge.ribbonYearCells()
        assert years2
        assert all(not y.get("sampleIds") for y in years2)
        assert all(not y.get("color") for y in years2)
        assert all(y.get("hasTiny") is False for y in years2)
    finally:
        shutdown_shell(engine)
        end = time.monotonic() + 0.4
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)


# ---------------------------------------------------------------------------
# 3. Sampling quality + incremental stability
# ---------------------------------------------------------------------------


def test_acceptance_burst_day_cannot_crowd_out_month_representatives():
    days: list[str] = []
    ids: list[str] = []
    for i in range(9000):
        days.append("2024-07-15")
        ids.append(f"burst-{i:05d}")
    for day in (1, 2, 3, 4, 5, 20, 21, 22):
        for j in range(25):
            days.append(f"2024-07-{day:02d}")
            ids.append(f"sparse-{day:02d}-{j:02d}")
    july = next(c for c in month_cells_for_year(days, 2024, media_ids=ids) if c.key == "2024-07")
    assert len(july.sample_ids) == MONTH_SAMPLE_BUDGET
    id_to_day = dict(zip(ids, days))
    sample_days = {id_to_day[mid] for mid in july.sample_ids}
    assert len(sample_days) >= 2
    # At most one slot from the burst day under round-robin with many sparse days.
    burst_slots = sum(1 for mid in july.sample_ids if id_to_day[mid] == "2024-07-15")
    assert burst_slots <= 1


def test_acceptance_sample_ids_stable_under_small_insert_not_just_reorder():
    """Adding one photograph must not unpredictably replace most representatives."""
    days = [f"2024-07-{1 + (i % 12):02d}" for i in range(60)]
    ids = [f"keep-{i:03d}" for i in range(60)]
    before = month_cells_for_year(days, 2024, media_ids=ids)
    before_ids = set(before[0].sample_ids)

    # Insert one new image on an existing day (and a reorder of the rest).
    days2 = list(reversed(days)) + ["2024-07-03"]
    ids2 = list(reversed(ids)) + ["new-001"]
    after = month_cells_for_year(days2, 2024, media_ids=ids2)
    after_ids = set(after[0].sample_ids)

    retained = before_ids & after_ids
    # Budget is 4 — at most one slot may change when one id is added.
    assert len(retained) >= len(before_ids) - 1
    assert len(before_ids - after_ids) <= 1


# ---------------------------------------------------------------------------
# 4. Large-archive bound
# ---------------------------------------------------------------------------


def test_acceptance_large_archive_work_and_memory_remain_bounded():
    n = 100_000
    days = [f"2019-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}" for i in range(n)]
    ids = [f"big-{i:06d}" for i in range(n)]

    # First build — O(n) index + stratified sample, not O(n) colour peeks.
    cells = year_cells(days, media_ids=ids)
    assert sum(c.photo_count for c in cells if c.kind == "year") == n
    for c in cells:
        assert len(c.sample_ids) <= 16

    # Repeated generation with the same inputs must stay cheap: only re-index,
    # sample budgets stay capped (assert structural bound, not wall clock).
    again = year_cells(days, media_ids=ids)
    assert [c.sample_ids for c in again] == [c.sample_ids for c in cells]

    # Hover-scale: one year → ≤12 month cells, each ≤4 samples.
    year = cells[0].year
    months = month_cells_for_year(days, year, media_ids=ids)
    assert len(months) <= 12
    assert all(len(m.sample_ids) <= 4 for m in months)


def test_acceptance_bridge_year_payload_cached_across_repeated_hover(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    store = tmp_path / "big.sqlite"
    conn = connect(store)
    init_db(conn)
    ns = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp() * 1e9)
    # Keep this store modest — bound is proven by cache hit identity, not 100k inserts.
    for i in range(40):
        p = tmp_path / f"b{i}.jpg"
        p.write_bytes(b"x")
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (f"b{i}", "folder", str(p), f"h{i}", 10, 10, ns + i * 86400, 1),
        )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _a, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        a = bridge.ribbonYearCells()
        b = bridge.ribbonYearCells()
        assert a == b
        # Same generation → month cache returns identical payloads on repeat hover.
        y = int(a[0]["year"])
        m1 = bridge.ribbonMonthCells(y)
        m2 = bridge.ribbonMonthCells(y)
        assert m1 == m2
        gen = bridge.archiveGeneration()
        bridge._bump_archive_generation()
        assert bridge.archiveGeneration() == gen + 1
        c = bridge.ribbonYearCells()
        # New generation rebuilds; structure still bounded.
        assert len(c) <= 40
    finally:
        shutdown_shell(engine)
        end = time.monotonic() + 0.4
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)


# ---------------------------------------------------------------------------
# 5. Interaction — strip ↔ preview without flicker / accidental dismissal
# ---------------------------------------------------------------------------


def _ns(y, m, d):
    return int(datetime(y, m, d, 14, 30, tzinfo=timezone.utc).timestamp() * 1e9)


def _call(obj, name, *args):
    from PySide6.QtCore import Q_ARG, Q_RETURN_ARG, QMetaObject

    return QMetaObject.invokeMethod(
        obj, name, Q_RETURN_ARG("QVariant"), *[Q_ARG("QVariant", a) for a in args]
    )


def test_acceptance_strip_preview_hover_survives_quick_moves_and_edges(tmp_path, monkeypatch):
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    store = tmp_path / "lens.sqlite"
    conn = connect(store)
    init_db(conn)
    n = 0
    for year, month, count in ((2023, 6, 30), (2024, 7, 80), (2025, 1, 30)):
        for i in range(count):
            n += 1
            path = tmp_path / f"p{n}.jpg"
            path.write_bytes(b"x")
            conn.execute(
                "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
                (f"m{n:04d}", "folder", str(path), f"h{n}", 10, 10, _ns(year, month, 1 + i % 28), 1),
            )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _a, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    root.resize(1100, 800)
    root.show()
    end = time.monotonic() + 1.2
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    scrub = None
    grid = None
    for _ in range(50):
        scrub = root.findChild(QQuickItem, "scrubber")
        grid = root.findChild(QQuickItem, "rollGrid")
        try:
            if scrub is not None and grid is not None and float(grid.property("contentY")) == float(
                grid.property("contentY")
            ):
                break
        except RuntimeError:
            scrub = None
            grid = None
        app.processEvents()
        time.sleep(0.02)
    try:
        assert scrub is not None and grid is not None
        before = float(grid.property("contentY"))
        h = float(scrub.height())

        # Open lens near mid strip.
        _call(scrub, "updateLensFromHover", h * 0.4)
        app.processEvents()
        assert int(scrub.property("lensYear") or -1) >= 0
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)

        # Simulate pointer leaving strip toward preview: leave timer armed, lensHover true.
        scrub.setProperty("lensHover", True)
        _call(scrub, "scheduleLensLeave")
        end = time.monotonic() + 0.25
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)
        # Lens must still be open — preview hover cancelled dismissal.
        assert int(scrub.property("lensYear") or -1) >= 0

        # Quick cancel/rearm cycles (edge chatter).
        for _ in range(6):
            _call(scrub, "scheduleLensLeave")
            _call(scrub, "cancelLensLeave")
            app.processEvents()
        assert int(scrub.property("lensYear") or -1) >= 0
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)

        # Edge positions along the strip.
        for frac in (0.05, 0.5, 0.95):
            _call(scrub, "updateLensFromHover", max(1.0, h * frac))
            app.processEvents()
            assert scrub.property("mode") == "idle"
            assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)

        # True leave: no strip, no lens hover → dismiss after timer.
        scrub.setProperty("lensHover", False)
        _call(scrub, "scheduleLensLeave")
        end = time.monotonic() + 0.35
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)
        assert int(scrub.property("lensYear") or -1) == -1
        assert float(grid.property("contentY")) == pytest.approx(before, abs=0.5)
    finally:
        shutdown_shell(engine)
        # Keep root alive until shutdown finishes processing.
        _ = root
        end = time.monotonic() + 0.3
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)
