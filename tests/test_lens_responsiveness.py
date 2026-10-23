"""Lens stays responsive and reuses work. Scores stay late-interaction max-sim."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest


def _naive_scores(query, groups, *, token_floor, score_floor, coverage_floor):
    scores = []
    for group in groups:
        sims = query @ group["matrix"].T
        maxes = sims.max(axis=1)
        score = float(maxes.mean())
        coverage = float((maxes >= token_floor).mean())
        above = score >= score_floor and coverage >= coverage_floor
        scores.append((group["media_id"], score, above, sims.argmax(axis=1).tolist()))
    return scores


def test_chunked_patch_scores_match_per_photo_max_sim():
    from semblon.region_search import score_patch_groups

    rng = np.random.default_rng(7)
    query = rng.standard_normal((12, 8)).astype(np.float32)
    query /= np.linalg.norm(query, axis=1, keepdims=True)
    groups = []
    for index in range(5):
        matrix = rng.standard_normal((17, 8)).astype(np.float32)
        matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
        groups.append(
            {
                "media_id": f"m{index}",
                "width": 100,
                "height": 80,
                "matrix": matrix,
                "boxes": [(float(i), 0.0, float(i + 4), 8.0) for i in range(17)],
            }
        )
    naive = _naive_scores(query, groups, token_floor=0.0, score_floor=0.0, coverage_floor=0.0)
    items = score_patch_groups(
        query,
        groups,
        token_floor=0.0,
        score_floor=0.0,
        coverage_floor=0.0,
        limit=10,
    )
    by_id = {item["media_id"]: item for item in items}
    assert len(by_id) == len(naive)
    for media_id, score, above, _winners in naive:
        assert by_id[media_id]["above_floor"] is above
        assert by_id[media_id]["score"] == pytest.approx(score, abs=1e-5)


def test_patch_gallery_is_loaded_once(tmp_path):
    from semblon.region_search import clear_patch_gallery_cache, load_patch_groups, patch_gallery_loads
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id,
           embedding_dim, embedding_norm, config_json, runtime_json, arch, execution)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        ("r1", "t", "0.0.1", "pack", 4, "l2", "{}", "{}", "x64", "emulated"),
    )
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','aaa',20,20,0,1)")
    conn.execute("INSERT INTO observations VALUES ('o1','m1',NULL,NULL,'r1')")
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider,
           bbox_x1, bbox_y1, bbox_x2, bbox_y2, payload_json)
           VALUES ('i1','o1','r1','clip','dinov2-vits14',0,0,4,4,'{}')"""
    )
    blob = np.ones(4, dtype=np.float32).tobytes()
    conn.execute(
        """INSERT INTO embeddings(embedding_id, item_id, modality, pack_id, embedding_dim, embedding)
           VALUES ('e1','i1','region_patch','pack-a',4,?)""",
        (blob,),
    )
    conn.commit()
    clear_patch_gallery_cache()
    reader = connect(store)
    first, saw = load_patch_groups(store, reader, "pack-a", 4)
    second, saw_again = load_patch_groups(store, reader, "pack-a", 4)
    reader.close()
    conn.close()
    assert saw is True and saw_again is True
    assert patch_gallery_loads() == 1
    assert first[0]["media_id"] == "m1"
    assert second[0]["matrix"].shape == (1, 4)
    clear_patch_gallery_cache()


def test_repeated_crop_reuses_the_decoded_frame(tmp_path, monkeypatch):
    import cv2

    from semblon.region_search import clear_frame_cache, crop_bgr
    from semblon.temporal import _decode_still

    path = tmp_path / "plain.png"
    raw = np.zeros((30, 40, 3), dtype=np.uint8)
    raw[:, :20] = (0, 0, 255)
    cv2.imwrite(str(path), raw)
    calls = {"n": 0}

    def counted(file):
        calls["n"] += 1
        return _decode_still(file)

    monkeypatch.setattr("semblon.temporal._decode_still", counted)
    clear_frame_cache()
    first = crop_bgr(path, 0, 0, 8, 8)
    second = crop_bgr(path, 4, 4, 8, 8)
    assert first.shape == (8, 8, 3)
    assert second.shape == (8, 8, 3)
    assert calls["n"] == 1
    clear_frame_cache()


def test_archive_reads_share_one_connection(tmp_path, monkeypatch):
    from semblon.archive_session import ArchiveSession
    from semblon.store import connect, connect_readonly, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.execute("INSERT INTO media VALUES ('m1','folder','/a.jpg','abc',10,12,0,1)")
    conn.commit()
    conn.close()
    opens = {"n": 0}

    def wrapped(path):
        opens["n"] += 1
        return connect_readonly(path)

    monkeypatch.setattr("semblon.archive_session.connect_readonly", wrapped)
    session = ArchiveSession(store)
    assert session.media("m1").path == "/a.jpg"
    assert session.media("m1").width == 10
    assert session.count() == 1
    assert len(session.window(0, 10)) == 1
    assert opens["n"] == 1
    session.invalidate_reads()
    assert session.count() == 1
    assert opens["n"] == 2


