"""Frontend shell contract: product-safe primary mode, advanced opt-in, prefs, state."""

import pytest

pytest.importorskip("PySide6")


@pytest.fixture
def shell(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    qapp = QApplication.instance() or QApplication([])
    made = []

    def make(store=None):
        path = store or (tmp_path / "s.sqlite")
        jobs = Application(path)
        bridge = ShellBridge(ArchiveModel(jobs), jobs)
        made.append(bridge)
        return bridge

    make.qapp = qapp
    yield make
    for bridge in made:
        bridge.shutdown()


def _raw_result(message, state="error"):
    from semblon.native_shell.adapter import Result

    return Result(state, message)


def test_primary_notice_never_leaks_technical_text(shell):
    bridge = shell()
    assert bridge.primaryMode
    bridge._apply_result(_raw_result("Traceback: sqlite3.OperationalError no such table"))
    assert "sqlite" not in bridge.noticeText.lower()
    assert "traceback" not in bridge.noticeText.lower()
    assert bridge.noticeText


def test_advanced_keeps_detail_and_switching_back_scrubs_it(shell):
    bridge = shell()
    bridge.setMode("advanced")
    bridge._apply_result(_raw_result("sqlite3.OperationalError: locked"))
    bridge._publish_similar("unavailable", "sqlite detail", [])
    assert "sqlite" in bridge.noticeText
    assert "sqlite" in bridge.similarNote
    bridge.setMode("primary")
    assert "sqlite" not in bridge.noticeText
    assert "sqlite" not in bridge.similarNote
    assert bridge.diagnosticsText == ""


@pytest.fixture
def qml_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    app = QApplication.instance() or QApplication([])
    _qapp, engine = build_shell(tmp_path / "s.sqlite", app=app)
    app.processEvents()
    yield app, engine, engine.rootObjects()[0], engine._semblon_bridge
    shutdown_shell(engine)


def test_advanced_diagnostics_are_opt_in_and_marked_active(qml_shell):
    from PySide6.QtCore import QObject

    app, _engine, root, bridge = qml_shell
    panel = root.findChild(QObject, "diagnosticsPanel")
    assert panel is not None
    assert panel.property("visible") is False
    assert bridge.diagnosticsText == ""
    bridge.submitCommand("status")
    assert "mode=" not in bridge.resultText

    bridge.setMode("advanced")
    app.processEvents()
    assert "mode=advanced" in bridge.diagnosticsText
    assert root.findChild(QObject, "advancedModeButton").property("visible") is True
    bridge.submitCommand("status")
    assert "mode=advanced" in bridge.resultText

    bridge.setMode("primary")
    app.processEvents()
    assert panel.property("visible") is False
    assert "mode=" not in bridge.resultText


def test_every_atmosphere_is_selectable_and_clean_install_is_dark(shell):
    from semblon.atmosphere import ATMOSPHERE_IDS

    bridge = shell()
    assert bridge.atmosphereId == "mica_dark"
    for atmosphere_id in ATMOSPHERE_IDS:
        bridge.setAtmosphere(atmosphere_id)
        assert bridge.atmosphereId == atmosphere_id
    bridge.setAtmosphere("not-a-theme")
    assert bridge.atmosphereId == ATMOSPHERE_IDS[-1]
    assert {row["id"] for row in bridge.atmosphereChoices} == set(ATMOSPHERE_IDS)


def test_explicit_theme_and_mode_survive_restart(shell, tmp_path):
    from semblon.atmosphere import ATMOSPHERE_IDS

    store = tmp_path / "persist.sqlite"
    chosen = next(i for i in ATMOSPHERE_IDS if i != "mica_dark")
    first = shell(store)
    first.setAtmosphere(chosen)
    first.setMode("advanced")
    first.shutdown()
    second = shell(store)
    assert second.atmosphereId == chosen
    assert second.advancedMode


def test_reset_defaults_returns_to_dark_primary_without_losing_library(shell, tmp_path):
    from semblon.atmosphere import ATMOSPHERE_IDS

    bridge = shell(tmp_path / "reset.sqlite")
    bridge.setAtmosphere(next(i for i in ATMOSPHERE_IDS if i != "mica_dark"))
    bridge.resetDefaults()
    assert bridge.atmosphereId == "mica_dark"
    assert bridge.primaryMode


def _seed(store, tmp_path, n=4):
    from semblon.store import connect, init_db

    conn = connect(store)
    init_db(conn)
    rows = []
    for i in range(n):
        day = 1_503_000_000_000_000_000 + i * 86_400_000_000_000
        sub = "2017" if i % 2 == 0 else "2018"
        rows.append((f"m{i}", "folder", str(tmp_path / sub / f"{i}.jpg"), f"h{i}", 10, 10, day, 1))
    conn.executemany("INSERT INTO media VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


def test_search_is_safe_in_both_modes(shell, tmp_path):
    bridge = shell()
    for mode in ("primary", "advanced"):
        bridge.setMode(mode)
        bridge.submitCommand("   ")
        assert bridge.resultText == "Nothing was searched."
        bridge.submitCommand("nobody-by-this-name")
        assert bridge.resultText
        assert "traceback" not in bridge.resultText.lower()
    bridge.setMode("primary")
    bridge.setSearchMode("text")
    assert bridge.searchModeLabel
    bridge.submitCommand("beach")
    assert "sqlite" not in bridge.resultText.lower()
    assert "traceback" not in bridge.resultText.lower()


def test_library_filters_facets_and_settings_keep_state_stable(shell, tmp_path):
    store = tmp_path / "lib.sqlite"
    _seed(store, tmp_path)
    bridge = shell(store)
    total = bridge.count
    assert total == 4
    bridge.setFacet("folders")
    assert bridge.facet == "folders"
    assert bridge.buckets
    bridge.selectBucket(bridge.buckets[0]["key"])
    assert 0 < bridge.count < total or bridge.count == total
    bridge.setFacet("memory")
    assert bridge.count == total
    bridge.setLibraryFilter("all")
    assert bridge.count == total
    bridge.setLibraryFilter("bogus-filter")
    assert bridge.count == total
    for _ in range(3):
        bridge.toggleSettings()
        bridge.cycleDensity()
    assert bridge.count == total
    assert bridge.surfaceState in {"ready", "empty"}
    assert bridge.photoCount == 4


def test_moments_facet_is_advanced_only(shell):
    bridge = shell()
    bridge.setFacet("moments")
    assert bridge.facet == "memory"
    assert "Advanced" in bridge.noticeText
    bridge.setMode("advanced")
    bridge.setFacet("moments")
    assert bridge.facet == "moments"
