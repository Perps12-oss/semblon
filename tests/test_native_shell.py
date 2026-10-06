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
    assert "shell.pointAt(" in qml
    assert "resolvePoint(" in qml
    assert "onPositionChanged" in qml
    assert "shell.pointAt(" not in qml.split("onPositionChanged", 1)[1].split("onReleased", 1)[0]
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



def _seed_focus_store(store, photo, other, *, visual=False):
    from semblon.store import connect, init_db

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
        if visual:
            conn.execute(
                """INSERT INTO runs(run_id, started_at, software_version, pack_id, embedding_dim,
                   embedding_norm, config_json, runtime_json, arch, execution)
                   VALUES ('r1','2026-10-06T00:00:00Z','1.4.0','p',512,'l2','{}','{}','x64','native')"""
            )
            conn.execute(
                "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES ('o1','a',NULL,NULL,'r1')"
            )
            conn.execute(
                """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
                   bbox_x1, bbox_y1, bbox_x2, bbox_y2, score, payload_json, face_id)
                   VALUES ('i1','o1','r1','object','visual.region',4,4,16,12,0.9,?,NULL)""",
                ('{"region_id":1,"kind":"thing","rows":{"6":[[4,16]]}}',),
            )
        conn.commit()
    finally:
        conn.close()


def test_point_uses_stored_region_without_refine(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
    from semblon.semantic_visual import LocalSemanticVisualProvider

    calls = []
    refine_calls = []

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        calls.append((media_id, x, y, w, h))
        return {"region": {}, "similar": {"status": "SUCCESS", "items": [{"media_id": "b", "score": 0.8}]}, "persons": 0}

    def boom(self, image, x, y):
        refine_calls.append((x, y))
        raise AssertionError("stored hit must not refine")

    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)
    monkeypatch.setattr(LocalSemanticVisualProvider, "refine_from_point", boom)
    photo = tmp_path / "a.png"
    other = tmp_path / "b.png"
    photo.write_bytes(b"not-decoded")
    other.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    _seed_focus_store(store, photo, other, visual=True)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openFocus("a")
    spec = bridge.pointAt(8 / 40, 6 / 20)
    assert refine_calls == []
    assert bridge._point_source == "stored"
    assert calls == [("a", 4, 4, 12, 8)]
    assert spec.startswith("0.1,")
    assert bridge.similarState == "ready"
    assert bridge.similarId(0) == "b"
    engine.deleteLater()


def test_point_on_fresh_image_refines_without_stored_region(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    import numpy as np

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
    from semblon.selection import load_media_bgr
    from semblon.semantic_visual import LocalSemanticVisualProvider
    from semblon.store import connect
    from semblon.visual.persist import load_hover_rows

    calls = []
    refine_calls = []

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        calls.append((media_id, x, y, w, h))
        return {"region": {}, "similar": {"status": "NO_RESULT", "items": []}, "persons": 0}

    def refine(self, image, x, y):
        refine_calls.append((x, y, image is not None))
        return {"bbox": (10, 4, 22, 14), "label": "unknown region"}

    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)
    monkeypatch.setattr(LocalSemanticVisualProvider, "refine_from_point", refine)
    monkeypatch.setattr("semblon.selection.load_media_bgr", lambda store, media_id: np.zeros((20, 40, 3), dtype=np.uint8))
    photo = tmp_path / "a.png"
    other = tmp_path / "b.png"
    photo.write_bytes(b"not-decoded")
    other.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    _seed_focus_store(store, photo, other, visual=False)
    conn = connect(store)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM observation_items WHERE provider='visual.region'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 0
    assert load_hover_rows(store, media_id="a", run_id="missing") == []
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openFocus("a")
    bridge.setRegion(0.2, 0.2, 0.2, 0.2)
    bridge.findSimilar()
    assert bridge.similarState == "empty"
    spec = bridge.pointAt(0.5, 0.5)
    assert refine_calls == [(20, 10, True)]
    assert bridge._point_source == "refine"
    assert calls[-1] == ("a", 10, 4, 12, 10)
    assert spec
    assert bridge.similarState == "empty"
    assert bridge.similarNote == "No similar images found yet."
    assert bridge.similarCount == 0
    engine.deleteLater()


def test_point_miss_clears_strip_and_letterbox_is_not_a_pixel(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
    from semblon.semantic_visual import LocalSemanticVisualProvider

    calls = []

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        calls.append((media_id, x, y, w, h))
        return {"region": {}, "similar": {"status": "SUCCESS", "items": [{"media_id": "b", "score": 0.5}]}, "persons": 0}

    def refine(self, image, x, y):
        return None

    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)
    monkeypatch.setattr(LocalSemanticVisualProvider, "refine_from_point", refine)
    monkeypatch.setattr("semblon.selection.load_media_bgr", lambda store, media_id: __import__("numpy").zeros((20, 40, 3), dtype="uint8"))
    photo = tmp_path / "a.png"
    other = tmp_path / "b.png"
    photo.write_bytes(b"not-decoded")
    other.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    _seed_focus_store(store, photo, other)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openFocus("a")
    bridge.setRegion(0.25, 0.25, 0.2, 0.2)
    bridge.findSimilar()
    assert bridge.similarState == "ready"
    assert bridge.pointAt(-0.1, 0.2) == ""
    assert bridge.similarState == "idle"
    assert bridge.pointAt(1.0, 0.2) == ""
    assert calls == [("a", 10, 5, 8, 4)]
    bridge.setRegion(0.25, 0.25, 0.2, 0.2)
    bridge.findSimilar()
    assert bridge.pointAt(0.5, 0.5) == ""
    assert bridge.similarState == "idle"
    assert bridge.similarCount == 0
    engine.deleteLater()


def test_second_point_replaces_strip(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
    from semblon.semantic_visual import LocalSemanticVisualProvider

    calls = []

    def fake_similar(self, media_id, x, y, w, h, **kwargs):
        calls.append((media_id, x, y, w, h))
        media = "b" if len(calls) == 1 else "c"
        return {"region": {}, "similar": {"status": "SUCCESS", "items": [{"media_id": media, "score": 0.7}]}, "persons": 0}

    def refine(self, image, x, y):
        if x < 10:
            return {"bbox": (2, 2, 8, 8)}
        return {"bbox": (20, 8, 30, 16)}

    monkeypatch.setattr(Application, "remember_and_find_region", fake_similar)
    monkeypatch.setattr(LocalSemanticVisualProvider, "refine_from_point", refine)
    monkeypatch.setattr("semblon.selection.load_media_bgr", lambda store, media_id: __import__("numpy").zeros((20, 40, 3), dtype="uint8"))
    photo = tmp_path / "a.png"
    other = tmp_path / "b.png"
    photo.write_bytes(b"not-decoded")
    other.write_bytes(b"not-decoded")
    store = tmp_path / "s.sqlite"
    _seed_focus_store(store, photo, other)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    bridge.openFocus("a")
    bridge.pointAt(0.1, 0.2)
    assert bridge.similarId(0) == "b"
    bridge.pointAt(0.6, 0.5)
    assert calls[-1][0] == "a"
    assert bridge.similarCount == 1
    assert bridge.similarId(0) == "c"
    bridge.escape()
    assert bridge.focusId == ""
    assert bridge.similarState == "idle"
    engine.deleteLater()