def test_missing_region_pack_is_remembered(tmp_path):
    from semblon.region_encoder import probe_region_pack, reset_session_for_tests

    reset_session_for_tests()
    try:
        first = probe_region_pack(tmp_path)
        second = probe_region_pack(tmp_path)
        assert first[0] is False
        assert second == first
        assert "missing" in (second[1] or "")
    finally:
        reset_session_for_tests()


def test_indexing_waits_until_an_interactive_forward_finishes():
    from semblon.region_encoder import _lane_enter, _lane_leave, reset_session_for_tests

    reset_session_for_tests()
    started = threading.Event()

    def hold() -> None:
        _lane_enter(interactive=True, cancelled=None, yield_budget=None)
        try:
            started.set()
            time.sleep(0.25)
        finally:
            _lane_leave(interactive=True)

    worker = threading.Thread(target=hold)
    worker.start()
    assert started.wait(2)
    began = time.perf_counter()
    try:
        _lane_enter(interactive=False, cancelled=None, yield_budget=[0.0])
        waited = time.perf_counter() - began
        _lane_leave(interactive=False)
    finally:
        worker.join(2)
        reset_session_for_tests()
    assert waited >= 0.15


def test_repeated_thumbnail_requests_decode_once(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEventLoop, QSize, QTimer
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    from semblon.native_shell.images import (
        ArchiveImageProvider,
        image_decode_count,
        reset_image_cache,
    )

    app = QApplication.instance() or QApplication([])
    path = tmp_path / "a.png"
    image = QImage(320, 200, QImage.Format.Format_RGB32)
    image.fill(0x336699)
    assert image.save(str(path))
    reset_image_cache()
    provider = ArchiveImageProvider(lambda _media_id: str(path))

    def fetch():
        response = provider.requestImageResponse("t/m1", QSize(160, 120))
        loop = QEventLoop()
        response.finished.connect(loop.quit)
        QTimer.singleShot(2000, loop.quit)
        loop.exec()
        app.processEvents()
        return response

    first = fetch()
    assert image_decode_count() == 1
    assert not first._image.isNull()
    second = fetch()
    assert image_decode_count() == 1
    assert second._image.width() == first._image.width()
    reset_image_cache()


def _png(path):
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * 16)


def _shell(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from semblon.application import Application
    from semblon.native_shell.host import build_shell
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    for media_id, name in (("m1", "a.png"), ("m2", "b.png")):
        path = tmp_path / name
        _png(path)
        conn.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            (media_id, "folder", str(path), media_id, 100, 80, 0, 1),
        )
    conn.commit()
    conn.close()
    app = QApplication.instance() or QApplication([])
    _jobs, engine = build_shell(store, app=app)
    bridge = engine._semblon_bridge
    monkeypatch.setattr(
        Application,
        "remember_and_find_region",
        lambda self, media_id, x, y, w, h, **kwargs: _hit("m2"),
    )
    bridge.openFocus("m1")
    bridge.setRegion(0.1, 0.2, 0.3, 0.25)
    return app, engine, bridge


def _hit(media_id: str):
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
        },
        "persons": 0,
        "wrote_embedding": False,
    }


def test_drawing_stays_responsive_while_search_runs(tmp_path, monkeypatch):
    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    monkeypatch.delenv("SEMBLON_SEARCH_SYNC", raising=False)
    gate = threading.Event()
    app, engine, bridge = _shell(tmp_path, monkeypatch)

    def slow(self, media_id, x, y, w, h, **kwargs):
        gate.wait(2)
        return _hit("m2")

    monkeypatch.setattr(Application, "remember_and_find_region", slow)
    try:
        bridge.findSimilar()
        assert bridge.searchBusy is True
        began = time.perf_counter()
        bridge.setRegion(0.2, 0.2, 0.2, 0.2)
        assert time.perf_counter() - began < 0.2
        assert bridge.selectionW == pytest.approx(0.2)
    finally:
        gate.set()
        shutdown_shell(engine)
        app.processEvents()


