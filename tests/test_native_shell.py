"""Native archive shell â€” Application client. Optional PySide6."""

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
    for name in ("host.py", "model.py", "images.py", "run.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "person_id" not in text
    # People reads the board member key to open that person's days.
    # The shell must not stamp the faces column or load the identity engine.
    bridge = (root / "bridge.py").read_text(encoding="utf-8")
    assert "faces.person_id" not in bridge
    assert "UPDATE faces" not in bridge
    assert "INSERT INTO faces" not in bridge
    assert "from semblon.identify" not in bridge
    assert "from semblon.cluster" not in bridge
    assert "from semblon.ingest" not in bridge


def test_shell_command_loads_qml_archive_not_the_widget_columns():
    from semblon.native_shell import run as run_mod

    src = inspect.getsource(run_mod.run_native_shell)
    assert "build_shell" in src
    assert "ShellWindow" not in src
    host_text = (
        Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "host.py"
    ).read_text(encoding="utf-8")
    assert "Table.qml" in host_text
    assert "submit_ingest" not in host_text
    bridge = Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "bridge.py"
    text = bridge.read_text(encoding="utf-8")
    assert "submit_ingest" in text
    assert "open_review=False" in text
    qml_dir = Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "qml"
    table = (qml_dir / "Table.qml").read_text(encoding="utf-8")
    roll = (qml_dir / "Roll.qml").read_text(encoding="utf-8")
    assert "Add a folder" in table + roll
    assert "Flickable" in roll and "ListView" not in roll
    assert "QListWidget" not in table + roll
    assert not (qml_dir / "Shell.qml").exists()
    assert not (qml_dir / "HomeLaunchpad.qml").exists()


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

    from semblon.native_shell.host import build_shell, shutdown_shell

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(tmp_path / "empty.sqlite", app=app)
    root = engine.rootObjects()[0]
    empty = root.findChild(QObject, "emptyState")
    roll = root.findChild(QObject, "rollGrid")
    assert empty is not None and empty.property("visible") is True
    assert roll is not None
    shutdown_shell(engine)


def test_shell_focus_roundtrip_follows_the_time_lens(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
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
    assert bridge.count == 2
    assert root.findChild(QObject, "emptyState").property("visible") is False
    shot = tmp_path / "field.png"
    root.grabWindow().save(str(shot))
    def settle():
        import time

        for _ in range(20):
            app.processEvents()
            time.sleep(0.03)

    bridge.openFocus("new")
    settle()
    assert bridge.focusId == "new"
    assert root.findChild(QObject, "viewer").property("visible") is True
    bridge.focusNext()
    assert bridge.focusId == "old"
    bridge.focusPrev()
    assert bridge.focusId == "new"
    bridge.escape()
    settle()
    assert bridge.focusId == ""
    assert root.findChild(QObject, "viewer").property("visible") is False
    bridge.openFocus("clip")
    app.processEvents()
    assert bridge.focusId == ""
    assert bridge.focusKind == ""
    assert bridge.focusUrl == ""
    shutdown_shell(engine)


def test_open_focus_in_context_scopes_day_when_mtime_exists(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    photo = tmp_path / "shot.png"
    image = QImage(32, 32, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkBlue)
    assert image.save(str(photo))
    # 2024-06-15 12:00:00 UTC in ns
    mtime_ns = 1_718_452_800_000_000_000
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    try:
        init_db(conn)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            ("m1", "folder", str(photo), "h1", 32, 32, mtime_ns, 1),
        )
        conn.commit()
    finally:
        conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    app.processEvents()
    bridge = engine._semblon_bridge
    bridge.openFocusInContext("m1")
    app.processEvents()
    assert bridge.focusId == "m1"
    assert bridge.scopeKind == "day"
    assert bridge.scopeLabel == "2024-06-15"
    assert bridge.focusFileMissing is False
    shutdown_shell(engine)


def test_open_focus_reports_missing_original(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    missing = tmp_path / "gone.png"
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    try:
        init_db(conn)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            ("m1", "folder", str(missing), "h1", 32, 32, 1, 1),
        )
        conn.commit()
    finally:
        conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    app.processEvents()
    bridge = engine._semblon_bridge
    bridge.openFocus("m1")
    app.processEvents()
    assert bridge.focusId == "m1"
    assert bridge.focusFileMissing is True
    assert "missing" in bridge.resultText.lower()
    shutdown_shell(engine)


def test_open_focus_in_context_without_day_stays_honest(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    photo = tmp_path / "nodate.png"
    image = QImage(16, 16, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.darkGreen)
    assert image.save(str(photo))
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    try:
        init_db(conn)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            ("m1", "folder", str(photo), "h1", 16, 16, None, 1),
        )
        conn.commit()
    finally:
        conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    app.processEvents()
    bridge = engine._semblon_bridge
    bridge.openFocusInContext("m1")
    app.processEvents()
    assert bridge.focusId == "m1"
    assert bridge.scopeKind == ""
    assert "no date" in bridge.resultText.lower()
    shutdown_shell(engine)


def test_shell_ask_and_similar_use_application_media_id(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
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
    bridge.openFocus("m1")
    bridge.askPhoto()
    assert asked == [("m1", None, {})]
    assert "Nothing was searched" in bridge.resultText
    bridge.findSimilar()
    assert found == []
    assert bridge.similarCount == 0
    bridge.setRegion(0.25, 0.5, 0.5, 0.25)
    bridge.findSimilar()
    assert found == [("m1", 10, 10, 20, 5)]
    assert bridge.similarState == "empty"
    assert bridge.similarCount == 0
    assert "m1" not in bridge.resultText
    assert root.findChild(QObject, "askPhoto") is not None
    assert root.findChild(QObject, "findSimilar") is None
    assert root.findChild(QObject, "similarStrip") is not None
    shutdown_shell(engine)


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
    assert bridge.similarState in {"empty", "unavailable", "ready"}
    assert "m1" not in bridge.similarNote
    import time

    bridge._start_ingest(tmp_path)
    deadline = time.monotonic() + 2
    while "kwargs" not in seen and time.monotonic() < deadline:
        time.sleep(0.01)
    assert seen["kwargs"]["open_review"] is False
    from semblon.observers import resolve_product_observers

    assert seen["kwargs"]["observers"] == resolve_product_observers()
    assert "face" in seen["kwargs"]["observers"].split(",")
    assert "color" in seen["kwargs"]["observers"].split(",")
    host = (
        Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "host.py"
    ).read_text(encoding="utf-8")
    assert "ArchiveSession(" not in host
    assert "Application(" in host
    assert "sqlite" not in host.lower()



def test_viewer_keeps_the_strip_and_a_primary_similar_action():
    """Drawing a region still fills the strip, and Find similar is a primary action."""
    qml_root = Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "qml"
    viewer = (qml_root / "Viewer.qml").read_text(encoding="utf-8")
    table = (qml_root / "Table.qml").read_text(encoding="utf-8")
    roll = (qml_root / "Roll.qml").read_text(encoding="utf-8")
    assert "shell.findSimilar()" in viewer
    assert "shell.findSimilarWhole()" in viewer
    assert "shell.resumeJob()" in roll
    assert 'objectName: "emptyResume"' in roll
    for name in (
        "similarAction", "sameFaceDoor", "duplicatesDoor", "installSuggestedModel",
        "screenQueryAction", "screenQueryModeAction", "screenQueryProgress", "similarStrip",
    ):
        assert f'objectName: "{name}"' in viewer, name
    assert 'label: "Find similar"' in viewer
    assert "shell.installSuggestedModel()" in viewer
    assert "shell.startScreenQuery()" in viewer
    assert 'sequence: "Ctrl+Shift+S"' in viewer
    assert "shell.toggleScreenQueryMode()" in viewer
    assert 'objectName: "findSimilar"' not in viewer
    assert "shell.openFocus(mediaId)" in viewer
    assert 'objectName: "primaryModeButton"' in (qml_root / "SettingsBody.qml").read_text(encoding="utf-8")
    host = (
        Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "host.py"
    ).read_text(encoding="utf-8")
    assert 'setContextProperty("similarModel"' in host
    assert "similarModel" in viewer


def test_drawn_region_strip_replaces_and_clears(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    calls = []

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        calls.append((media_id, x, y, w, h))
        if len(calls) == 1:
            return {
                "region": {},
                "similar": {
                    "status": "SUCCESS",
                    "items": [
                        {"media_id": "b", "score": 0.9, "provider": "hidden", "item_id": "i1"},
                        {"media_id": "c", "score": 0.4, "kind": "object"},
                    ],
                },
                "persons": 0,
            }
        return {"region": {}, "similar": {"status": "NO_RESULT", "items": []}, "persons": 0}

    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)
    photo = tmp_path / "a.png"
    other = tmp_path / "b.png"
    photo.write_bytes(b"not-decoded")
    other.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    try:
        init_db(conn)
        conn.executemany(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            [
                ("a", "folder", str(photo), "ha", 40, 20, 3, 1),
                ("b", "folder", str(other), "hb", 40, 20, 2, 1),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    bridge.openFocus("a")
    bridge.clearDrawnQuery()
    assert calls == []
    assert bridge.similarState == "idle"
    bridge.setRegion(0, 0, 0, 0)
    bridge.findSimilar()
    assert calls == []
    assert bridge.similarCount == 0
    bridge.setRegion(0.25, 0.5, 0.5, 0.25)
    bridge.findSimilar()
    app.processEvents()
    assert calls == [("a", 10, 10, 20, 5)]
    assert bridge.similarState == "ready"
    assert bridge.similarCount == 2
    assert bridge.similarId(0) == "b"
    assert bridge.similarId(1) == "c"
    assert bridge.thumbFor("b") == "image://archive/t/b"
    assert "hidden" not in bridge.similarNote
    assert "i1" not in bridge.resultText
    import time

    for _ in range(20):
        app.processEvents()
        time.sleep(0.03)
    strip = root.findChild(QObject, "similarStrip")
    assert strip is not None and strip.property("visible") is True
    assert float(strip.property("width")) >= 72
    bridge.openFocus("b")
    assert bridge.focusId == "b"
    assert bridge.similarState == "idle"
    assert bridge.similarCount == 0
    bridge.setRegion(0.1, 0.1, 0.2, 0.2)
    bridge.findSimilar()
    assert bridge.similarState == "empty"
    assert bridge.similarCount == 0
    assert "colour" in bridge.similarNote.lower()
    bridge.setRegion(0.1, 0.1, 0.2, 0.2)
    bridge.findSimilar()
    bridge.focusNext()
    assert bridge.similarState == "idle"
    bridge.setRegion(0.1, 0.1, 0.2, 0.2)
    bridge.findSimilar()
    bridge.escape()
    assert bridge.focusId == ""
    assert bridge.similarState == "idle"
    shutdown_shell(engine)


def _wait_idle(jobs, timeout=90.0):
    import time

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    deadline = time.monotonic() + timeout
    while jobs.busy and time.monotonic() < deadline:
        if app is not None:
            app.processEvents()
        time.sleep(0.05)
    if app is not None:
        app.processEvents()
    assert not jobs.busy


def _appearance_rows(store):
    from semblon.observers import APPEARANCE_PACK
    from semblon.store import connect

    conn = connect(store)
    try:
        return conn.execute(
            """SELECT o.media_id, e.pack_id
               FROM embeddings e
               JOIN observation_items i ON i.item_id = e.item_id
               JOIN observations o ON o.observation_id = i.observation_id
               WHERE e.modality='appearance' AND e.pack_id=?""",
            (APPEARANCE_PACK,),
        ).fetchall()
    finally:
        conn.close()


def test_bridge_ingest_finished_is_marshaled_to_bridge_thread(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    import threading
    import time

    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    qapp = QApplication.instance() or QApplication([])
    jobs = Application(tmp_path / "fresh.sqlite")
    bridge = ShellBridge(ArchiveModel(jobs), jobs)
    callbacks: dict[str, object] = {}

    def fake_submit_ingest(folder, **kwargs):
        callbacks["on_done"] = kwargs["on_done"]
        return object()

    monkeypatch.setattr(jobs, "submit_ingest", fake_submit_ingest)
    seen: list[QThread] = []
    done = threading.Event()
    worker_thread: list[QThread] = []

    def record_emit() -> None:
        seen.append(QThread.currentThread())
        done.set()

    bridge.ingestFinished.connect(record_emit)
    bridge._start_ingest(tmp_path)
    assert "on_done" in callbacks

    def run_done() -> None:
        worker_thread.append(QThread.currentThread())
        callbacks["on_done"](None)

    thread = threading.Thread(target=run_done)
    thread.start()
    thread.join()

    deadline = time.monotonic() + 5.0
    while not done.is_set() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert done.is_set()
    assert seen == [bridge.thread()]
    assert worker_thread and worker_thread[0] != seen[0]


def test_shell_add_folder_indexes_appearance_and_draw_finds_it(tmp_path, monkeypatch):
    """Fresh native Add Folder writes appearance/rgb8@1. Draw searches that space."""
    pytest.importorskip("PySide6")
    cv2 = pytest.importorskip("cv2")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import sys
    from types import SimpleNamespace

    import numpy as np
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel
    from semblon.observers import APPEARANCE_PACK

    monkeypatch.setitem(sys.modules, "insightface", SimpleNamespace(__version__="0.test"))
    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(
            __version__="0.test",
            get_available_providers=lambda: ["CPUExecutionProvider"],
        ),
    )
    monkeypatch.setattr("semblon.ingest.load_app", lambda *_args, **_kwargs: object())
    monkeypatch.setattr("semblon.ingest.embed_bgr", lambda *_args, **_kwargs: [])

    folder = tmp_path / "photos"
    folder.mkdir()
    red = np.zeros((80, 120, 3), np.uint8)
    red[:, :] = (20, 20, 220)
    red_b = red.copy()
    red_b[0, 0] = (20, 20, 221)
    blue = np.zeros((80, 120, 3), np.uint8)
    blue[:, :] = (220, 20, 20)
    assert cv2.imwrite(str(folder / "red-a.png"), red)
    assert cv2.imwrite(str(folder / "red-b.png"), red_b)
    assert cv2.imwrite(str(folder / "blue.png"), blue)
    (folder / "broken.jpg").write_bytes(b"not-a-jpeg")
    (folder / "notes.txt").write_text("not media", encoding="utf-8")

    store = tmp_path / "fresh.sqlite"
    assert not store.exists()
    assert not (tmp_path / ".semblon-index.npz").exists()
    qapp = QApplication.instance() or QApplication([])
    del qapp
    jobs = Application(store)
    finished = []
    bridge = ShellBridge(ArchiveModel(jobs), jobs)
    bridge.ingestFinished.connect(lambda: finished.append(True))

    empty = tmp_path / "empty"
    empty.mkdir()
    bridge._start_ingest(empty)
    _wait_idle(jobs)
    assert _appearance_rows(store) == []

    bridge._start_ingest(folder)
    _wait_idle(jobs, timeout=120)
    assert finished
    rows = _appearance_rows(store)
    assert len(rows) >= 2
    assert all(row[1] == APPEARANCE_PACK for row in rows)
    assert not (tmp_path / ".semblon-index.npz").exists()

    from semblon.store import connect

    conn = connect(store)
    try:
        observations = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        red_id = conn.execute(
            "SELECT media_id FROM media WHERE path LIKE '%red-a.png'"
        ).fetchone()[0]
        other_red = conn.execute(
            "SELECT media_id FROM media WHERE path LIKE '%red-b.png'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert observations >= 2
    indexed = {row[0] for row in rows}
    assert red_id in indexed and other_red in indexed

    bridge.openFocus(red_id)
    bridge.setRegion(0.1, 0.1, 0.5, 0.5)
    bridge.findSimilar()
    assert bridge.similarState == "ready"
    found = {bridge.similarId(i) for i in range(bridge.similarCount)}
    assert other_red in found
    bridge.openFocus(other_red)
    assert bridge.focusId == other_red

    before = len(_appearance_rows(store))
    bridge._start_ingest(folder)
    _wait_idle(jobs, timeout=120)
    assert len(_appearance_rows(store)) == before

    bridge.openFocus(red_id)
    bridge.setRegion(0, 0, 0, 0)
    bridge.findSimilar()
    assert bridge.similarState in {"empty", "unavailable"}
    assert bridge.similarCount == 0
    bridge.pauseJob()
    bridge.cancelJob()
    assert not jobs.busy


def test_shell_resume_unpauses_and_resubmits_cancelled_folder(tmp_path, monkeypatch):
    """Resume uses the existing job door. No second engine."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import threading
    import time
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    started = threading.Event()
    release = threading.Event()
    seen = []

    def fake_process(folder, **kwargs):
        seen.append(dict(kwargs))
        started.set()
        while not release.is_set():
            if kwargs.get("cancel") and kwargs["cancel"]():
                from semblon.process import ProcessCancelled
                raise ProcessCancelled("cancelled", run_id="r")
            time.sleep(0.02)
        return {"run_id": "r", "out": None}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    qapp = QApplication.instance() or QApplication([])
    jobs = Application(tmp_path / "s.sqlite")
    bridge = ShellBridge(ArchiveModel(jobs), jobs)
    folder = tmp_path / "photos"
    folder.mkdir()
    bridge._start_ingest(folder)
    assert started.wait(2)
    bridge.pauseJob()
    assert jobs.paused
    assert bridge.jobState == "paused"
    bridge.resumeJob()
    assert not jobs.paused
    assert bridge.jobState == "running"
    bridge.cancelJob()
    deadline = time.monotonic() + 3
    while jobs.busy and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    qapp.processEvents()
    assert not jobs.busy
    assert bridge.canResume
    seen.clear()
    started.clear()
    release.set()
    bridge.resumeJob()
    assert started.wait(2)
    assert seen[-1]["resume"] is True
    assert seen[-1]["open_review"] is False
    release.set()
    deadline = time.monotonic() + 3
    while jobs.busy and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not jobs.busy


def test_people_desk_uses_review_and_returns_to_the_same_session(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    calls = []

    def fake_board(self, run_id=None):
        return {
            "items": [
                {
                    "cluster_id": "c1",
                    "face_count": 2,
                    "named": False,
                    "person_names": [],
                    "members": [{"media_id": "m1", "face_id": "f1"}],
                },
                {
                    "cluster_id": "c2",
                    "face_count": 1,
                    "named": True,
                    "person_names": ["Ada"],
                    "members": [{"media_id": "m2", "face_id": "f2"}],
                },
            ]
        }

    def record(name):
        def _inner(*args, **kwargs):
            calls.append(name)
            return {"display_name": "Ada"}
        return _inner

    monkeypatch.setattr(Application, "board", fake_board)
    monkeypatch.setattr("semblon.review_board.name_cluster", record("name"))
    monkeypatch.setattr("semblon.review_board.merge_clusters", record("merge"))
    monkeypatch.setattr("semblon.review_board.split_cluster", record("split"))
    monkeypatch.setattr("semblon.review_board.ignore_subject", record("ignore"))
    monkeypatch.setattr("semblon.review_board.note_subject", record("note"))
    monkeypatch.setattr("semblon.review_board.rule_out_subject", record("rule_out"))
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")

    photo = tmp_path / "a.png"
    photo.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h", 40, 20, 3, 1),
    )
    conn.commit()
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    assert root.findChild(QObject, "peopleButton") is not None
    import time

    bridge.openPeople()
    for _ in range(20):
        app.processEvents()
        time.sleep(0.03)
    desk = root.findChild(QObject, "peopleDesk")
    assert desk.property("visible") is True
    assert bridge.peopleEmpty is False
    assert bridge.people_model.rowCount() == 2
    bridge.selectGroup("missing")
    assert bridge.peopleNote == "That group is no longer here."
    bridge.selectGroup("c1")
    assert bridge.evidenceId == "m1"
    bridge.openEvidence("m1")
    assert bridge.focusId == "m1"
    bridge.escape()
    app.processEvents()
    assert bridge.focusId == ""
    assert bridge.peopleOpen is True
    assert bridge.decide("name", "c1", "") == "A name or note is required."
    assert bridge.decide("name", "c1", "Ada") == "Saved name: Ada."
    assert bridge.decide("merge", "c1", "c2").startswith("Merged")
    assert bridge.decide("split", "c1", "f1").startswith("Split")
    assert bridge.decide("ignore", "c1", "") == "Left this group unknown."
    assert bridge.decide("note", "c1", "keep") == "Saved your note."
    assert bridge.decide("rule_out", "c1", "") == "Marked this as not the same person."
    assert calls == ["name", "merge", "split", "ignore", "note", "rule_out"]
    bridge.closePeople()
    assert bridge.peopleOpen is False
    qml = Path(__file__).resolve().parents[1].joinpath("semblon/native_shell/qml/People.qml").read_text(encoding="utf-8")
    assert "review.html" not in qml
    assert 'text: "Play"' not in qml
    shutdown_shell(engine)


def test_people_split_uses_visual_face_selection_and_merge_target(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    calls = []

    def fake_board(self, run_id=None):
        return {
            "items": [
                {
                    "cluster_id": "c1",
                    "face_count": 3,
                    "named": False,
                    "person_names": [],
                    "members": [
                        {"media_id": "m1", "face_id": "f1", "path": "/tmp/a.png", "bbox": (1, 2, 30, 30)},
                        {"media_id": "m1", "face_id": "f2", "path": "/tmp/a.png", "bbox": (40, 2, 30, 30)},
                        {"media_id": "m2", "face_id": "f3", "path": "/tmp/b.png", "bbox": (10, 8, 24, 24)},
                    ],
                },
                {
                    "cluster_id": "c2",
                    "face_count": 1,
                    "named": True,
                    "person_names": ["Bea"],
                    "members": [{"media_id": "m3", "face_id": "g1", "path": "/tmp/c.png", "bbox": (3, 3, 16, 16)}],
                },
            ]
        }

    def record(name):
        def _inner(*args, **kwargs):
            calls.append((name, args, kwargs))
            return {"display_name": "Ada"}

        return _inner

    monkeypatch.setattr(Application, "board", fake_board)
    monkeypatch.setattr("semblon.review_board.merge_clusters", record("merge"))
    monkeypatch.setattr("semblon.review_board.split_cluster", record("split"))
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")

    photo = tmp_path / "a.png"
    photo.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h", 40, 20, 3, 1),
    )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    assert root.findChild(QObject, "splitFaceGrid") is not None
    assert root.findChild(QObject, "mergeTargetFlow") is not None
    bridge.openPeople()
    bridge.selectGroup("c1")
    crop = bridge.face_crop_spec("f1")
    assert crop is not None
    assert crop["bbox"] == (1, 2, 29, 28)
    candidates = bridge.mergeCandidates
    assert candidates and candidates[0]["faceCount"] == 1
    assert bridge.selectedTitle == "Candidate group"
    assert bridge.selectedBandLabel.startswith("Needs review")
    assert bridge.selectedCount == 3
    assert len(bridge.selectedMembers) == 3
    assert bridge.faceThumb("f1") == "image://face/f1"
    bridge.toggleSplitFace("f1")
    bridge.toggleSplitFace("f2")
    assert bridge.isSplitFaceSelected("f1")
    assert bridge.isSplitFaceSelected("f2")
    assert bridge.canSplitSelected is True
    assert bridge.splitSelectedFaces().startswith("Split")
    bridge.selectGroup("c1")
    bridge.selectMergeTarget("c2")
    assert bridge.mergeTargetTitle == "Bea"
    assert bridge.canMergeSelected is True
    assert bridge.mergeSelectedGroup().startswith("Merged")
    assert [name for name, _args, _kwargs in calls] == ["split", "merge"]
    from PySide6.QtCore import QMetaObject

    assert QMetaObject.invokeMethod(bridge, "findSimilarFaces") is True
    assert bridge.searchDoorLabel == "Same face"
    shutdown_shell(engine)


def test_people_desk_hides_video_only_tracks_from_qt_shell(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    def fake_board(self, run_id=None):
        return {
            "items": [
                {
                    "kind": "track",
                    "track_id": "t1",
                    "face_count": 2,
                    "named": False,
                    "person_names": [],
                    "members": [
                        {"media_id": "mv1", "face_id": "fv1", "source_type": "video", "path": "/tmp/a.mp4", "bbox": (0, 0, 10, 10)},
                        {"media_id": "mv1", "face_id": "fv2", "source_type": "video", "path": "/tmp/a.mp4", "bbox": (12, 0, 10, 10)},
                    ],
                },
                {
                    "kind": "cluster",
                    "cluster_id": "c1",
                    "face_count": 1,
                    "named": False,
                    "person_names": [],
                    "members": [{"media_id": "m1", "face_id": "f1", "source_type": "folder", "path": "/tmp/a.png", "bbox": (1, 2, 20, 20)}],
                },
            ]
        }

    monkeypatch.setattr(Application, "board", fake_board)

    photo = tmp_path / "a.png"
    photo.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h", 40, 20, 3, 1),
    )
    conn.commit()
    conn.close()

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openPeople()
    assert bridge.people_model.rowCount() == 1
    assert bridge.people_model.row("c1") is not None
    assert bridge.people_model.row("t1") is None
    shutdown_shell(engine)


def test_people_actions_follow_selected_kind(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    def fake_board(self, run_id=None):
        return {
            "items": [
                {
                    "kind": "cluster",
                    "cluster_id": "c1",
                    "face_count": 2,
                    "named": False,
                    "person_names": [],
                    "members": [
                        {"media_id": "m1", "face_id": "f1", "source_type": "folder", "path": "/a", "bbox": (0, 0, 10, 10)},
                        {"media_id": "m1", "face_id": "f2", "source_type": "folder", "path": "/a", "bbox": (20, 0, 10, 10)},
                    ],
                },
                {
                    "kind": "unassigned",
                    "face_id": "f9",
                    "face_count": 1,
                    "named": False,
                    "person_names": [],
                    "members": [
                        {"media_id": "m2", "face_id": "f9", "source_type": "folder", "path": "/b", "bbox": (0, 0, 8, 8)}
                    ],
                },
            ]
        }

    monkeypatch.setattr(Application, "board", fake_board)
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openPeople()
    bridge.selectGroup("c1")
    assert bridge.selectedKind == "cluster"
    assert bridge.canNameSelected is True
    assert bridge.canNoteSelected is True
    assert bridge.canIgnoreSelected is True
    assert bridge.canMergeCluster is True
    assert bridge.canSplitCluster is True
    assert bridge.people_model.row("c1")["faceId"] == "f1"
    bridge.selectGroup("f9")
    assert bridge.selectedKind == "unassigned"
    assert bridge.canNameSelected is True
    assert bridge.canNoteSelected is True
    assert bridge.canIgnoreSelected is True
    assert bridge.canMergeCluster is False
    assert bridge.canSplitCluster is False
    assert bridge.canMergeSelected is False
    shutdown_shell(engine)


def test_focus_loads_observation_boxes(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    def fake_canvas(self, run_id=None):
        return {
            "faces": [
                {
                    "face_id": "f1",
                    "media_id": "m1",
                    "bbox_x1": 10,
                    "bbox_y1": 20,
                    "bbox_x2": 110,
                    "bbox_y2": 120,
                    "cluster_id": None,
                    "person_id": None,
                    "status": "ok",
                }
            ],
            "items": [],
            "track_lane_by_face": {},
            "track_lane_by_item": {},
        }

    monkeypatch.setattr(Application, "canvas", fake_canvas)

    def fake_overlay(store, media_id):
        from semblon.canvas_data import overlay_boxes

        return overlay_boxes(fake_canvas(None), media_id)

    monkeypatch.setattr("semblon.canvas_data.overlay_boxes_for_media", fake_overlay)
    store = tmp_path / "s.sqlite"
    photo = tmp_path / "a.jpg"
    photo.write_bytes(b"x")
    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h1", 200, 100, 1, 1),
    )
    conn.commit()
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openFocus("m1")
    boxes = bridge.focusObservationBoxes
    assert len(boxes) == 1
    assert boxes[0]["id"] == "f1"
    assert boxes[0]["nx"] == 0.05
    assert boxes[0]["ny"] == 0.2
    bridge.selectObservation("f1")
    assert bridge.selectedObservationId == "f1"
    bridge.escape()
    assert bridge.focusObservationBoxes == []
    shutdown_shell(engine)


def test_advanced_activity_opens_history_rows(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    def fake_activity(self, run_id=None):
        return {
            "empty": False,
            "processing": {"lines": ["Scanned 3 photos."]},
            "together_lines": ["Ada and Bea appear together."],
            "moment_lines": ["A quiet afternoon."],
        }

    monkeypatch.setattr(Application, "activity_memory", fake_activity)
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    bridge.setMode("advanced")
    bridge.showActivity()
    assert bridge.activityOpen is True
    assert len(bridge.activityRows) == 3
    assert root.findChild(QObject, "activitySheet") is not None
    bridge.closeActivity()
    assert bridge.activityOpen is False
    shutdown_shell(engine)


def test_job_band_exposes_pause_and_cancel(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    assert root.findChild(QObject, "jobBand") is not None
    assert bridge.taskLabel == "Quiet"
    assert bridge.taskCount == 0
    bridge._timer.stop()
    bridge._job_active = True
    bridge._job_state = "running"
    bridge._progress_current = 1
    bridge._progress_total = 4
    bridge.jobChanged.emit()
    bridge.openTasks()
    app.processEvents()
    assert bridge.taskCount == 1
    assert root.findChild(QObject, "pauseJob") is not None
    assert root.findChild(QObject, "cancelJob") is not None
    bridge.closeTasks()
    assert bridge.tasksOpen is False
    shutdown_shell(engine)


def test_unresolved_text_is_initialized(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    app = QApplication.instance() or QApplication([])
    del app
    jobs = Application(tmp_path / "s.sqlite")
    bridge = ShellBridge(ArchiveModel(jobs), jobs)
    assert bridge.unresolvedText == ""
    bridge.shutdown()


def test_decide_names_an_unassigned_face(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    calls = []

    def fake_board(self, run_id=None):
        return {
            "items": [
                {
                    "kind": "unassigned",
                    "face_id": "f9",
                    "face_count": 1,
                    "named": False,
                    "person_names": [],
                    "members": [{"media_id": "m1", "face_id": "f9", "source_type": "folder"}],
                }
            ]
        }

    def record(name):
        def _inner(*args, **kwargs):
            calls.append(name)
            return {"display_name": "Ada", "person_id": "p1"}

        return _inner

    monkeypatch.setattr(Application, "board", fake_board)
    monkeypatch.setattr("semblon.review_board.name_cluster", record("cluster"))
    monkeypatch.setattr("semblon.review_board.name_face", record("face"))
    monkeypatch.setattr("semblon.review_board.ignore_subject", record("ignore"))
    monkeypatch.setattr("semblon.review_board.note_subject", record("note"))
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")
    app = QApplication.instance() or QApplication([])
    del app
    jobs = Application(tmp_path / "s.sqlite")
    bridge = ShellBridge(ArchiveModel(jobs), jobs)
    assert bridge.decide("name", "f9", "Ada") == "Saved name: Ada."
    assert bridge.decide("note", "f9", "keep") == "Saved your note."
    assert bridge.decide("ignore", "f9", "") == "Left this group unknown."
    assert calls == ["face", "note", "ignore"]
    bridge.shutdown()


def test_decide_refuses_a_track_without_a_selected_face(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    def fake_board(self, run_id=None):
        return {
            "items": [
                {
                    "kind": "track",
                    "track_id": "t1",
                    "face_count": 2,
                    "named": False,
                    "person_names": [],
                    "members": [
                        {"media_id": "mv", "face_id": "fv", "source_type": "video"},
                    ],
                }
            ]
        }

    monkeypatch.setattr(Application, "board", fake_board)
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")
    app = QApplication.instance() or QApplication([])
    del app
    jobs = Application(tmp_path / "s.sqlite")
    bridge = ShellBridge(ArchiveModel(jobs), jobs)
    bridge.setMode("advanced")
    note = bridge.decide("ignore", "t1", "")
    assert "track is not a person" in note
    bridge.shutdown()


def test_decide_reaches_real_review_writer(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id, embedding_dim,
           embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("run-1", "2026-10-06T00:00:00Z", "test", "pack", 512, "l2", "{}", "{}", "x64", "native"),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")
    app = QApplication.instance() or QApplication([])
    del app
    jobs = Application(store)
    bridge = ShellBridge(ArchiveModel(jobs), jobs)
    note = bridge.decide("name", "missing-cluster", "Ada")
    assert note == "Semblon couldn't save that decision."
    assert "traceback" not in note.lower()
    assert "sqlite" not in note.lower()


def test_primary_presentation_fails_closed_and_advanced_preserves_detail():
    from semblon.native_shell.presentation import present_message

    fallback = "FALLBACK"
    technical = "sqlite error\ntraceback here\ncluster_id=c1"
    assert present_message("primary", technical, fallback=fallback) == fallback
    assert present_message("advanced", technical, fallback=fallback) == technical

    assert present_message("primary", "backend timeout while syncing cache", fallback=fallback) == fallback
    assert present_message("advanced", "backend timeout while syncing cache", fallback=fallback) == "backend timeout while syncing cache"

    assert present_message("primary", "internal provider failure", fallback=fallback) == fallback
    assert present_message("primary", "hello from an unknown backend", fallback=fallback) == fallback

    mixed = "Saved your note.\ninternal provider failure"
    assert present_message("primary", mixed, fallback=fallback) == fallback

    assert present_message("primary", "", fallback=fallback) == fallback
    assert present_message("advanced", "", fallback=fallback) == fallback


def test_primary_presentation_unknown_text_invariant():
    from semblon.native_shell.presentation import present_message

    fallback = "FALLBACK"
    for unknown in [
        "backend timeout while syncing cache",
        "internal provider failure",
        "unexpected database state",
        "foo bar baz",
    ]:
        assert present_message("primary", unknown, fallback=fallback) == fallback


def test_decision_success_outputs_remain_safe_and_stable():
    from semblon.native_shell.presentation import decision_success

    assert decision_success("name", "Ada") == "Saved name: Ada."
    assert decision_success("name", "") == "Saved name for this group."
    assert decision_success("ignore") == "Left this group unknown."
    assert decision_success("note") == "Saved your note."
    assert decision_success("merge") == "Merged the selected groups."
    assert decision_success("split") == "Split the selected faces into a new group."
    assert decision_success("rule_out") == "Marked this as not the same person."
    assert decision_success("other") == "Saved your decision."


def test_bridge_mode_and_atmosphere_persist(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel
    from semblon.ui_prefs import load_prefs

    store = tmp_path / "prefs.sqlite"
    jobs = Application(store)
    bridge = ShellBridge(ArchiveModel(jobs), jobs)

    assert bridge.mode == "primary"
    bridge.toggleMode()
    assert bridge.mode == "advanced"
    bridge.setAtmosphere("tokyo_synth")
    prefs = load_prefs(store)
    assert prefs.get("shell_mode") == "advanced"
    assert prefs.get("theme") == "tokyo_synth"

    bridge2 = ShellBridge(ArchiveModel(jobs), jobs)
    assert bridge2.mode == "advanced"
    assert bridge2.atmosphereId == "tokyo_synth"


def test_bridge_submit_command_primary_vs_advanced(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    def fake_board(self, run_id=None):
        return {
            "items": [
                {
                    "cluster_id": "c1",
                    "face_count": 2,
                    "named": True,
                    "person_names": ["Ada"],
                    "members": [{"media_id": "m1", "face_id": "f1"}],
                },
                {
                    "cluster_id": "c2",
                    "face_count": 1,
                    "named": False,
                    "person_names": [],
                    "members": [{"media_id": "m2", "face_id": "f2"}],
                },
            ]
        }

    monkeypatch.setattr(Application, "board", fake_board)

    store = tmp_path / "prefs.sqlite"
    jobs = Application(store)
    bridge = ShellBridge(ArchiveModel(jobs), jobs)

    bridge.submitCommand("ada")
    assert bridge.resultText == "Found: Ada."

    bridge.submitCommand("status")
    assert bridge.resultText == "No people matched that search."

    bridge.setMode("advanced")
    bridge.submitCommand("status")
    assert "mode=advanced" in bridge.resultText
    assert "focus_id=" in bridge.resultText

    bridge.submitCommand("people")
    assert "c2" in bridge.resultText


def test_point_uses_stored_region_then_existing_similar_door(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    found = []

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        found.append((media_id, x, y, w, h))
        return {"region": {}, "similar": {"status": "SUCCESS", "items": [{"media_id": "m2", "score": 0.8}]}, "persons": 0}

    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)
    photo = tmp_path / "a.png"
    photo.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute("INSERT INTO media VALUES (?,?,?,?,?,?,?,?)", ("m1", "folder", str(photo), "h", 100, 80, 3, 1))
    conn.execute("INSERT INTO media VALUES (?,?,?,?,?,?,?,?)", ("m2", "folder", str(photo), "i", 100, 80, 4, 1))
    conn.commit()
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openFocus("m1")
    bridge.setRegion(0.2, 0.2, 0.1, 0.1)
    assert bridge._region_norm == (0.2, 0.2, 0.1, 0.1)
    assert bridge._selection_kind == "drawn"
    monkeypatch.setattr(bridge, "_stored_visual_bbox", lambda media_id, px, py: (10, 20, 30, 40))
    monkeypatch.setattr(bridge, "_refine_bbox", lambda media_id, px, py: (1, 1, 90, 70))
    spec = bridge.pointAt(0.5, 0.5)
    assert spec == "0.34,0.3,0.32,0.4"
    assert found == [("m1", 34, 24, 32, 32)]
    assert bridge.similarCount == 1
    assert bridge.similarId(0) == "m2"
    bridge.openFocus(bridge.similarId(0))
    assert bridge.focusId == "m2"
    assert bridge.similarCount == 0
    bridge.escape()
    assert bridge.focusId == ""
    assert bridge.pointAt(-0.1, 0.2) == ""
    assert found == [("m1", 34, 24, 32, 32)]
    shutdown_shell(engine)


def test_point_on_fresh_image_refines_without_inventing_a_miss(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.store import connect, init_db

    found = []
    monkeypatch.setattr(
        Application,
        "remember_and_find_region",
        lambda self, media_id, x, y, w, h, **kwargs: found.append((x, y, w, h)) or {"similar": {"status": "UNAVAILABLE", "reason": "pack"}},
    )
    photo = tmp_path / "a.png"
    photo.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute("INSERT INTO media VALUES (?,?,?,?,?,?,?,?)", ("m1", "folder", str(photo), "h", 50, 40, 3, 1))
    conn.commit()
    conn.close()
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openFocus("m1")
    monkeypatch.setattr(bridge, "_stored_visual_bbox", lambda media_id, px, py: (1, 1, 40, 30))
    monkeypatch.setattr(bridge, "_refine_bbox", lambda media_id, px, py: (5, 6, 10, 12))
    assert bridge.pointAt(0.2, 0.2) == "0.0,0.0,0.64,0.8"
    assert found == [(0, 0, 32, 32)]
    assert bridge.similarState == "unavailable"
    assert bridge.pointAt(0.2, 0.2) == "0.0,0.0,0.64,0.8"
    assert found == [(0, 0, 32, 32), (0, 0, 32, 32)]
    shutdown_shell(engine)







def test_bridge_exposes_read_only_editorial_counts(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.executemany(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        [
            ("p1", "folder", str(tmp_path / "2017" / "a.jpg"), "h1", 10, 10, 1_503_000_000_000_000_000, 1),
            ("v1", "video", str(tmp_path / "2017" / "c.mp4"), "h3", 10, 10, 1_503_100_000_000_000_000, 1),
        ],
    )
    conn.commit()
    conn.close()
    _app = QApplication.instance() or QApplication([])
    bridge = ShellBridge(ArchiveModel(Application(store)), Application(store))
    try:
        assert bridge.photoCount == 1
        assert bridge.videoCount == 1
        assert bridge.yearRows[0]["label"] == "2017"
        assert "no relationship" in bridge.spatialNote.lower()
    finally:
        bridge.shutdown()


def test_scan_progress_keeps_the_field_windowed(tmp_path, monkeypatch):
    """Progress must not rebuild the calendar id lists on the UI thread."""
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.events import JOB_PROGRESS
    from semblon.native_shell.model import ArchiveModel
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.close()
    _app = QApplication.instance() or QApplication([])
    bridge = ShellBridge(ArchiveModel(Application(store)), Application(store))
    calls = {"n": 0}

    def editorial():
        calls["n"] += 1

    bridge._reload_editorial = editorial
    bridge._model.set_media_ids(["p1"])
    bridge._scope_kind = ""
    bridge._person_field_filter = False
    bridge._events.record(JOB_PROGRESS, {"current": 1, "total": 4, "stage": "ingest"})
    bridge._library_refresh_at = 0.0
    try:
        bridge._flush_progress()
        assert calls["n"] == 0
        assert bridge._model.media_ids() is None
        assert bridge._progress_current == 1
        bridge._refresh_library()
        assert calls["n"] == 1
    finally:
        bridge.shutdown()


def test_gate_a_archive_similar_and_context_journey(tmp_path, monkeypatch):
    """Milestones 1–3: reconnect, honest Similar, day context with neighbours (offscreen)."""
    import time
    from unittest.mock import patch

    import numpy as np

    pytest.importorskip("PySide6")
    cv2 = pytest.importorskip("cv2")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell
    from semblon.process import process_folder
    from semblon.store import connect

    folder = tmp_path / "José"
    folder.mkdir()
    day_ns = 1_718_452_800_000_000_000  # 2024-06-15 UTC
    other_ns = 1_721_044_800_000_000_000  # 2024-07-15 UTC

    def _write(name: str, bgr, mtime_ns: int) -> Path:
        path = folder / name
        ok, buf = cv2.imencode(".png", bgr)
        assert ok
        path.write_bytes(buf.tobytes())
        os.utime(path, ns=(mtime_ns, mtime_ns))
        return path

    # Distinct bytes (unique sha256) but close colour histograms so Similar can match.
    green_a = np.zeros((48, 48, 3), dtype=np.uint8)
    green_a[:, :] = (0, 210, 0)
    green_a[0, 0] = (1, 210, 0)
    green_b = np.zeros((48, 48, 3), dtype=np.uint8)
    green_b[:, :] = (0, 205, 0)
    green_b[0, 0] = (2, 205, 0)
    red = np.zeros((48, 48, 3), dtype=np.uint8)
    red[:, :] = (0, 0, 210)
    _write("a.png", green_a, day_ns)
    _write("b.png", green_b, day_ns)
    _write("c.png", red, other_ns)
    store = tmp_path / "gate-a.sqlite"
    quiet = lambda *_a, **_k: None
    with (
        patch("semblon.ingest.load_app", return_value=object()),
        patch("semblon.ingest.embed_bgr", return_value=[]),
    ):
        process_folder(folder, store=store, observers="color", progress=quiet)

    conn = connect(store)
    try:
        rows = {
            Path(r[1]).name: (r[0], r[1])
            for r in conn.execute("SELECT media_id, path FROM media").fetchall()
        }
    finally:
        conn.close()
    assert set(rows) == {"a.png", "b.png", "c.png"}
    id_a, path_a = rows["a.png"]
    id_b, path_b = rows["b.png"]
    id_c, _path_c = rows["c.png"]

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    try:
        for _ in range(20):
            app.processEvents()
            time.sleep(0.01)
        assert bridge.empty is False
        assert bridge.count == 3

        bridge.openFocus(id_a)
        app.processEvents()
        assert bridge.focusId == id_a
        assert bridge.focusFileMissing is False
        bridge.findSimilarWhole()
        app.processEvents()
        assert "colour histogram" in bridge.similarNote.lower()
        assert bridge.similarState in {"ready", "empty"}
        if bridge.similarState == "ready":
            assert bridge.similarId(0) in {id_a, id_b, id_c}

        # Context from a same-day neighbour: Field shows that day's archive rows only.
        bridge.openFocusInContext(id_b)
        app.processEvents()
        assert bridge.focusId == id_b
        assert bridge.scopeKind == "day"
        assert bridge.scopeLabel == "2024-06-15"
        field_ids = {
            bridge._model.data(bridge._model.index(i, 0), Qt.ItemDataRole.UserRole + 1)
            for i in range(bridge._model.rowCount())
        }
        assert id_a in field_ids and id_b in field_ids
        assert id_c not in field_ids

        Path(path_a).unlink()
        bridge.openFocus(id_a)
        app.processEvents()
        assert bridge.focusFileMissing is True
        assert "missing" in bridge.resultText.lower()

        moved = folder / "b-renamed.png"
        Path(path_b).replace(moved)
        with (
            patch("semblon.ingest.load_app", return_value=object()),
            patch("semblon.ingest.embed_bgr", return_value=[]),
        ):
            process_folder(folder, store=store, observers="color", progress=quiet)
        conn = connect(store)
        try:
            new_path = conn.execute(
                "SELECT path FROM media WHERE media_id=?", (id_b,)
            ).fetchone()[0]
            count = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
        finally:
            conn.close()
        assert count == 3
        assert Path(new_path) == moved
        bridge._refresh_library()
        app.processEvents()
        bridge.openFocus(id_b)
        app.processEvents()
        assert bridge.focusId == id_b
        assert bridge.focusFileMissing is False
    finally:
        shutdown_shell(engine)
