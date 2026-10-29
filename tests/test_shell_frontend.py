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

    import time

    app, _engine, root, bridge = qml_shell
    root.setProperty("settingsOpen", True)
    for _ in range(20):
        app.processEvents()
        time.sleep(0.04)
    panel = root.findChild(QObject, "diagnosticsPanel")
    assert panel is not None
    assert panel.property("visible") is False
    assert bridge.diagnosticsText == ""
    bridge.submitCommand("status")
    assert "mode=" not in bridge.resultText

    button = root.findChild(QObject, "advancedModeButton")
    assert button is not None
    assert button.property("selected") is False

    bridge.setMode("advanced")
    for _ in range(5):
        app.processEvents()
    assert "mode=advanced" in bridge.diagnosticsText
    assert button.property("selected") is True
    assert panel.property("visible") is True
    bridge.submitCommand("status")
    assert "mode=advanced" in bridge.resultText

    bridge.setMode("primary")
    app.processEvents()
    assert panel.property("visible") is False
    assert button.property("selected") is False
    assert "mode=" not in bridge.resultText



def test_chrome_tokens_follow_atmosphere_and_light_is_readable(qml_shell):
    from semblon.atmosphere import ATMOSPHERE_IDS
    from semblon.native_shell.tokens import tokens_for

    app, _engine, _root, bridge = qml_shell
    assert bridge.lightPalette is False

    for atmosphere_id in ATMOSPHERE_IDS:
        bridge.setAtmosphere(atmosphere_id)
        app.processEvents()
        expected = tokens_for(atmosphere_id)
        assert bridge.lightPalette is (atmosphere_id == "light")
        assert bridge.bg2 == expected["bg2"]
        assert bridge.border1 == expected["border1"]
        assert bridge.text3 == expected["text3"]
        assert bridge.accentDim == expected["accentDim"]
        assert bridge.dangerColor == expected["danger"]



def test_qml_has_no_hardcoded_chrome_colors():
    import re
    from pathlib import Path

    # Every colour lives in Theme.qml so both palettes stay in step.
    for path in Path("semblon/native_shell/qml").glob("*.qml"):
        if path.name == "Theme.qml":
            continue
        literals = re.findall(r'"#[0-9a-fA-F]{6,8}"', path.read_text(encoding="utf-8"))
        assert literals == [], path.name


def test_sidebar_scopes_library_by_year_and_folder_and_clears(shell, tmp_path):
    store = tmp_path / "lib.sqlite"
    _seed(store, tmp_path)
    bridge = shell(store)
    assert bridge.count == 4
    assert [row["label"] for row in bridge.yearRows] == ["2017"]
    labels = {row["label"]: row["count"] for row in bridge.folderRows}
    assert labels == {"2017": 2, "2018": 2}

    bridge.selectFolder("2018")
    assert bridge.scopeKind == "folder" and bridge.scopeLabel == "2018"
    assert bridge._model.rowCount() == 2
    assert bridge.noticeText == "Showing 2018."

    bridge.selectYear("2017")
    assert bridge.scopeKind == "year"
    assert bridge._model.rowCount() == 4

    bridge.selectFolder("no-such-folder")
    assert bridge.scopeLabel == "2017"
    assert bridge._model.rowCount() == 4

    bridge.selectFolder("2017")
    assert bridge._model.rowCount() == 2
    bridge.clearScope()
    assert bridge.scopeLabel == "" and bridge._model.rowCount() == 4
    assert bridge.noticeText == "Showing everything."


def test_sidebar_media_kind_splits_photos_and_videos_in_scope(shell, tmp_path):
    from semblon.store import connect

    store = tmp_path / "lib.sqlite"
    _seed(store, tmp_path)
    conn = connect(store)
    conn.execute("UPDATE media SET source_type = 'video' WHERE media_id IN ('m0','m1')")
    conn.commit()
    conn.close()
    bridge = shell(store)
    assert bridge._model.rowCount() == 4

    bridge.setMediaKind("video")
    assert bridge.mediaKind == "video"
    assert bridge._model.rowCount() == 2
    assert {row["label"]: row["count"] for row in bridge.folderRows} == {"2017": 1, "2018": 1}
    assert bridge.noticeText == "Showing videos."

    bridge.selectFolder("2017")
    assert bridge._model.rowCount() == 1
    bridge.setMediaKind("photo")
    assert bridge.scopeLabel == "2017"
    assert bridge._model.rowCount() == 1
    assert {row["label"]: row["count"] for row in bridge.yearRows} == {"2017": 2}

    bridge.clearScope()
    assert bridge._model.rowCount() == 2
    bridge.setMediaKind("all")
    assert bridge._model.rowCount() == 4
    bridge.setMediaKind("bogus")
    assert bridge.mediaKind == "all"


