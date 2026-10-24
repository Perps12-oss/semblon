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

    qml = Path("semblon/native_shell/qml/Viewer.qml").read_text(encoding="utf-8")
    settings = Path("semblon/native_shell/qml/SettingsBody.qml").read_text(encoding="utf-8")
    assert 'objectName: "qualityFast"' in settings
    assert 'objectName: "qualityMax"' in settings
    assert 'objectName: "searchQualityFocus"' in qml
    assert 'objectName: "searchPhaseBadge"' in qml
    assert "setSearchQuality" in settings


def _photo_store(tmp_path):
    store = tmp_path / "s.sqlite"
    photo = tmp_path / "a.jpg"
    photo.write_bytes(b"not-decoded")
    conn = connect(store)
    init_db(conn)
    _run(conn)
    conn.execute(
        "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", str(photo), "m1", 32, 32, 0, 1),
    )
    conn.commit()
    conn.close()
    return store, photo


def _phase_hit(media_id: str, phase: str) -> dict:
    return {
        "region": {},
        "similar": {
            "status": "SUCCESS",
            "items": [
                {
                    "media_id": media_id,
                    "score": 0.5,
                    "match_norm": [0.1, 0.2, 0.3, 0.4],
                }
            ],
            "similarity_basis": "Similar look",
            "engine": "dinov2-patch",
            "search_phase": phase,
        },
        "persons": 0,
        "wrote_embedding": False,
    }


def test_balanced_region_search_previews_fast_then_refines(tmp_path, monkeypatch):
    from semblon.user_region import list_user_regions

    calls = []

    def fake_find(_store, **kwargs):
        calls.append(kwargs["search_quality"])
        if kwargs["search_quality"] == "fast":
            return {
                "status": "SUCCESS",
                "items": [{"media_id": "m2", "score": 0.5}],
                "similarity_basis": "Similar look",
            }
        return {
            "status": "SUCCESS",
            "items": [
                {"media_id": "m2", "score": 0.8},
                {"media_id": "m3", "score": 0.7},
            ],
            "similarity_basis": "Similar look",
        }

    monkeypatch.setattr("semblon.region_search.find_similar_region", fake_find)
    store, photo = _photo_store(tmp_path)
    previews = []
    rec = remember_and_find(
        store,
        media_id="m1",
        image_path=photo,
        x=0,
        y=0,
        w=16,
        h=16,
        search_quality="max",
        on_first=previews.append,
    )
    assert calls == ["fast", "max"]
    assert previews[0]["similar"]["search_phase"] == "first"
    assert previews[0]["persons"] == 0
    assert rec["similar"]["search_phase"] == "refined"
    assert [item["media_id"] for item in rec["similar"]["items"]] == ["m2", "m3"]
    assert rec["persons"] == 0
    assert rec["wrote_embedding"] is False
    assert len(list_user_regions(store)) == 1


def test_empty_refine_keeps_the_fast_hits(tmp_path, monkeypatch):
    from semblon.user_region import list_user_regions

    def fake_find(_store, **kwargs):
        if kwargs["search_quality"] == "fast":
            return {
                "status": "SUCCESS",
                "items": [{"media_id": "m2", "score": 0.5}],
                "similarity_basis": "Similar look",
            }
        return {"status": "NO_RESULT", "items": [], "similarity_basis": "Similar look"}

    monkeypatch.setattr("semblon.region_search.find_similar_region", fake_find)
    store, photo = _photo_store(tmp_path)
    rec = remember_and_find(
        store,
        media_id="m1",
        image_path=photo,
        x=0,
        y=0,
        w=16,
        h=16,
        search_quality="balanced",
        on_first=lambda _preview: None,
    )
    assert rec["similar"]["search_phase"] == "kept"
    assert rec["similar"]["items"][0]["media_id"] == "m2"
    assert len(list_user_regions(store)) == 1


def test_fast_region_search_is_a_single_pass(tmp_path, monkeypatch):
    calls = []

    def fake_find(_store, **kwargs):
        calls.append(kwargs["search_quality"])
        return {"status": "NO_RESULT", "items": [], "similarity_basis": "Similar look"}

    monkeypatch.setattr("semblon.region_search.find_similar_region", fake_find)
    store, photo = _photo_store(tmp_path)
    seen = []
    rec = remember_and_find(
        store,
        media_id="m1",
        image_path=photo,
        x=0,
        y=0,
        w=16,
        h=16,
        search_quality="fast",
        on_first=seen.append,
    )
    assert calls == ["fast"]
    assert seen == []
    assert rec["similar"]["search_phase"] == "fast"
    plain = remember_and_find(
        store,
        media_id="m1",
        image_path=photo,
        x=1,
        y=1,
        w=8,
        h=8,
        search_quality="balanced",
    )
    assert calls == ["fast", "balanced"]
    assert "search_phase" not in plain["similar"]


