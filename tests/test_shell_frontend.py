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