def test_sidebar_notices_stay_product_safe_in_primary(shell, tmp_path):
    store = tmp_path / "lib.sqlite"
    _seed(store, tmp_path)
    bridge = shell(store)
    bridge.selectFolder("2018")
    assert bridge.noticeText == "Showing 2018."
    bridge.clearScope()
    assert "sqlite" not in bridge.noticeText.lower()



def test_the_old_sidebar_is_gone(qml_shell):
    from PySide6.QtCore import QObject

    _app, _engine, root, _bridge = qml_shell
    assert root.findChild(QObject, "archiveSidebar") is None


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


def test_clear_library_drops_the_index_and_keeps_originals(shell, tmp_path, monkeypatch):
    from semblon.atmosphere import ATMOSPHERE_IDS

    store = tmp_path / "clear.sqlite"
    bridge = shell(store)
    _seed(store, tmp_path, n=2)
    photo = tmp_path / "2017" / "0.jpg"
    photo.parent.mkdir(parents=True, exist_ok=True)
    photo.write_bytes(b"original-stays")
    (tmp_path / "2018").mkdir(exist_ok=True)
    (tmp_path / "2018" / "1.jpg").write_bytes(b"original-stays")
    bridge._discovery_file().write_text("{}", encoding="utf-8")
    bridge._keeps_file().write_text('[{"understanding":"Kept find","items":[]}]', encoding="utf-8")
    chosen = next(i for i in ATMOSPHERE_IDS if i != "mica_dark")
    bridge.setAtmosphere(chosen)
    bridge._model.reload()
    bridge.openFocus("m0")
    assert bridge.focusId == "m0"
    assert bridge.keptCount == 1
    bridge.clearLibrary()
    bridge.confirmAccept()
    assert bridge.resultText == "Semblon's list of your photos was cleared. Your original photos were not changed. Add a folder to start again."
    assert bridge._jobs.archive_count() == 0
    assert bridge._model.rowCount() == 0
    assert bridge.focusId == ""
    assert bridge.keptCount == 0
    assert store.is_file()
    assert photo.read_bytes() == b"original-stays"
    assert not bridge._discovery_file().exists()
    assert not bridge._keeps_file().exists()
    assert bridge.atmosphereId == chosen


def test_clear_library_cancel_and_busy_leave_the_index(shell, tmp_path, monkeypatch):
    from types import SimpleNamespace

    store = tmp_path / "keep.sqlite"
    bridge = shell(store)
    _seed(store, tmp_path, n=2)
    bridge._model.reload()
    bridge.clearLibrary()
    bridge.confirmDecline()
    assert bridge.resultText == "Library clear was cancelled."
    assert bridge._jobs.archive_count() == 2

    bridge._jobs.engine._current = SimpleNamespace()
    try:
        bridge.clearLibrary()
        assert bridge.resultText == "A folder is being added. Wait until that finishes."
        assert bridge._jobs.archive_count() == 2
    finally:
        bridge._jobs.engine._current = None


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


def test_memory_facet_keeps_the_media_kind_filter(shell, tmp_path):
    from semblon.store import connect

    store = tmp_path / "lib.sqlite"
    _seed(store, tmp_path)
    conn = connect(store)
    conn.execute("UPDATE media SET source_type = 'video' WHERE media_id = 'm0'")
    conn.commit()
    conn.close()
    bridge = shell(store)
    bridge.setMediaKind("photo")
    assert bridge._model.rowCount() == 3
    bridge.setFacet("folders")
    assert bridge.buckets
    bridge.selectBucket(bridge.buckets[0]["key"])
    bridge.setFacet("memory")
    assert bridge.mediaKind == "photo"
    assert bridge.scopeKind == ""
    assert bridge.facet == "memory"
    assert bridge._model.rowCount() == 3


def test_select_day_narrows_to_that_day(shell, tmp_path):
    store = tmp_path / "lib.sqlite"
    _seed(store, tmp_path)
    bridge = shell(store)
    assert len(bridge.dayRows) == 4
    label = bridge.dayRows[0]["label"]
    bridge.selectDay(label)
    assert bridge.scopeKind == "day"
    assert bridge.scopeLabel == label
    assert bridge._model.rowCount() == 1
    bridge.setFacet("memory")
    assert bridge.scopeKind == ""
    assert bridge._model.rowCount() == 4


