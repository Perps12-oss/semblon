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
    from semblon.application import Application
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
    app_facade = Application(store)
    session = app_facade.archive
    calls: list[tuple[int, int]] = []
    real = session.window

    def wrapped(offset, limit):
        calls.append((offset, limit))
        return real(offset, limit)

    session.window = wrapped  # type: ignore[method-assign]
    model = ArchiveModel(app_facade)
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


def test_shell_ask_and_similar_use_application_media_id(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
    from semblon.store import connect, init_db

    asked = []
    found = []

    def fake_query(self, media_id, rect=None, **kwargs):
        asked.append((media_id, rect, kwargs))
        return {
            "status": "NO_RESULT",
            "lines": ["Nothing was searched."],
            "reason": "Nothing was searched.",
            "region": {"x": 0, "y": 0, "w": 8, "h": 8},
            "media_id": media_id,
        }

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        found.append((media_id, x, y, w, h))
        return {"region": {}, "similar": {"status": "NO_RESULT", "items": []}, "persons": 0}

    monkeypatch.setattr(Application, "query_media", fake_query)
    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)

    photo = tmp_path / "a.png"
    photo.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    try:
        init_db(conn)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            ("m1", "folder", str(photo), "h", 40, 20, 3, 1),
        )
        conn.commit()
    finally:
        conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    assert root.findChild(QObject, "lensLine").property("text") == "Time"
    bridge.openFocus("m1")
    bridge.askPhoto()
    assert asked == [("m1", None, {})]
    assert "Nothing was searched" in bridge.resultText
    bridge.findSimilar()
    assert found == []
    bridge.setRegion(0.25, 0.5, 0.5, 0.25)
    bridge.findSimilar()
    assert found == [("m1", 10, 10, 20, 5)]
    assert root.findChild(QObject, "askPhoto") is not None
    assert root.findChild(QObject, "resultText") is not None
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
    assert "pyside6" in lowered
    assert "forward" in lowered
    assert "not the product home" not in lowered
    assert "native production shell" not in lowered


def test_bridge_archive_media_ask_similar_and_ingest_use_application(tmp_path, monkeypatch):
    """Real Application methods. No QML. No monkeypatch of query or archive reads."""
    pytest.importorskip("PySide6")
    cv2 = pytest.importorskip("cv2")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import numpy as np
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel
    from semblon.store import connect, init_db

    photo = tmp_path / "a.png"
    assert cv2.imwrite(str(photo), np.zeros((20, 40, 3), np.uint8))
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h", 40, 20, 3, 1),
    )
    conn.commit()
    conn.close()

    seen: dict = {}

    def fake_process(folder, **kwargs):
        seen["folder"] = Path(folder)
        seen["kwargs"] = kwargs
        return {"run_id": "r-bridge", "out": None}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)

    qapp = QApplication.instance() or QApplication([])
    del qapp
    jobs = Application(store)
    model = ArchiveModel(jobs)
    bridge = ShellBridge(model, jobs)
    assert model.rowCount() == 1
    assert bridge.path_for("m1") == str(photo)
    assert jobs.media_path("m1") == str(photo)
    bridge.openFocus("m1")
    bridge.askPhoto()
    assert bridge.resultText
    assert "searched" in bridge.resultText.lower() or "Nothing" in bridge.resultText
    bridge.setRegion(0.1, 0.1, 0.4, 0.4)
    bridge.findSimilar()
    assert bridge.resultText
    import time

    bridge._start_ingest(tmp_path)
    deadline = time.monotonic() + 2
    while "kwargs" not in seen and time.monotonic() < deadline:
        time.sleep(0.01)
    assert seen["kwargs"]["open_review"] is False
    host = (
        Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "host.py"
    ).read_text(encoding="utf-8")
    assert "ArchiveSession(" not in host
    assert "Application(" in host
    assert "sqlite" not in host.lower()

