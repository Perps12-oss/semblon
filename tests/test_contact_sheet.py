"""Contact Sheet shell: the small backend pieces the Roll, loupe and first run rely on."""

import ast
import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")


def _seed(store, tmp_path, n=3):
    from semblon.store import connect, init_db

    conn = connect(store)
    init_db(conn)
    rows = []
    for i in range(n):
        day = 1_503_000_000_000_000_000 + i * 3_600_000_000_000
        rows.append((f"m{i}", "folder", str(tmp_path / f"{i}.jpg"), f"h{i}", 10, 10, day, 1))
    conn.executemany("INSERT INTO media VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    QApplication.instance() or QApplication([])
    store = tmp_path / "s.sqlite"
    _seed(store, tmp_path)
    jobs = Application(store)
    made = ShellBridge(ArchiveModel(jobs), jobs)
    made._model.reload()
    yield made
    made.shutdown()


def test_day_detail_lists_a_days_photos_without_inventing_people(bridge, tmp_path):
    from semblon.native_shell.editorial import day_detail, scope_ids

    store = tmp_path / "s.sqlite"
    days = scope_ids(store).get("day", {})
    assert days
    label = next(iter(days))
    detail = day_detail(store, label)
    assert detail["count"] == len(days[label]) == 3
    assert detail["faceCount"] == 0
    assert detail["people"] == []
    assert day_detail(store, "no-such-day")["count"] == 0


def test_adding_something_that_is_not_a_folder_says_so_and_changes_nothing(bridge, tmp_path):
    before = bridge._jobs.archive_count()
    bridge.addFolderPath(str(tmp_path / "missing"))
    assert "folder" in bridge.noticeText.lower()
    assert bridge._jobs.archive_count() == before


def test_job_fraction_is_clamped(bridge):
    assert bridge.jobFraction == 0.0
    bridge._progress_total = 4
    bridge._progress_current = 1
    assert bridge.jobFraction == 0.25
    bridge._progress_current = 9
    assert bridge.jobFraction == 1.0


def test_matches_on_the_roll_replace_the_view_and_clear_restores_it(bridge):
    assert bridge._model.rowCount() == 3
    bridge._similar.set_rows([("m2", 0.9), ("m0", 0.5)])
    bridge.showMatchesOnRoll()
    assert bridge.matchesOnRoll is True
    assert bridge._model.rowCount() == 2
    bridge.clearMatches()
    assert bridge.matchesOnRoll is False
    assert bridge._model.rowCount() == 3


def test_bundled_fonts_register_so_windows_cannot_substitute_them(bridge):
    from semblon.native_shell.host import load_bundled_fonts

    families = " ".join(load_bundled_fonts())
    assert "Fraunces" in families
    assert "Inter" in families


def test_one_gui_remains(bridge):
    from pathlib import Path

    qml = Path("semblon/native_shell/qml")
    assert (qml / "Table.qml").is_file()
    assert not any((qml / name).exists() for name in ("Shell.qml", "HomeLaunchpad.qml"))
    for path in qml.glob("*.qml"):
        assert "QtQuick.Controls" not in path.read_text(encoding="utf-8"), path.name

BANNED = re.compile(
    r"\b(models?|packs?|quer(?:y|ies)|embeddings?|index(?:ed|es|ing)?|capabilit(?:y|ies)|schema|apis?)\b",
    re.IGNORECASE,
)


def _python_strings(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
                docs.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs:
            text = node.value
            if " " in text and not re.match(r"\s*(SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|PRAGMA)\b", text, re.I):
                yield node.lineno, text


def test_no_engine_words_in_anything_a_person_reads():
    """Banned words must not appear in shell QML text or in dialog/banner/install strings."""
    hits = []
    for path in Path("semblon/native_shell/qml").glob("*.qml"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("//"):
                continue
            for literal in re.findall(r'"((?:[^"\\]|\\.)*)"', line):
                if " " in literal and BANNED.search(literal):
                    hits.append(f"{path.name}:{number}: {literal}")
    for name in (
        "semblon/native_shell/bridge.py",
        "semblon/native_shell/adapter.py",
        "semblon/native_shell/presentation.py",
        "semblon/optional_providers.py",
    ):
        for number, text in _python_strings(name):
            if BANNED.search(text):
                hits.append(f"{name}:{number}: {text[:80]}")
    assert not hits, "engine words reach people:\n" + "\n".join(hits)


def test_install_failure_text_never_leaks_engine_words():
    from semblon.native_shell.bridge import _plain

    fallback = "That didn't finish."
    assert _plain("region pack install refused: sha256=abc", fallback) == fallback
    assert _plain("", fallback) == fallback
    assert _plain("The disk is full.", fallback) == "The disk is full."

# --- Pointer and keyboard interaction (offscreen window, simulated input) ---

def _spin(app, seconds=0.5):
    import time

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)


def _boot_with_photo(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell

    photo = tmp_path / "a.png"
    img = QImage(480, 320, QImage.Format.Format_RGB32)
    img.fill(QColor("#885522"))
    img.save(str(photo))
    store = tmp_path / "s.sqlite"
    from semblon.store import connect, init_db

    conn = connect(store)
    init_db(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "h", 480, 320, 1_503_000_000_000_000_000, 1),
    )
    conn.commit()
    conn.close()
    app = QApplication.instance() or QApplication([])
    _a, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    root.resize(1200, 800)
    root.show()
    _spin(app, 1.5)
    return app, engine, root, engine._semblon_bridge


def _open_viewer(app, root, bridge):
    from PySide6.QtCore import QMetaObject, QObject

    bridge.openFocus("m1")
    _spin(app, 1.0)
    viewer = root.findChild(QObject, "viewer")
    QMetaObject.invokeMethod(viewer, "forceActiveFocus")
    _spin(app, 0.2)
    return viewer


def test_loupe_pointer_drag_selects_a_detail(tmp_path, monkeypatch):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from semblon.native_shell.host import shutdown_shell

    app, engine, root, bridge = _boot_with_photo(tmp_path, monkeypatch)
    try:
        viewer = _open_viewer(app, root, bridge)
        QTest.keyClick(root, Qt.Key.Key_L)
        _spin(app, 0.2)
        assert viewer.property("loupeOn") is True
        cx, cy = root.width() // 2, root.height() // 2 - 40
        QTest.mousePress(root, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(cx - 60, cy - 40))
        for step in range(1, 9):
            QTest.mouseMove(root, QPoint(cx - 60 + step * 15, cy - 40 + step * 10))
            app.processEvents()
        QTest.mouseRelease(root, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(cx + 60, cy + 40))
        _spin(app, 0.3)
        assert viewer.property("lw") > 100 and viewer.property("lh") > 70
        nx, ny, nw, nh = bridge._region_norm
        assert nw > 0 and nh > 0 and 0 <= nx <= 1 and 0 <= ny <= 1
        assert bridge._selection_kind == "drawn"
    finally:
        shutdown_shell(engine)


def test_loupe_keyboard_only_selects_a_detail(tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from semblon.native_shell.host import shutdown_shell

    app, engine, root, bridge = _boot_with_photo(tmp_path, monkeypatch)
    try:
        viewer = _open_viewer(app, root, bridge)
        shift = Qt.KeyboardModifier.ShiftModifier
        QTest.keyClick(root, Qt.Key.Key_L)
        _spin(app, 0.3)
        assert viewer.property("loupeOn") is True
        QTest.keyClick(root, Qt.Key.Key_Right)
        _spin(app, 0.2)
        assert viewer.property("lw") > 0
        start_x = viewer.property("lx")
        QTest.keyClick(root, Qt.Key.Key_Right)
        assert viewer.property("lx") > start_x
        start_w = viewer.property("lw")
        QTest.keyClick(root, Qt.Key.Key_Right, shift)
        assert viewer.property("lw") > start_w
        assert bridge.focusId == "m1"
        QTest.keyClick(root, Qt.Key.Key_Return)
        _spin(app, 0.2)
        assert bridge._selection_kind == "drawn"
        assert bridge._region_norm[2] > 0
    finally:
        shutdown_shell(engine)


def _boot_people(tmp_path, monkeypatch):
    from semblon.application import Application

    calls = []

    def fake_board(self, run_id=None):
        return {
            "items": [
                {"cluster_id": cid, "face_count": 2, "named": False, "person_names": [],
                 "members": [{"media_id": "m1", "face_id": f"f{cid}"}]}
                for cid in ("c1", "c2")
            ]
        }

    def record(name):
        def _inner(*args, **kwargs):
            calls.append((name, args[-2:] if name == "merge" else ()))
            return {"display_name": "Ada"}
        return _inner

    monkeypatch.setattr(Application, "board", fake_board)
    monkeypatch.setattr("semblon.review_board.merge_clusters", record("merge"))
    monkeypatch.setattr("semblon.review_board.ignore_subject", record("ignore"))
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")
    app, engine, root, bridge = _boot_with_photo(tmp_path, monkeypatch)
    bridge.openPeople()
    _spin(app, 1.0)
    return app, engine, root, bridge, calls


def test_people_pointer_drag_merges_one_print_onto_another(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject, QPoint, QPointF, Qt
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    from semblon.native_shell.host import shutdown_shell

    app, engine, root, bridge, calls = _boot_people(tmp_path, monkeypatch)
    try:
        grid = root.findChild(QObject, "printGrid")
        plates = [p for p in grid.property("contentItem").childItems() if p.objectName() == "print"]
        assert len(plates) == 2
        centres = [p.mapToScene(QPointF(70, 80)).toPoint() for p in plates]
        a, b = centres
        QTest.mousePress(root, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
        for step in range(1, 13):
            QTest.mouseMove(root, QPoint(a.x() + (b.x() - a.x()) * step // 12, a.y() + (b.y() - a.y()) * step // 12))
            app.processEvents()
        QTest.mouseRelease(root, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b)
        _spin(app, 0.3)
        assert [c[0] for c in calls] == ["merge"]
    finally:
        shutdown_shell(engine)


def test_people_keyboard_merges_and_sends_away_without_a_mouse(tmp_path, monkeypatch):
    from PySide6.QtCore import QMetaObject, QObject, Qt
    from PySide6.QtTest import QTest

    from semblon.native_shell.host import shutdown_shell

    app, engine, root, bridge, calls = _boot_people(tmp_path, monkeypatch)
    try:
        grid = root.findChild(QObject, "printGrid")
        QMetaObject.invokeMethod(grid, "forceActiveFocus")
        _spin(app, 0.2)
        QTest.keyClick(root, Qt.Key.Key_S)
        _spin(app, 0.3)
        assert [c[0] for c in calls] == ["merge"]
        QTest.keyClick(root, Qt.Key.Key_X)
        _spin(app, 0.3)
        assert [c[0] for c in calls][-1] == "ignore"
    finally:
        shutdown_shell(engine)


def _by_label(root, label):
    from PySide6.QtCore import QObject

    for item in root.findChildren(QObject):
        if item.property("label") == label and item.property("dimmed") is not None:
            return item
    return None


def test_first_run_has_one_primary_action_and_dimmed_verbs(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    app = QApplication.instance() or QApplication([])
    _a, engine = build_shell(tmp_path / "empty.sqlite", app=app)
    root = engine.rootObjects()[0]
    root.resize(1200, 800)
    root.show()
    _spin(app, 1.5)
    try:
        assert root.findChild(QObject, "addFolder").property("visible") is False
        assert root.findChild(QObject, "chooseFolder").property("visible") is True
        for label in ("Find a person", "Find a detail"):
            verb = _by_label(root, label)
            assert verb.property("dimmed") is True
            assert verb.property("whyDimmed") == "Add photos first"
            assert verb.property("activeFocusOnTab") is True
        more = root.findChild(QObject, "moreButton").property("label")
        assert more.startswith("More\u2026") and "Everything" not in more
        palettes = [o for o in root.findChildren(QObject) if o.property("actions") is not None and o.property("open") is not None]
        ids = {a["id"] for a in palettes[0].property("actions").toVariant()}
        assert "add" in ids and "settings" in ids
        assert not ids & {"people", "duplicates", "find", "region"}
    finally:
        shutdown_shell(engine)


def test_with_photos_the_add_button_returns_and_verbs_wake(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    from semblon.native_shell.host import shutdown_shell

    app, engine, root, _bridge = _boot_with_photo(tmp_path, monkeypatch)
    try:
        assert root.findChild(QObject, "addFolder").property("visible") is True
        assert _by_label(root, "Find a person").property("dimmed") is False
        assert root.findChild(QObject, "chooseFolder").property("visible") is False
    finally:
        shutdown_shell(engine)

def test_no_native_pop_ups_remain():
    import pathlib

    import semblon

    root = pathlib.Path(semblon.__file__).parent
    offenders = [
        str(p.relative_to(root))
        for p in root.rglob("*.py")
        if "QMessageBox" in p.read_text(encoding="utf8", errors="ignore")
    ]
    assert offenders == []


def test_install_question_is_a_themed_sheet_with_verbs_and_inline_progress(tmp_path, monkeypatch):
    from semblon.native_shell.adapter import Result

    monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")
    app, engine, root, bridge = _boot_with_photo(tmp_path, monkeypatch)
    try:
        monkeypatch.setattr(
            bridge._adapter,  # noqa: SLF001 - test seam
            "install_region_pack",
            lambda: Result("ready", "Ready."),
        )
        bridge._install_suggestion = "region_pack"  # noqa: SLF001
        bridge.installSuggestedModel()
        ask = bridge.confirm
        assert ask["open"] and ask["yes"] == "Get it ready" and ask["no"] == "Not now"
        assert any("Nothing leaves your computer" in f for f in ask["facts"])
        assert any("MB" in f or "download" in f for f in ask["facts"])
        bridge.confirmDecline()
        assert not bridge.confirm["open"]
        bridge.installSuggestedModel()
        bridge.confirmAccept()
        assert bridge.confirm["open"] and bridge.confirm["busy"]
        assert "ready" in bridge.confirm["progress"].lower()
    finally:
        from semblon.native_shell.host import shutdown_shell

        shutdown_shell(engine)

def test_bottom_bar_verbs_show_pressed_state_and_focus_ring(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    app, engine, root, bridge = _boot_with_photo(tmp_path, monkeypatch)
    try:
        for _ in range(5):
            app.processEvents()
        labels = ["Find a moment", "Find a person", "Find a detail", "Tidy up"]
        for label in labels:
            tool = _by_label(root, label)
            assert tool is not None and tool.property("dimmed") is False
            tool.forceActiveFocus()
            app.processEvents()
            rings = [c for c in tool.findChildren(QObject) if c.objectName() == "focusRing"]
            assert rings and rings[0].property("visible") is True, label
        moment = _by_label(root, "Find a moment")
        assert moment.property("selected") is False
        moment.activated.emit()
        app.processEvents()
        assert moment.property("selected") is True
        moment.activated.emit()
        app.processEvents()
        assert moment.property("selected") is False
    finally:
        from semblon.native_shell.host import shutdown_shell

        shutdown_shell(engine)


def _boot_people_with(tmp_path, monkeypatch, items):
    from semblon.application import Application

    calls = []

    def record(name):
        def _inner(*args, **kwargs):
            calls.append((name, args[-1] if name == "merge" else None))
            return {"display_name": "Ada"}
        return _inner

    monkeypatch.setattr(Application, "board", lambda self, run_id=None: {"items": items})
    monkeypatch.setattr("semblon.review_board.merge_clusters", record("merge"))
    monkeypatch.setattr("semblon.review_board.name_cluster", record("name"))
    monkeypatch.setattr("semblon.process.latest_run_id", lambda store, **kwargs: "run-1")
    app, engine, root, bridge = _boot_with_photo(tmp_path, monkeypatch)
    bridge.openPeople()
    _spin(app, 1.0)
    return app, engine, root, bridge, calls


def _faces(prefix, n):
    return [{"media_id": "m1", "face_id": f"{prefix}{i}"} for i in range(n)]


def _ada_board():
    return [
        {"cluster_id": "c1", "face_count": 4, "named": True, "person_names": ["Ada"],
         "members": [dict(m, person_id="p1") for m in _faces("a", 4)]},
        {"cluster_id": "c2", "face_count": 2, "named": False, "person_names": [], "members": _faces("b", 2)},
        {"cluster_id": "c3", "face_count": 1, "named": False, "person_names": [], "members": _faces("c", 1)},
    ]


def test_people_cards_carry_a_fan_of_up_to_three_faces_and_plain_labels(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    app, engine, root, bridge, _calls = _boot_people_with(tmp_path, monkeypatch, _ada_board())
    try:
        rows = {r["subject"]: r for r in bridge.people_model._rows}
        assert rows["c1"]["faceIds"] == ["a0", "a1", "a2"]
        assert rows["c2"]["faceIds"] == ["b0", "b1"]
        assert rows["c1"]["label"] == "Ada"
        assert rows["c2"]["label"] == "Unnamed group"
        words = " ".join(str(c["label"]) for c in bridge.mergeCandidates).lower()
        assert "candidate" not in words
    finally:
        shutdown_shell(engine)


def test_naming_a_group_after_an_existing_person_asks_same_person_or_someone_else(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    app, engine, root, bridge, calls = _boot_people_with(tmp_path, monkeypatch, _ada_board())
    try:
        bridge.selectGroup("c2")
        bridge.decide("name", "c2", "ada")
        assert calls == []
        assert bridge.confirm["open"] and bridge.confirm["yes"] == "Same person" and bridge.confirm["no"] == "Someone else"
        assert "already" in bridge.confirm["title"].lower()
        bridge.confirmDismiss()  # Escape must not decide anything
        assert not bridge.confirm["open"] and calls == []
        bridge.decide("name", "c2", "ada")
        bridge.confirmAccept()
        assert calls == [("merge", ["c1", "c2"])]
        calls.clear()
        bridge.decide("name", "c3", "Ada")
        bridge.confirmDecline()
        assert [c[0] for c in calls] == ["name"]
        # a different name never asks
        calls.clear()
        bridge.decide("name", "c3", "Grace")
        assert not bridge.confirm["open"] and [c[0] for c in calls] == ["name"]
    finally:
        shutdown_shell(engine)


def test_two_named_people_are_never_joined_and_are_flagged_when_names_collide(tmp_path, monkeypatch):
    from semblon.native_shell.host import shutdown_shell

    board = _ada_board()
    board[1] = {"cluster_id": "c2", "face_count": 2, "named": True, "person_names": ["Ada"],
                "members": [dict(m, person_id="p2") for m in _faces("b", 2)]}
    app, engine, root, bridge, calls = _boot_people_with(tmp_path, monkeypatch, board)
    try:
        rows = {r["subject"]: r for r in bridge.people_model._rows}
        assert rows["c1"]["twin"] and rows["c2"]["twin"] and not rows["c3"]["twin"]
        bridge.selectGroup("c2")
        note = bridge.sameAs("c1")
        assert "Rename one" in note and calls == []
    finally:
        shutdown_shell(engine)


def test_same_as_picker_is_searchable_and_keyboard_driven(tmp_path, monkeypatch):
    from PySide6.QtCore import QMetaObject, QObject, Qt
    from PySide6.QtTest import QTest

    from semblon.native_shell.host import shutdown_shell

    app, engine, root, bridge, calls = _boot_people_with(tmp_path, monkeypatch, _ada_board())
    try:
        assert root.findChild(QObject, "mergeTargetFlow") is None
        grid = root.findChild(QObject, "printGrid")
        QMetaObject.invokeMethod(grid, "forceActiveFocus")
        _spin(app, 0.2)
        picker = root.findChild(QObject, "sameAsPicker")
        assert picker.property("shown") is False
        QTest.keyClick(root, Qt.Key.Key_Right)  # second card
        QTest.keyClick(root, Qt.Key.Key_M)
        _spin(app, 0.3)
        assert picker.property("shown") is True
        for ch in "ad":
            QTest.keyClick(root, ch)
        _spin(app, 0.2)
        QTest.keyClick(root, Qt.Key.Key_Return)
        _spin(app, 0.4)
        assert picker.property("shown") is False
        assert calls == [("merge", ["c1", "c2"])]
    finally:
        shutdown_shell(engine)


def test_photo_view_keeps_four_actions_in_view_and_no_debug_text(tmp_path, monkeypatch):
    import re

    from PySide6.QtCore import QObject
    from semblon.native_shell.host import shutdown_shell

    app, engine, root, bridge = _boot_with_photo(tmp_path, monkeypatch)
    try:
        viewer = _open_viewer(app, root, bridge)
        bar = root.findChild(QObject, "findDetail").parent()
        shown = [c.property("label") for c in bar.childItems() if c.property("label") and c.isVisible()]
        assert shown == ["Back to photos", "Previous", "Next", "Find a detail", "More…"]
        menu = root.findChild(QObject, "moreMenu")
        assert menu.property("shown") is False
        # the menu merges the near-duplicates into one plain name each
        labels = [c.property("label") for c in menu.findChildren(QObject) if c.property("label")]
        assert len(labels) == len(set(labels))
        for banned in ("Find similar", "Find more like this photo", "More like this"):
            assert banned not in labels
        assert "Find photos like this one" in labels
        qml = Path("semblon/native_shell/qml/Viewer.qml").read_text(encoding="utf-8")
        assert "searchTimingLabel" not in qml and "searchQualityLabel" not in qml
        for path in Path("semblon/native_shell/qml").glob("*.qml"):
            text = path.read_text(encoding="utf-8")
            assert not re.search(r"\b\d+ ms\b|First look \d|Refined \d", text), path.name
    finally:
        shutdown_shell(engine)


def test_more_menu_opens_from_keyboard_and_the_palette_offers_the_same_actions(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject, Qt
    from PySide6.QtTest import QTest
    from semblon.native_shell.host import shutdown_shell

    app, engine, root, bridge = _boot_with_photo(tmp_path, monkeypatch)
    try:
        _open_viewer(app, root, bridge)
        menu = root.findChild(QObject, "moreMenu")
        QTest.keyClick(root, Qt.Key.Key_Period, Qt.KeyboardModifier.ControlModifier)
        _spin(app, 0.2)
        assert menu.property("shown") is True
        QTest.keyClick(root, Qt.Key.Key_Escape)
        _spin(app, 0.2)
        assert menu.property("shown") is False
        assert bridge.focusId == "m1"  # Escape closed the menu, not the photo
        palette = [c for c in root.findChildren(QObject) if c.property("actions") is not None and c.property("shown") is not None]
        labels = [a["label"] for a in palette[0].property("actions").toVariant()]
        assert "Find photos like this one" in labels and "Find a detail" in labels
    finally:
        shutdown_shell(engine)


def _boot_tidy(tmp_path, monkeypatch, files):
    from PySide6.QtCore import QObject  # noqa: F401
    from semblon.native_shell.adapter import Result
    """Shell with one set of copies. Returns (app, engine, root, bridge)."""
    app, engine, root, bridge = _boot_with_photo(tmp_path, monkeypatch)
    members = [
        {"path": str(f), "media_id": "m%d" % i, "in_library": True} for i, f in enumerate(files)
    ]
    report = {
        "groups": [{"kind": "exact", "members": members, "count": len(members)}],
        "exact_group_count": 1, "near_group_count": 0, "near_status": "AVAILABLE",
    }
    monkeypatch.setattr(
        bridge._adapter, "duplicates",
        lambda: Result("ready", "Duplicates: 1 set of exact copies.", {"report": report}),
    )
    return app, engine, root, bridge


def test_tidy_up_lists_copies_and_never_removes_without_a_confirm(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject
    from semblon.native_shell.host import shutdown_shell
    a, b = tmp_path / "a.jpg", tmp_path / "b.jpg"
    a.write_bytes(b"x" * 200_000); b.write_bytes(b"x" * 200_000)
    app, engine, root, bridge = _boot_tidy(tmp_path, monkeypatch, [a, b])
    try:
        bridge.openTidy()
        _spin(app)
        assert bridge.tidyOpen and len(bridge.tidySets) == 1
        assert bridge.tidySummary == "1 set of exact copies"
        desk = root.findChild(QObject, "tidyDesk")
        assert desk is not None and desk.property("visible") is True
        bridge.keepCopy(0, 0)
        assert bridge.confirm["open"] is True and bridge.confirm["danger"] is True
        assert "Recycle Bin" in bridge.confirm["body"]
        assert a.exists() and b.exists()
        bridge.confirmDecline()
        assert a.exists() and b.exists() and len(bridge.tidySets) == 1
        bridge.keepCopy(0, 0)
        monkeypatch.setattr("PySide6.QtCore.QFile.moveToTrash", staticmethod(lambda p: (Path(p).unlink(), True)[1]))
        bridge.confirmAccept()
        assert a.exists() and not b.exists()
        assert bridge.tidySets == []
        bridge.closeTidy()
        assert not bridge.tidyOpen
    finally:
        shutdown_shell(engine)


def test_tidy_up_wording_has_correct_plurals(tmp_path, monkeypatch):
    import semblon.duplicates as dup
    from semblon.native_shell.adapter import ArchiveAdapter

    def said(exact, near):
        monkeypatch.setattr(dup, "find_integrity_groups", lambda store: {"exact_group_count": exact, "near_group_count": near})
        adapter = ArchiveAdapter.__new__(ArchiveAdapter)
        monkeypatch.setattr(ArchiveAdapter, "store", property(lambda self: tmp_path / "s.db"))
        (tmp_path / "s.db").write_bytes(b"")
        return adapter.duplicates().message

    assert said(6, 1) == "Duplicates: 6 sets of exact copies, 1 set of near copies."
    assert said(1, 0) == "Duplicates: 1 set of exact copies."


def test_scrubber_hides_over_photo_view_and_header_band_is_solid(tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    from semblon.native_shell.host import shutdown_shell

    app, engine, root, bridge = _boot_with_photo(tmp_path, monkeypatch)
    try:
        scrub = root.findChild(QObject, "scrubber")
        assert scrub.property("opacity") == 1
        _open_viewer(app, root, bridge)
        _spin(app, 0.5)
        assert scrub.property("opacity") == 0
        bridge.escape()
        _spin(app, 0.5)
        assert scrub.property("opacity") == 1
        text = Path("semblon/native_shell/qml/Roll.qml").read_text(encoding="utf-8")
        assert "color: Theme.bg" in text
    finally:
        shutdown_shell(engine)


def test_preflight_confirm_is_plain_and_add_on_sizes_are_shown():
    from semblon.native_shell import bridge as b

    cls = b.ShellBridge
    plain = cls._plain_confirm({"name": "Text in photos", "detail": "pinned python package environment == 1.2"})
    low = str(plain).lower()
    for word in ("environment", "package", "python", "=="):
        assert word not in low
    for key in ("object_pack", "region_pack"):
        assert "MB" in str(b._INSTALL_PROMPTS[key])


def test_placeholder_label_font_covers_its_characters():
    from PySide6.QtGui import QFontMetrics
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import load_bundled_fonts

    from PySide6.QtGui import QFont

    QApplication.instance() or QApplication([])
    load_bundled_fonts()
    metrics = QFontMetrics(QFont("Inter"))
    assert all(metrics.inFont(ch) for ch in "IMG 0123456789 x abc")