def test_video_focus_stays_closed(shell, tmp_path):
    from semblon.store import connect

    store = tmp_path / "lib.sqlite"
    _seed(store, tmp_path)
    conn = connect(store)
    conn.execute("UPDATE media SET source_type = 'video' WHERE media_id = 'm0'")
    conn.commit()
    conn.close()
    bridge = shell(store)
    bridge.openFocus("m0")
    assert bridge.focusId == ""
    bridge.openFocus("m1")
    assert bridge.focusId == "m1"
    from pathlib import Path

    # PySide6-Essentials does not ship QtMultimedia; the import must stay out.
    for path in Path("semblon/native_shell/qml").glob("*.qml"):
        text = path.read_text(encoding="utf-8")
        assert "import QtMultimedia" not in text, path.name
        assert "MediaPlayer {" not in text, path.name


def test_moments_facet_available_in_primary(shell):
    """Context Sidebar Moments uses real browse buckets in Primary mode."""
    bridge = shell()
    bridge.setFacet("moments")
    assert bridge.facet == "moments"


def _run_job(app, bridge, folder, monkeypatch, behaviour):
    import time

    monkeypatch.setattr("semblon.process.process_folder", behaviour)
    bridge._start_ingest(folder)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        app.processEvents()
        if not bridge._jobs.busy and bridge._events.last("job.cancelled") or bridge._events.last("job.failed"):
            break
        time.sleep(0.02)
    for _ in range(5):
        app.processEvents()
        time.sleep(0.02)


