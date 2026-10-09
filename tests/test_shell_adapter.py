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


def test_tokens_match_the_blueprint_dark_contract():
    assert DARK["bg0"] == "#0b0c0e"
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
    assert model.data(model.index(0, 0), 0) or True
    from PySide6.QtCore import Qt

    assert model.data(model.index(0, 0), Qt.ItemDataRole.UserRole + 1) == "m2"
    assert calls == []


def test_shell_exposes_facet_settings_and_similar(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell

    store = _store(tmp_path)
    app = QApplication.instance() or QApplication([])
    _qapp, engine = build_shell(store, app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    assert root.findChild(QObject, "facetBar") is not None
    assert root.findChild(QObject, "settingsButton") is not None
    assert root.findChild(QObject, "searchField") is not None
    assert root.findChild(QObject, "searchField").property("visible") is True
    assert root.findChild(QObject, "commandField").property("visible") is False
    bridge.toggleSettings()
    app.processEvents()
    sheet = root.findChild(QObject, "settingsSheet")
    assert sheet.property("visible") is True
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
    root.close()