def test_new_search_keeps_previous_matches_until_it_finishes(tmp_path, monkeypatch):
    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    monkeypatch.delenv("SEMBLON_SEARCH_SYNC", raising=False)
    gate = threading.Event()
    app, engine, bridge = _shell(tmp_path, monkeypatch)
    calls = {"n": 0}

    def paced(self, media_id, x, y, w, h, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _hit("m2")
        gate.wait(2)
        return _hit("m1")

    monkeypatch.setattr(Application, "remember_and_find_region", paced)
    try:
        bridge.findSimilar()
        deadline = time.time() + 2
        while bridge.searchBusy and time.time() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert bridge.similarId(0) == "m2"
        bridge.findSimilar()
        assert bridge.searchBusy is True
        assert bridge.similarState == "loading"
        assert bridge.similarId(0) == "m2"
        gate.set()
        deadline = time.time() + 2
        while bridge.searchBusy and time.time() < deadline:
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()
        assert bridge.similarId(0) == "m1"
    finally:
        gate.set()
        shutdown_shell(engine)


def test_search_worker_exception_clears_busy(tmp_path, monkeypatch):
    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    app, engine, bridge = _shell(tmp_path, monkeypatch)

    def broken(self, media_id, x, y, w, h, **kwargs):
        raise RuntimeError("encoder blew up")

    monkeypatch.setattr(Application, "remember_and_find_region", broken)
    try:
        bridge.findSimilar()
        assert bridge.searchBusy is False
        assert bridge.similarState == "error"
        assert bridge.similarCount == 0
    finally:
        shutdown_shell(engine)


def test_indexed_region_search_does_not_encode_the_crop(tmp_path, monkeypatch):
    from semblon.region_search import roi_query_tokens, search_patches
    from semblon.store import connect, init_db

    store = tmp_path / "s.sqlite"
    conn = connect(store)
    init_db(conn)
    conn.close()
    fine = np.array([1, 0, 0, 0], dtype=np.float32)
    coarse = np.array([0, 0, 1, 0], dtype=np.float32)
    other = np.array([0, 1, 0, 0], dtype=np.float32)
    groups = [
        {
            "media_id": "m1",
            "width": 100,
            "height": 80,
            "matrix": np.stack([fine, fine, fine, fine, coarse]),
            "boxes": [(10, 10, 18, 18), (18, 10, 26, 18), (10, 18, 18, 26), (18, 18, 26, 26), (0, 0, 80, 60)],
        },
        {
            "media_id": "m2",
            "width": 100,
            "height": 80,
            "matrix": other.reshape(1, 4),
            "boxes": [(10, 10, 18, 18)],
        },
    ]
    monkeypatch.setattr("semblon.region_search.load_patch_groups", lambda *args, **kwargs: (groups, True))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("indexed search encoded the crop")

    monkeypatch.setattr("semblon.region_search.content_patch_records", forbidden)
    result = search_patches(
        store,
        np.zeros((8, 8, 3), dtype=np.uint8),
        exclude_media_id="m1",
        query_box=(8, 8, 20, 20),
        token_floor=0.0,
        score_floor=0.0,
        coverage_floor=0.0,
    )
    assert result["query_source"] == "index"
    assert result["status"] == "SUCCESS"
    assert result["items"][0]["media_id"] == "m2"
    tokens = roi_query_tokens(groups, "m1", (8, 8, 20, 20))
    assert tokens is not None
    assert tokens.shape == (4, 4)


def test_batched_forward_matches_single_image_tokens():
    from semblon.region_encoder import content_patch_records, encode_images, probe_region_pack

    ready, _note = probe_region_pack()
    if not ready:
        pytest.skip("region pack is not installed")
    rng = np.random.default_rng(3)
    images = [
        rng.integers(0, 255, size=(180, 240, 3), dtype=np.uint8),
        rng.integers(0, 255, size=(90, 140, 3), dtype=np.uint8),
    ]
    batched = encode_images(images)
    assert len(batched) == 2
    for image, hidden in zip(images, batched):
        _cls, records = content_patch_records(image)
        solo = hidden[1:]
        # Letterbox drops padding tokens. Compare the content rows by L2 cosine of CLS.
        assert hidden.shape[-1] == 384
        assert records
        cls = hidden[0]
        cls = cls / max(float(np.linalg.norm(cls)), 1e-8)
        stored = np.frombuffer(records[0]["blob"], dtype=np.float32)
        # First record is a patch, not CLS. Compare CLS bytes via a second split.
        from semblon.region_encoder import _split_content_patches

        scene, patches = _split_content_patches(image, hidden)
        assert len(patches) == len(records)
        left = np.frombuffer(scene, dtype=np.float32)
        right = np.frombuffer(_cls, dtype=np.float32)
        assert np.allclose(left, right, atol=1e-4)
        for got, expected in zip(patches, records):
            assert np.allclose(
                np.frombuffer(got["blob"], dtype=np.float32),
                np.frombuffer(expected["blob"], dtype=np.float32),
                atol=1e-4,
            )
            assert got["bbox"] == expected["bbox"]
        assert stored.shape == (384,)


def test_shutdown_drops_a_late_search_result(tmp_path, monkeypatch):
    from semblon.application import Application
    from semblon.native_shell.host import shutdown_shell

    monkeypatch.delenv("SEMBLON_SEARCH_SYNC", raising=False)
    gate = threading.Event()
    app, engine, bridge = _shell(tmp_path, monkeypatch)

    def slow(self, media_id, x, y, w, h, **kwargs):
        gate.wait(2)
        return _hit("m2")

    monkeypatch.setattr(Application, "remember_and_find_region", slow)
    try:
        bridge.findSimilar()
        assert bridge.searchBusy is True
        gate.set()
        bridge.shutdown()
        app.processEvents()
        assert bridge.similarCount == 0
    finally:
        gate.set()
        shutdown_shell(engine)