def test_empty_state_guides_first_run_and_recovery(qml_shell, tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    from semblon.process import ProcessCancelled

    app, _engine, root, bridge = qml_shell
    empty = root.findChild(QObject, "emptyState")
    assert empty.property("visible") is True
    assert root.findChild(QObject, "emptyResume").property("visible") is False
    assert root.findChild(QObject, "emptyStatus").property("visible") is False

    folder = tmp_path / "photos"
    folder.mkdir()

    def cancelled(folder, **kwargs):
        raise ProcessCancelled("cancelled", run_id="r")

    _run_job(app, bridge, folder, monkeypatch, cancelled)
    assert bridge.canResume
    assert root.findChild(QObject, "emptyResume").property("visible") is True
    assert root.findChild(QObject, "emptyStatus").property("visible") is True


def test_focus_navigation_and_stale_detail_after_library_change(shell, tmp_path):
    from semblon.store import connect

    store = tmp_path / "focus.sqlite"
    _seed(store, tmp_path)
    bridge = shell(store)
    bridge.openIndex(0)
    first = bridge.focusId
    assert first
    assert bridge.focusName
    bridge.focusNext()
    second = bridge.focusId
    assert second and second != first
    bridge.focusPrev()
    assert bridge.focusId == first
    assert bridge.path_for("missing") is None
    assert bridge.path_for(first)

    conn = connect(store)
    conn.execute("DELETE FROM media WHERE media_id = ?", (first,))
    conn.commit()
    conn.close()
    bridge._refresh_library()
    assert bridge.count == 3
    assert bridge.focusId != first
    assert bridge.focusName != "" or bridge.focusId == ""


def test_review_actions_give_safe_feedback_and_keep_selection_stable(shell):
    from semblon.native_shell.presentation import is_primary_safe_message

    bridge = shell()
    bridge.openPeople()
    assert bridge.peopleOpen
    for call in (bridge.mergeSelectedGroup, bridge.splitSelectedFaces):
        note = call()
        assert is_primary_safe_message(note), note
    bridge.selectGroup("does-not-exist")
    assert bridge.selectedSubject == ""
    assert is_primary_safe_message(bridge.peopleNote), bridge.peopleNote
    bridge.toggleSplitFace("f-missing")
    assert bridge.splitSelectionCount in (0, 1)
    bridge.clearSplitSelection()
    assert bridge.splitSelectionCount == 0
    bridge.closePeople()
    assert not bridge.peopleOpen


def test_similar_without_focus_is_honest_and_product_safe(shell):
    bridge = shell()
    bridge.findSimilar()
    assert bridge.similarState == "unavailable"
    assert bridge.similarNote == "Open a photo first."
    bridge.findSimilarWhole()
    assert bridge.similarCount == 0
    assert "sqlite" not in bridge.similarNote.lower()


def test_every_qml_action_maps_to_a_real_bridge_slot_or_property():
    import re

    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.host import QML

    source = QML.read_text(encoding="utf-8")
    called = set(re.findall(r"\b(?:shellApi|shell)\.([A-Za-z_]\w*)\(", source))
    used = set(re.findall(r"\b(?:shellApi|shell)\.([A-Za-z_]\w*)\b(?!\()", source))
    missing = sorted(name for name in called | used if not hasattr(ShellBridge, name))
    assert not missing, missing



def test_settings_body_calls_resolve_to_bridge_slots():
    import re
    from pathlib import Path

    from semblon.native_shell.bridge import ShellBridge

    source = Path("semblon/native_shell/qml/SettingsBody.qml").read_text(encoding="utf-8")
    called = set(re.findall(r"shell\.(\w+)\(", source))
    assert called
    assert {name for name in called if not hasattr(ShellBridge, name)} == set()


def test_windows_journey_launch_ingest_browse_search_theme_restart_recover(tmp_path, monkeypatch):
    cv2 = pytest.importorskip("cv2")
    import sys
    import time
    from types import SimpleNamespace

    import numpy as np
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.atmosphere import ATMOSPHERE_IDS
    from semblon.native_shell.host import build_shell, shutdown_shell

    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setitem(sys.modules, "insightface", SimpleNamespace(__version__="0.test"))
    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(__version__="0.test", get_available_providers=lambda: ["CPUExecutionProvider"]),
    )
    monkeypatch.setattr("semblon.ingest.load_app", lambda *_a, **_k: object())
    monkeypatch.setattr("semblon.ingest.embed_bgr", lambda *_a, **_k: [])

    def wait_idle(app, bridge):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            app.processEvents()
            if not bridge._jobs.busy:
                break
            time.sleep(0.05)
        for _ in range(10):
            app.processEvents()
            time.sleep(0.02)

    folder = tmp_path / "photos"
    folder.mkdir()
    for name, colour in (("a.png", (20, 20, 220)), ("b.png", (220, 20, 20))):
        image = np.zeros((80, 120, 3), np.uint8)
        image[:, :] = colour
        assert cv2.imwrite(str(folder / name), image)

    store = tmp_path / "journey.sqlite"
    app = QApplication.instance() or QApplication([])
    _qapp, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    try:
        assert bridge.empty and bridge.primaryMode and bridge.atmosphereId == "mica_dark"
        assert root.findChild(QObject, "emptyState").property("visible") is True
        assert root.findChild(QObject, "homeButton") is None

        bridge._start_ingest(tmp_path / "missing-folder")
        wait_idle(app, bridge)
        assert bridge.empty
        assert "traceback" not in (bridge.noticeText + bridge.resultText).lower()

        bridge._start_ingest(folder)
        wait_idle(app, bridge)
        assert not bridge.empty
        assert bridge.count == 2
        assert bridge.photoCount == 2
        assert root.findChild(QObject, "emptyState").property("visible") is False
        assert root.findChild(QObject, "rollGrid") is not None

        bridge.showLibrary()
        app.processEvents()
        bridge.showHome()
        bridge.showLibrary()
        app.processEvents()
        bridge.setFacet("folders")
        assert bridge.buckets
        bridge.setFacet("memory")
        assert bridge.count == 2
        bridge.openIndex(0)
        assert bridge.focusId
        bridge.escape()
        bridge.submitCommand("nobody")
        assert "sqlite" not in bridge.resultText.lower()

        chosen = next(i for i in ATMOSPHERE_IDS if i != "mica_dark")
        bridge.setAtmosphere(chosen)
    finally:
        shutdown_shell(engine)

    _qapp, engine = build_shell(store, app=app)
    try:
        again = engine._semblon_bridge
        assert again.atmosphereId == chosen
        assert again.count == 2
        assert not again.empty
    finally:
        shutdown_shell(engine)


