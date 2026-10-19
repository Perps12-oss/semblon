"""Search quality profiles tune visual Similar. They stay off identity and duplicates."""

from __future__ import annotations

import numpy as np
import pytest

from semblon.application import Application
from semblon.native_shell.adapter import AdapterError, ArchiveAdapter
from semblon.native_shell.presentation import is_primary_safe_message
from semblon.region_search import remember_and_find
from semblon.search import search_similar_media
from semblon.similarity_profile import resolve_search_quality
from semblon.store import connect, init_db
from semblon.ui_prefs import load_search_quality


def _run(conn) -> None:
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack-a", 2, "l2", "{}", "{}", "x64", "emulated"),
    )


def test_profiles_keep_fast_tighter_than_max():
    fast = resolve_search_quality("fast")
    maximum = resolve_search_quality("nope")
    assert maximum.key == "balanced"
    maximum = resolve_search_quality("max")
    assert fast.patch_score_floor > maximum.patch_score_floor
    assert fast.max_results < maximum.max_results
    assert fast.patch_token_stride > 1
    assert maximum.region_score_floor < fast.region_score_floor


def test_region_colour_fallback_uses_the_profile_floor(tmp_path, monkeypatch):
    captured: dict = {}

    def fake_search_vector(*_args, **kwargs):
        captured.update(kwargs)
        return {
            "status": "NO_RESULT",
            "items": [],
            "modality": "appearance",
            "pack_id": "appearance/rgb8@1",
        }

    monkeypatch.setattr(
        "semblon.region_search.probe_region_pack",
        lambda root=None: (False, "unavailable: region encoder missing"),
    )
    monkeypatch.setattr("semblon.region_search.search_vector", fake_search_vector)
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    conn.execute("INSERT INTO media VALUES ('m1','folder','a.jpg','aaa',32,32,0,1)")
    conn.commit()
    conn.close()
    photo = tmp_path / "a.jpg"
    import cv2

    cv2.imwrite(str(photo), np.full((32, 32, 3), 40, dtype=np.uint8))
    rec = remember_and_find(
        store,
        media_id="m1",
        image_path=photo,
        x=0,
        y=0,
        w=16,
        h=16,
        limit=20,
        search_quality="fast",
    )
    assert captured["min_score"] == pytest.approx(0.88)
    assert captured["limit"] == 6
    assert rec["similar"]["search_profile"] == "fast"
    assert rec["persons"] == 0
    assert rec["wrote_embedding"] is False


def test_whole_image_fast_uses_a_higher_scene_floor(tmp_path, monkeypatch):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    _run(conn)
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','m1',64,64,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o-m1','m1',NULL,NULL,'r1')")
    blob = np.ones(4, dtype=np.float32)
    blob = (blob / np.linalg.norm(blob)).tobytes()
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
           score, payload_json)
           VALUES (?,?,?,?,?,?,?)""",
        ("scene-1", "o-m1", "r1", "clip", "test", 1.0, "{}"),
    )
    conn.execute(
        """INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
           VALUES (?,?,?,?,?,?)""",
        ("scene-1-e", "scene-1", "scene", "region/scene", 4, blob),
    )
    conn.commit()
    conn.close()
    seen: dict = {}

    def fake_search_similar(_store, _item, *, limit, min_score):
        seen["limit"] = limit
        seen["min_score"] = min_score
        return {"status": "NO_RESULT", "items": [], "modality": "scene", "pack_id": "region/scene"}

    monkeypatch.setattr("semblon.search.search_similar", fake_search_similar)
    rec = search_similar_media(store, "m1", limit=20, search_quality="fast")
    assert seen["min_score"] == pytest.approx(0.55)
    assert seen["limit"] == 12
    assert rec["search_profile"] == "fast"


def test_settings_quality_persists_and_stays_product_safe(tmp_path):
    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.close()
    adapter = ArchiveAdapter(Application(store))
    assert adapter.search_quality().data["quality"] == "balanced"
    saved = adapter.set_search_quality("max")
    assert saved.message == "Search quality is Max power."
    assert is_primary_safe_message(saved.message)
    assert load_search_quality(store) == "max"
    again = ArchiveAdapter(Application(store)).search_quality()
    assert again.data["quality"] == "max"
    with pytest.raises(AdapterError):
        adapter.set_search_quality("duplicate")


def test_shell_quality_toggle_updates_the_focus_label(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(tmp_path / "s.sqlite", app=app)
    root = engine.rootObjects()[0]
    bridge = engine._semblon_bridge
    try:
        bridge.toggleSettings()
        app.processEvents()
        assert root.findChild(QObject, "qualityFast") is not None
        assert root.findChild(QObject, "qualityMax") is not None
        assert root.findChild(QObject, "searchQualityFocus") is not None
        bridge.setSearchQuality("fast")
        app.processEvents()
        assert bridge.searchQuality == "fast"
        assert bridge.searchQualityLabel == "Fast mode"
        assert bridge.noticeText == "Search quality is Fast mode."
        assert "duplicate" not in bridge.noticeText.lower()
    finally:
        shutdown_shell(engine)


def test_focus_quality_controls_are_in_the_shell():
    from pathlib import Path

    qml = Path("semblon/native_shell/qml/Shell.qml").read_text(encoding="utf-8")
    assert 'objectName: "qualityFast"' in qml
    assert 'objectName: "qualityMax"' in qml
    assert 'objectName: "searchQualityFocus"' in qml
    assert "setSearchQuality" in qml
    assert "Neither path is a duplicate scan." in qml