def test_cancel_after_the_first_look_skips_the_refine(tmp_path, monkeypatch):
    calls = []

    def fake_find(_store, **kwargs):
        calls.append(kwargs["search_quality"])
        return {
            "status": "SUCCESS",
            "items": [{"media_id": "m2", "score": 0.4}],
            "similarity_basis": "Similar look",
        }

    monkeypatch.setattr("semblon.region_search.find_similar_region", fake_find)
    store, photo = _photo_store(tmp_path)
    stop = {"on": False}

    def on_first(_preview):
        stop["on"] = True

    rec = remember_and_find(
        store,
        media_id="m1",
        image_path=photo,
        x=0,
        y=0,
        w=16,
        h=16,
        search_quality="max",
        on_first=on_first,
        cancelled=lambda: stop["on"],
    )
    assert calls == ["fast"]
    assert rec["similar"]["search_phase"] == "kept"
    assert rec["similar"]["items"][0]["media_id"] == "m2"
    assert rec["persons"] == 0


def _shell_store(tmp_path):
    store = tmp_path / "shell.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id in ("m1", "m2", "m3"):
        path = tmp_path / f"{media_id}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 100, 80, 0, 1),
        )
    conn.commit()
    conn.close()
    return store


def test_shell_refine_ends_on_the_fuller_pass(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    seen = {"on_first": 0}

    def fake(self, media_id, x, y, w, h, **kwargs):
        on_first = kwargs.get("on_first")
        assert kwargs.get("search_quality") == "balanced"
        if on_first is not None:
            seen["on_first"] += 1
            on_first(_phase_hit("m2", "first"))
        return _phase_hit("m3", "refined")

    monkeypatch.setattr(Application, "remember_and_find_region", fake)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(_shell_store(tmp_path), app=app)
    bridge = engine._semblon_bridge
    phases = []
    bridge.similarChanged.connect(
        lambda: phases.append((bridge.similarPhase, bridge.similarNote, bridge.similarCount))
    )
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        bridge.findSimilar()
        assert seen["on_first"] == 1
        assert bridge.searchBusy is False
        assert bridge.similarPhase == "refined"
        assert bridge.similarPhaseLabel == "Refined"
        assert bridge.similarId(0) == "m3"
        assert any(
            phase == "first" and "still refining" in note
            for phase, note, _count in phases
        )
        root = engine.rootObjects()[0]
        chip = root.findChild(QObject, "searchPhaseBadge")
        assert chip is not None
        assert chip.property("text") == "Refined"
    finally:
        shutdown_shell(engine)


def test_shell_fast_quality_skips_the_preview(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("SEMBLON_SEARCH_SYNC", "1")
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    def fake(self, media_id, x, y, w, h, **kwargs):
        assert kwargs.get("on_first") is None
        assert kwargs.get("search_quality") == "fast"
        return _phase_hit("m2", "fast")

    monkeypatch.setattr(Application, "remember_and_find_region", fake)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(_shell_store(tmp_path), app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.setSearchQuality("fast")
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        bridge.findSimilar()
        assert bridge.similarPhase == "fast"
        assert bridge.similarPhaseLabel == "Fast look"
        assert bridge.similarId(0) == "m2"
        assert "refining" not in bridge.similarNote
    finally:
        shutdown_shell(engine)


def test_cancel_during_refine_keeps_the_first_look(tmp_path, monkeypatch):
    import threading
    import time

    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.delenv("SEMBLON_SEARCH_SYNC", raising=False)
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.host import build_shell, shutdown_shell

    gate = threading.Event()
    first = threading.Event()

    def fake(self, media_id, x, y, w, h, **kwargs):
        on_first = kwargs.get("on_first")
        if on_first is not None:
            on_first(_phase_hit("m2", "first"))
            first.set()
        gate.wait(2)
        return _phase_hit("m3", "refined")

    monkeypatch.setattr(Application, "remember_and_find_region", fake)
    app = QApplication.instance() or QApplication([])
    _app, engine = build_shell(_shell_store(tmp_path), app=app)
    bridge = engine._semblon_bridge
    try:
        bridge.openFocus("m1")
        bridge.setRegion(0.1, 0.2, 0.3, 0.25)
        bridge.findSimilar()
        assert first.wait(2)
        deadline = time.time() + 2
        while bridge.similarPhase != "first" and time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        assert bridge.similarPhase == "first"
        assert bridge.similarId(0) == "m2"
        assert bridge.searchBusy is True
        bridge.cancelSimilar()
        assert bridge.searchBusy is False
        assert bridge.similarPhase == "kept"
        assert bridge.similarPhaseLabel == "Kept the first look"
        assert "kept the first look" in bridge.similarNote
        assert bridge.similarId(0) == "m2"
        gate.set()
        deadline = time.time() + 2
        while time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        assert bridge.similarCount == 1
        assert bridge.similarId(0) == "m2"
        assert bridge.similarPhase == "kept"
    finally:
        gate.set()
        shutdown_shell(engine)