def test_discovery_result_preview_does_not_mutate_bridge_focus_or_search(qml_shell):
    from PySide6.QtCore import QObject

    app, _engine, root, bridge = qml_shell
    viewer = root.findChild(QObject, "viewer")
    strip = root.findChild(QObject, "similarStrip")
    return_tool = root.findChild(QObject, "returnFromPreview")
    open_tool = root.findChild(QObject, "previewThisPhoto")
    assert viewer is not None and strip is not None
    assert return_tool is not None and open_tool is not None

    original_focus = bridge.focusId
    original_state = bridge.similarState
    original_count = bridge.similarCount

    viewer.setProperty("previewId", "match-preview")
    viewer.setProperty("loupeOn", True)
    app.processEvents()

    assert viewer.property("previewId") == "match-preview"
    assert bridge.focusId == original_focus
    assert bridge.similarState == original_state
    assert bridge.similarCount == original_count
    assert strip.property("visible") is True
    assert return_tool.property("visible") is True
    assert open_tool.property("visible") is True

    viewer.setProperty("previewId", "")
    app.processEvents()
    assert bridge.focusId == original_focus
    assert bridge.similarState == original_state
    assert bridge.similarCount == original_count


def test_lens_recovery_controls_call_existing_slots(qml_shell):
    """Loaded window reaches the slots that were already implemented."""
    from pathlib import Path

    from PySide6.QtCore import QObject

    app, _engine, root, bridge = qml_shell
    qml = Path("semblon/native_shell/qml")
    viewer = (qml / "Viewer.qml").read_text(encoding="utf-8")
    light = (qml / "LightTable.qml").read_text(encoding="utf-8")
    people = (qml / "People.qml").read_text(encoding="utf-8")
    settings = (qml / "SettingsBody.qml").read_text(encoding="utf-8")
    table = (qml / "Table.qml").read_text(encoding="utf-8")
    assert 'objectName: "backDiscovery"' in viewer and "shell.backToDiscovery" in viewer
    assert "shell.canBackDiscovery" in viewer
    assert 'objectName: "seeThisDay"' in viewer and "shell.showDayAroundFocus" in viewer
    assert 'label: "Find by date"' in light
    assert "momentsRequested" in light and "shell.openUnresolvedInbox" in light
    assert "shell.clearPersonFieldFilter" in light and 'shell.setFacet("memory")' in light
    assert "shell.showSelectedPersonOnly" in people
    assert "shell.browseSelectedPersonInTime" in people
    assert 'objectName: "reopenLastFind"' in settings and "lastFindRequested" in settings
    assert "shell.reopenLastVisualSearch" in table
    assert 'shell.setFacet("moments")' in table and "shell.selectBucket" in table
    assert 'objectName: "momentsSheet"' in table
    for path in qml.glob("*.qml"):
        text = path.read_text(encoding="utf-8")
        assert "push_lens" not in text
        assert "DiscoverySession" not in text
        assert "CompareSession" not in text
        assert "lens_home" not in text

    app.processEvents()
    for name in (
        "backDiscovery",
        "seeThisDay",
        "reopenLastFind",
        "onlyTheirPhotos",
        "momentsButton",
        "reviewOverlooked",
        "showEverything",
        "momentsSheet",
    ):
        assert root.findChild(QObject, name) is not None, name

    root.findChild(QObject, "momentsButton").activated.emit()
    app.processEvents()
    assert bridge.facet == "moments"
    assert root.findChild(QObject, "momentsSheet").property("open") is True
    root.findChild(QObject, "showEverything").activated.emit()
    app.processEvents()
    assert bridge.facet == "memory"
    assert root.findChild(QObject, "momentsSheet").property("open") is False

    root.setProperty("settingsOpen", True)
    root.findChild(QObject, "reopenLastFind").activated.emit()
    app.processEvents()
    assert root.property("settingsOpen") is False
    assert "no saved search yet" in bridge.noticeText

    root.findChild(QObject, "seeThisDay").activated.emit()
    app.processEvents()
    assert bridge.scopeKind != "day"
    assert "No date on file" in bridge.resultText

    root.findChild(QObject, "reviewOverlooked").activated.emit()
    app.processEvents()
    assert bridge.peopleOpen is True


def test_discovery_preview_has_explicit_navigation_and_escape_return():
    from pathlib import Path

    qml = Path("semblon/native_shell/qml/Viewer.qml").read_text(encoding="utf-8")
    assert "function returnFromPreview()" in qml
    assert "function openPreviewAsFocus()" in qml
    assert "shell.openDiscoveryHit(target)" in qml
    assert 'Keys.onEscapePressed: {\n        if (previewId !== "") returnFromPreview()' in qml
    assert 'onClicked: { viewer.previewId = mediaId; viewer.forceActiveFocus() }' in qml
