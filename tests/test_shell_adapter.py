"""Adapter and shell wiring for the blueprint v3 surface. No second archive."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from semblon.application import Application
from semblon.native_shell.adapter import AdapterError, ArchiveAdapter
from semblon.native_shell.events import JOB_STARTED, LIBRARY_CHANGED, ShellEvents
from semblon.native_shell.tokens import DARK, DENSITY_PX, cell_size
from semblon.store import connect, init_db


def _store(tmp_path: Path) -> Path:
    store = tmp_path / "store.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.executemany(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        [
            ("m1", "folder", str(tmp_path / "a.jpg"), "h1", 20, 10, 2_000_000_000, 1),
            ("m2", "folder", str(tmp_path / "b.jpg"), "h2", 20, 10, 1_000_000_000, 1),
        ],
    )
    conn.commit()
    conn.close()
    return store


def test_shell_package_stays_off_identity_engines():
    root = Path(__file__).resolve().parents[1] / "semblon" / "native_shell"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "from semblon.process import process_folder" not in text
        assert "from semblon.ingest" not in text
        assert "insightface" not in text.lower()
        assert "FaceAnalysis" not in text


def test_cli_exposes_shell_as_the_only_gui_command():
    import re
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "semblon", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    help_text = proc.stdout
    assert re.search(r"\bshell\b", help_text)
    assert "review-ui" not in help_text
    assert not re.search(r"^\s+home\s", help_text, flags=re.M)
    assert not re.search(r"^\s+canvas\s", help_text, flags=re.M)


def test_tokens_match_the_blueprint_dark_contract():
    assert DARK["bg0"] == "#0a0b10"
    assert DARK["bg1"] == "#151820"
    assert DARK["bg2"] == "#22252d"
    assert DARK["accent"] == "#4f8cff"
    assert DARK["review"] == "#a15cf5"
    assert cell_size("comfortable") == 220
    assert cell_size("cozy") == 160
    assert cell_size("compact") == 110
    assert DENSITY_PX["cozy"] == 160


def test_event_channel_rejects_unknown_names():
    channel = ShellEvents()
    channel.record(JOB_STARTED, {"resume": False})
    channel.record(LIBRARY_CHANGED, {"count": 1})
    assert [item["name"] for item in channel.snapshot()] == [JOB_STARTED, LIBRARY_CHANGED]
    with pytest.raises(ValueError):
        channel.record("cluster.retuned", {})


def test_browse_and_health_use_real_reads(tmp_path):
    store = _store(tmp_path)
    adapter = ArchiveAdapter(Application(store))
    days = adapter.browse("timeline")
    folders = adapter.browse("folders")
    assert days.state == "ready"
    assert days.data["buckets"]
    assert folders.state == "ready"
    health = adapter.library_health()
    assert health.state in {"ready", "error"}
    assert health.message.startswith("Library check:")
    with pytest.raises(AdapterError):
        adapter.browse("places")


def test_missing_text_and_similar_stay_honest(tmp_path):
    store = _store(tmp_path)
    adapter = ArchiveAdapter(Application(store))
    text = adapter.search("text", "hello")
    assert text.state in {"empty", "unavailable"}
    similar = adapter.similar_media("m1")
    assert similar.state in {"empty", "unavailable"}
    assert similar.data["items"] == []


def test_reset_keeps_the_library_file(tmp_path):
    store = _store(tmp_path)
    before = store.read_bytes()
    adapter = ArchiveAdapter(Application(store))
    result = adapter.reset_defaults()
    assert result.state == "ready"
    assert store.is_file()
    assert store.read_bytes() == before


def test_density_cozy_persists_without_a_schema_column(tmp_path):
    store = _store(tmp_path)
    adapter = ArchiveAdapter(Application(store))
    saved = adapter.set_density("cozy")
    assert saved.data["density"] == "cozy"
    assert saved.data["cell"] == 160
    again = ArchiveAdapter(Application(store)).density()
    assert again.data["density"] == "cozy"


def test_archive_model_filter_does_not_widen_the_window(tmp_path):
    pytest.importorskip("PySide6")
    from semblon.native_shell.model import ArchiveModel

    store = _store(tmp_path)
    app = Application(store)
    model = ArchiveModel(app)
    model.reload()
    calls = []
    real = app.archive.window

    def wrapped(offset, limit):
        calls.append((offset, limit))
        return real(offset, limit)

    app.archive.window = wrapped
    model.set_media_ids(["m2"])
    assert model.rowCount() == 1
    assert model.data(model.index(0, 0), 0) == "b.jpg"
    from PySide6.QtCore import Qt

    assert model.data(model.index(0, 0), Qt.ItemDataRole.UserRole + 1) == "m2"
    assert calls == []


def test_qml_exposes_four_operations_and_hides_places():
    root = Path(__file__).resolve().parents[1] / "semblon" / "native_shell" / "qml"
    qml = (root / "Shell.qml").read_text(encoding="utf-8")
    home = (root / "HomeLaunchpad.qml").read_text(encoding="utf-8")
    sidebar = (root / "ContextSidebar.qml").read_text(encoding="utf-8")
    assert '"rescan"' in qml
    assert '"namedItems"' in qml
    assert '"knowledgePack"' in qml
    assert '"installModel"' in qml
    assert "Named items" in qml
    assert "Knowledge pack" in qml
    assert "Install model" in qml
    assert 'objectName: "namedItemsSheet"' in qml
    assert 'objectName: "similarAction"' in qml
    assert 'objectName: "archiveCard"' in home
    assert 'objectName: "peopleCard"' in home
    assert 'objectName: "discoverCard"' in home
    assert "HomeLaunchpad" in qml
    assert '"homeButton"' in qml
    assert 'showHome' in qml
    assert "ContextSidebar" in qml
    assert 'objectName: "archiveSidebar"' in sidebar
    assert 'objectName: "sidebarMoments"' in sidebar
    assert "Explore your archive" not in sidebar
    assert 'objectName: "archiveBrowseFlick"' in qml
    assert 'text: "Video"' in qml
    assert "facetBar" not in qml
    assert "quickActionRail" not in qml
    assert "librarySnapshot" not in qml
    assert "There is more to remember." in home
    assert "Visual discovery" in home
    assert "Explore all capabilities" in home
    assert "Places" not in qml
    assert "Coming soon" not in home
    assert "coming soon" not in home
    assert 'objectName: "mainSidebar"' not in qml
    assert "timelineRail" not in qml


def test_empty_day_repaints_its_own_canvas():
    qml = (
        Path(__file__).resolve().parents[1]
        / "semblon"
        / "native_shell"
        / "qml"
        / "DayCell.qml"
    ).read_text(encoding="utf-8")
    assert "id: emptyDayOutline" in qml
    assert "emptyDayOutline.requestPaint()" in qml
    assert "parent.requestPaint()" not in qml


def test_named_items_do_not_create_people(tmp_path):
    from semblon.user_region import persist_user_region

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "emulated"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','a.jpg','aaa',200,100,0,1)")
    conn.commit()
    conn.close()
    saved = persist_user_region(store, media_id="m1", x=10, y=10, w=40, h=20, run_id="r1")
    adapter = ArchiveAdapter(Application(store))
    listed = adapter.named_items()
    assert listed.state == "ready"
    assert listed.data["items"][0]["label"] == "Unnamed item"
    named = adapter.name_named_item(saved["item_id"], "old camera")
    assert named.message == "Named items: saved old camera."
    again = adapter.named_items()
    assert again.data["items"][0]["label"] == "old camera"
    conn = connect(store)
    try:
        assert conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0] == 0
    finally:
        conn.close()


def test_pack_and_model_file_stay_local(tmp_path, monkeypatch):
    store = _store(tmp_path)
    adapter = ArchiveAdapter(Application(store))
    pack = tmp_path / "pack.json"
    pack.write_text('{"entries":[{"kind":"landmark","match":{"text":"pier"},"label":"Pier"}]}', encoding="utf-8")
    monkeypatch.delenv("SEMBLON_LKG_PACK", raising=False)
    seen = adapter.inspect_pack(str(pack))
    assert seen.state == "ready"
    assert os.environ["SEMBLON_LKG_PACK"] == str(pack.resolve())
    source = tmp_path / "model.bin"
    source.write_bytes(b"model-bytes")
    dest = tmp_path / "installed.bin"
    installed = adapter.install_model_file(str(source), str(dest))
    assert installed.state == "ready"
    assert dest.read_bytes() == b"model-bytes"
    assert store.is_file()


def test_rescan_forwards_existing_reprocess_flag(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    import threading
    import time

    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.bridge import ShellBridge
    from semblon.native_shell.model import ArchiveModel

    seen = {}
    started = threading.Event()

    def fake_process(folder, **kwargs):
        seen["reprocess"] = kwargs.get("reprocess")
        seen["folder"] = str(folder)
        started.set()
        return {"run_id": "r", "out": None}

    monkeypatch.setattr("semblon.process.process_folder", fake_process)
    app = QApplication.instance() or QApplication([])
    jobs = Application(tmp_path / "s.sqlite")
    bridge = ShellBridge(ArchiveModel(jobs), jobs)
    folder = tmp_path / "photos"
    folder.mkdir()
    bridge._last_folder = folder
    bridge.rescanFolder()
    assert started.wait(3)
    deadline = time.monotonic() + 3
    while jobs.busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.02)
    assert seen["reprocess"] is True
    assert bridge.noticeText.startswith("Rescan:")
    bridge.shutdown()


def test_shell_exposes_facet_settings_and_similar(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    store = _store(tmp_path)
    app = QApplication.instance() or QApplication([])
    _qapp, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    assert root.findChild(QObject, "facetBar") is None
    assert root.findChild(QObject, "quickActionRail") is None
    assert root.findChild(QObject, "librarySnapshot") is None
    assert root.findChild(QObject, "homeButton") is not None
    assert root.findChild(QObject, "settingsButton") is not None
    assert bridge.homeOpen is True
    assert root.findChild(QObject, "emptyState").property("visible") is True
    assert root.findChild(QObject, "searchField").property("visible") is False
    bridge.showLibrary()
    app.processEvents()
    assert bridge.homeOpen is False
    assert root.findChild(QObject, "archiveSidebar") is not None
    assert root.findChild(QObject, "searchField") is not None
    assert root.findChild(QObject, "searchField").property("visible") is True
    assert root.findChild(QObject, "commandField").property("visible") is False
    bridge.toggleSettings()
    app.processEvents()
    sheet = root.findChild(QObject, "settingsSheet")
    assert sheet.property("visible") is True
    assert root.findChild(QObject, "primaryModeButton") is not None
    assert root.findChild(QObject, "atmospherePicker") is not None
    bridge.setFacet("days")
    app.processEvents()
    assert bridge.facet == "timeline"
    assert bridge.buckets
    bridge.selectBucket(bridge.buckets[0]["key"])
    app.processEvents()
    assert bridge.surfaceState == "ready"
    bridge.libraryHealth()
    assert bridge.noticeText.startswith("Library check:")
    bridge.setMode("advanced")
    app.processEvents()
    bridge.showCapabilities()
    assert bridge.noticeText.startswith("Capabilities:")
    bridge.cycleDensity()
    assert "Density is" in bridge.noticeText
    bridge.shutdown()
    root.close()
    shutdown_shell(engine)
    app.processEvents()
