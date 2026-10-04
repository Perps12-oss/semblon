"""Native archive shell — Application client. Optional PySide6."""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

from semblon.native_shell import run_native_shell


def test_native_shell_package_has_no_identity_or_ingest_imports():
    root = Path(__file__).resolve().parents[1] / "semblon" / "native_shell"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "from semblon.process import process_folder" not in text
        assert "from semblon.ingest" not in text
        assert "insightface" not in text.lower()
        assert "FaceAnalysis" not in text
    for name in ("archive_session.py",):
        text = (root.parents[0] / name).read_text(encoding="utf-8")
        assert "person_id" not in text
    for name in ("bridge.py", "host.py", "model.py", "images.py", "run.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "person_id" not in text


def test_shell_command_loads_qml_archive_not_the_widget_columns():
    from semblon.native_shell import run as run_mod

    src = inspect.getsource(run_mod.run_native_shell)
    assert "build_shell" in src
    assert "ShellWindow" not in src
    host_text = (
        Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "host.py"
    ).read_text(encoding="utf-8")
    assert "Shell.qml" in host_text
    assert "submit_ingest" not in host_text
    bridge = Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "bridge.py"
    text = bridge.read_text(encoding="utf-8")
    assert "submit_ingest" in text
    assert "open_review=False" in text
    qml = (Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "qml" / "Shell.qml").read_text(
        encoding="utf-8"
    )
    assert "Add a folder" in qml
    assert 'objectName: "lensLine"' in qml
    assert "GridView" in qml
    assert "QListWidget" not in qml


def test_archive_model_fetches_a_window_not_the_library(tmp_path):
    pytest.importorskip("PySide6")
    from semblon.archive_session import ArchiveSession
    from semblon.native_shell.model import ArchiveModel
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    try:
        init_db(conn)
        conn.executemany(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            [
                (f"m{i:04d}", "folder", f"{i}.jpg", f"h{i}", 10, 10, i, 1)
                for i in range(500)
            ],
        )
        conn.commit()
    finally:
        conn.close()
    session = ArchiveSession(store)
    calls: list[tuple[int, int]] = []
    real = session.window

    def wrapped(offset, limit):
        calls.append((offset, limit))
        return real(offset, limit)

    session.window = wrapped  # type: ignore[method-assign]
    model = ArchiveModel(session)
    model.reload()
    assert model.rowCount() == 500
    assert calls == []
    index = model.index(0, 0)
    assert model.data(index, 0x0100 + 1)
    assert calls
    assert calls[0][1] <= 120
    calls.clear()
    assert model.data(model.index(400, 0), 0x0100 + 1)
    assert calls
    assert calls[0][1] <= 120
    assert sum(limit for _offset, limit in calls) < 500


def test_shell_qml_shows_time_and_empty_archive(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(tmp_path / "empty.sqlite", app=app)
    root = engine.rootObjects()[0]
    lens = root.findChild(QObject, "lensLine")
    empty = root.findChild(QObject, "emptyState")
    field = root.findChild(QObject, "fieldGrid")
    assert lens is not None and lens.property("text") == "Time"
    assert empty is not None and empty.property("visible") is True
    assert field is not None and field.property("visible") is False
    engine.deleteLater()


def test_shell_focus_roundtrip_follows_the_time_lens(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell
    from semblon.store import connect, init_db

    photo = tmp_path / "new.png"
    older = tmp_path / "old.png"
    fresh = QImage(64, 48, QImage.Format.Format_RGB32)
    fresh.fill(Qt.GlobalColor.darkCyan)
    assert fresh.save(str(photo))
    previous = QImage(64, 48, QImage.Format.Format_RGB32)
    previous.fill(Qt.GlobalColor.darkGray)
    assert previous.save(str(older))
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    try:
        init_db(conn)
        conn.executemany(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            [
                ("new", "folder", str(photo), "hnew", 64, 48, 20, 8),
                ("old", "folder", str(older), "hold", 64, 48, 10, 8),
                ("clip", "video", str(tmp_path / "missing.mp4"), "hvid", 320, 180, 5, 8),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    app.processEvents()
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    assert bridge.count == 3
    assert root.findChild(QObject, "emptyState").property("visible") is False
    assert root.findChild(QObject, "fieldGrid").property("visible") is True
    assert root.findChild(QObject, "lensLine").property("text") == "Time"
    shot = tmp_path / "field.png"
    root.grabWindow().save(str(shot))
    bridge.openFocus("new")
    app.processEvents()
    assert bridge.focusId == "new"
    assert root.findChild(QObject, "focusLayer").property("visible") is True
    bridge.focusNext()
    assert bridge.focusId == "old"
    bridge.focusPrev()
    assert bridge.focusId == "new"
    bridge.escape()
    app.processEvents()
    assert bridge.focusId == ""
    assert root.findChild(QObject, "focusLayer").property("visible") is False
    assert root.findChild(QObject, "lensLine").property("text") == "Time"
    bridge.openFocus("clip")
    app.processEvents()
    assert bridge.focusKind == "video"
    assert bridge.focusUrl == ""
    assert root.findChild(QObject, "videoMissing").property("visible") is True
    engine.deleteLater()


def test_run_native_shell_exits_when_pyside_missing(tmp_path, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "PySide6" or name.startswith("PySide6."):
            raise ImportError("test: no pyside")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(SystemExit) as ei:
        run_native_shell(store=tmp_path / "s.sqlite")
    assert ei.value.code == 2


def test_cli_registers_shell_command():
    from semblon.cli import main
    import io
    from contextlib import redirect_stderr, redirect_stdout

    buf = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        try:
            main(["shell", "--help"])
        except SystemExit as e:
            assert e.code == 0
    text = buf.getvalue() + err.getvalue()
    lowered = text.lower()
    assert "not the product home" in lowered
    assert "native production shell" not in lowered
