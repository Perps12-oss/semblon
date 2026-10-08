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
    assert bridge.count == 2
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
    assert bridge.focusId == ""
    assert bridge.focusKind == ""
    assert bridge.focusUrl == ""
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


def test_focus_qml_draws_into_strip_without_a_similar_button():
    """Product door is the drag release. No Qt import, so this is not an EGL test."""
    qml = (
        Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "qml" / "Shell.qml"
    ).read_text(encoding="utf-8")
    assert "shell.findSimilar()" in qml
    assert "shell.resumeJob()" in qml
    assert 'objectName: "resumeJob"' in qml
    assert 'text: "Similar"' not in qml
    assert 'objectName: "findSimilar"' not in qml
    assert 'objectName: "similarStrip"' in qml
    assert "shell.thumbFor(mediaId)" in qml
    assert "shell.openFocus(mediaId)" in qml
    assert "shell.clearDrawnQuery()" in qml
    assert "image://archive/t/" not in qml.split("similarStrip", 1)[-1].split("similarThumb", 1)[0]
    host = (
        Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "host.py"
    ).read_text(encoding="utf-8")
    assert 'setContextProperty("similarModel"' in host


def test_drawn_region_strip_replaces_and_clears(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
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
    assert root.findChild(QObject, "findSimilar") is None
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
    assert bridge.similarNote == "No similar images found yet."
    bridge.setRegion(0.1, 0.1, 0.2, 0.2)
    bridge.findSimilar()
    bridge.focusNext()
    assert bridge.similarState == "idle"
    bridge.setRegion(0.1, 0.1, 0.2, 0.2)
    bridge.findSimilar()
    bridge.escape()
    assert bridge.focusId == ""
    assert bridge.similarState == "idle"
    engine.deleteLater()


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


def test_shell_add_folder_indexes_appearance_and_draw_finds_it(tmp_path, monkeypatch):
    """Fresh native Add Folder writes appearance/rgb8@1. Draw searches that space."""
    pytest.importorskip("PySide6")
    cv2 = pytest.importorskip("cv2")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import numpy as np
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel
    from semblon.observers import APPEARANCE_PACK

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
    from semblon.native_shell.host import build_shell
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
    monkeypatch.setattr("semblon.review.name_cluster", record("name"))
    monkeypatch.setattr("semblon.review.merge_clusters", record("merge"))
    monkeypatch.setattr("semblon.review.split_cluster", record("split"))
    monkeypatch.setattr("semblon.review.ignore_subject", record("ignore"))
    monkeypatch.setattr("semblon.review.note_subject", record("note"))
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
    assert root.findChild(QObject, "commandField").property("visible") is False
    bridge.openPeople()
    app.processEvents()
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
    assert calls == ["name", "merge", "split", "ignore", "note"]
    bridge.closePeople()
    assert bridge.peopleOpen is False
    qml = Path(__file__).resolve().parents[1].joinpath("semblon/native_shell/qml/Shell.qml").read_text(encoding="utf-8")
    assert "review.html" not in qml
    assert 'text: "Play"' not in qml
    engine.deleteLater()


def test_people_split_uses_visual_face_selection_and_merge_target(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
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
    monkeypatch.setattr("semblon.review.merge_clusters", record("merge"))
    monkeypatch.setattr("semblon.review.split_cluster", record("split"))
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
    assert bridge.selectedTitle == "Unnamed"
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
    engine.deleteLater()


def test_people_desk_hides_video_only_tracks_from_qt_shell(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
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
    engine.deleteLater()


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


def test_point_uses_stored_region_then_existing_similar_door(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
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
    monkeypatch.setattr(bridge, "_stored_visual_bbox", lambda media_id, px, py: (10, 20, 30, 40))
    spec = bridge.pointAt(0.5, 0.5)
    assert spec == "0.1,0.25,0.3,0.5"
    assert found == [("m1", 10, 20, 30, 40)]
    assert bridge.similarCount == 1
    assert bridge.similarId(0) == "m2"
    bridge.openFocus(bridge.similarId(0))
    assert bridge.focusId == "m2"
    assert bridge.similarCount == 0
    bridge.escape()
    assert bridge.focusId == ""
    assert bridge.pointAt(-0.1, 0.2) == ""
    assert found == [("m1", 10, 20, 30, 40)]
    engine.deleteLater()


def test_point_on_fresh_image_refines_without_inventing_a_miss(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
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
    monkeypatch.setattr(bridge, "_stored_visual_bbox", lambda media_id, px, py: None)
    monkeypatch.setattr(bridge, "_refine_bbox", lambda media_id, px, py: (5, 6, 10, 12))
    assert bridge.pointAt(0.2, 0.2) == "0.1,0.15,0.2,0.3"
    assert found == [(5, 6, 10, 12)]
    assert bridge.similarState == "unavailable"
    monkeypatch.setattr(bridge, "_refine_bbox", lambda media_id, px, py: None)
    assert bridge.pointAt(0.2, 0.2) == ""
    assert bridge.similarCount == 0
    engine.deleteLater()





