"""Category backfill is isolated, resumable, and does not assign identity."""

from __future__ import annotations

import numpy as np

from semblon.category_backfill import (
    CATEGORIES,
    ProviderProbe,
    coverage_report,
    run_category_backfill,
)
from semblon.store import SCHEMA_VERSION, apply_migrations, connect, init_db


def _probe(version="v1", *, objects=True, words=True, people=True, regions=True):
    def probe(category):
        flags = {"people": people, "objects": objects, "regions": regions, "words": words}
        if not flags[category]:
            return ProviderProbe(False, category, "", f"{category} is not available on this computer.")
        return ProviderProbe(True, category, version, "")

    return probe


def _store(tmp_path, names=("a.jpg", "b.jpg")):
    store = tmp_path / "library.sqlite"
    conn = connect(store)
    init_db(conn)
    for name in names:
        path = tmp_path / name
        if name.endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
            path.write_bytes(b"still")
        conn.execute(
            "INSERT INTO media(media_id, source_type, path, sha256, width, height, mtime_ns, byte_size) VALUES (?,?,?,?,?,?,?,?)",
            (name, "video" if name.endswith(".mp4") else "folder", str(path), "sha-" + name, 8, 8, 1, 5),
        )
    conn.commit()
    conn.close()
    return store


def _install(monkeypatch, *, detect=None, objects=None, regions=None, words=None, decode=None, probe=None):
    import semblon.category_backfill as backfill

    calls = {name: 0 for name in ("people", "objects", "regions", "words", "contour", "cluster", "ingest")}

    def people_detect(img):
        calls["people"] += 1
        if detect is not None:
            return detect(img)
        return []

    def objects_detect(img):
        calls["objects"] += 1
        if objects is not None:
            return objects(img)
        return []

    def regions_prepare(img, *, depth, cancelled):
        calls["regions"] += 1
        if regions is not None:
            return regions(img, depth=depth, cancelled=cancelled)
        return {"counts": {}, "records": [], "skip_persist": False}

    def words_ocr(img):
        calls["words"] += 1
        if words is not None:
            return words(img)
        return {"text": "", "score": 0.0, "words": []}

    monkeypatch.setattr(backfill, "people_detect", people_detect)
    monkeypatch.setattr(backfill, "objects_detect", objects_detect)
    monkeypatch.setattr(backfill, "regions_prepare", regions_prepare)
    monkeypatch.setattr(backfill, "words_ocr", words_ocr)
    monkeypatch.setattr(backfill, "probe_category", probe or _probe())
    monkeypatch.setattr(backfill, "decode_image", decode or (lambda path: object()))

    def boom(*_a, **_k):
        calls["ingest"] += 1
        raise AssertionError("broad ingest must not run")

    monkeypatch.setattr("semblon.process.process_folder", boom)
    monkeypatch.setattr("semblon.observers.contour_objects", lambda *_a, **_k: calls.__setitem__("contour", calls["contour"] + 1) or [])
    monkeypatch.setattr("semblon.cluster.cluster_run", lambda *_a, **_k: calls.__setitem__("cluster", calls["cluster"] + 1))
    return calls


def _completed(store, category):
    conn = connect(store)
    try:
        rows = conn.execute(
            "SELECT state, outcome, frame_done, detail_done, provider_version FROM category_coverage WHERE category=?",
            (category,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def test_provider_isolation(tmp_path, monkeypatch):
    store = _store(tmp_path)
    calls = _install(monkeypatch)
    for category in CATEGORIES:
        run_category_backfill(store, category)
    assert calls["ingest"] == 0
    assert calls["contour"] == 0
    assert calls["cluster"] == 0
    assert calls["people"] == 2
    assert calls["objects"] == 2
    assert calls["words"] == 2
    assert calls["regions"] == 4  # frame + detail for two photos
    people = coverage_report(store, "people")
    objects = coverage_report(store, "objects")
    assert people["completed"] == 2
    assert objects["completed"] == 2
    assert people["completed"] == objects["completed"]
    # Completing every category still leaves each count on its own rows.
    conn = connect(store)
    try:
        paired = conn.execute(
            """SELECT media_id, category, state FROM category_coverage
               WHERE state='completed'"""
        ).fetchall()
    finally:
        conn.close()
    by_cat = {}
    for row in paired:
        by_cat.setdefault(row["category"], 0)
        by_cat[row["category"]] += 1
    assert by_cat == {name: 2 for name in CATEGORIES}


def test_people_does_not_assign_identity(tmp_path, monkeypatch):
    store = _store(tmp_path, ("a.jpg",))
    vector = np.ones(128, dtype=np.float32)
    vector /= np.linalg.norm(vector)

    def detect(_img):
        return [{
            "bbox": (1.0, 2.0, 40.0, 50.0),
            "det_score": 0.99,
            "face_w": 39,
            "face_h": 48,
            "dim": 128,
            "embedding": vector,
        }]

    calls = _install(monkeypatch, detect=detect)
    rec = run_category_backfill(store, "people")
    assert rec["status"] == "completed"
    assert calls["cluster"] == 0
    conn = connect(store)
    try:
        persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
        faces = conn.execute("SELECT person_id, cluster_id, status FROM faces").fetchall()
    finally:
        conn.close()
    assert persons == 0
    assert len(faces) == 1
    assert faces[0]["person_id"] is None
    assert faces[0]["cluster_id"] is None


def test_objects_unavailable_does_not_invent_labels(tmp_path, monkeypatch):
    store = _store(tmp_path, ("a.jpg",))
    calls = _install(monkeypatch, probe=_probe(objects=False))
    rec = run_category_backfill(store, "objects")
    assert rec["status"] == "unavailable"
    assert "not available" in rec["user_message"]
    assert calls["objects"] == 0
    assert calls["people"] == 0
    assert _completed(store, "objects") == []
    conn = connect(store)
    try:
        labels = conn.execute(
            "SELECT COUNT(*) FROM observation_items WHERE kind='object'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert labels == 0


def test_ocr_states_stay_distinct(tmp_path, monkeypatch):
    cases = {
        "unavailable": (False, None, "unavailable", None),
        "read_failure": (True, None, "failed", "read_failure"),
        "execution_failure": (True, {"error": "boom", "note": "boom"}, "failed", "execution_failure"),
        "empty": (True, {"text": "  ", "score": 0, "words": []}, "completed", "empty"),
        "text": (True, {"text": "Hello", "score": 1, "words": [{"text": "Hello", "score": 0.9, "bbox": (1, 1, 4, 4)}]}, "completed", "text"),
    }
    for name, (available, payload, state, outcome) in cases.items():
        folder = tmp_path / name
        folder.mkdir()
        store = _store(folder, ("a.jpg",))

        def words(_img, payload=payload):
            return payload

        def decode(path, available=available):
            if name == "read_failure":
                return None
            return object()

        _install(
            monkeypatch,
            words=words,
            decode=decode,
            probe=_probe(words=available),
        )
        rec = run_category_backfill(store, "words")
        if not available:
            assert rec["status"] == "unavailable"
            assert _completed(store, "words") == []
            continue
        rows = _completed(store, "words")
        assert rows[0]["state"] == state
        assert rows[0]["outcome"] == outcome
        if outcome == "empty":
            assert rec["completed"] == 1
        if outcome == "execution_failure":
            assert rec["failed"] == 1
            assert rec["completed"] == 0


def test_region_isolation_reports_frame_and_detail(tmp_path, monkeypatch):
    store = _store(tmp_path, ("a.jpg",))
    depths = []

    def regions(_img, *, depth, cancelled):
        depths.append(depth)
        return {"counts": {}, "records": [], "skip_persist": False}

    calls = _install(monkeypatch, regions=regions)
    rec = run_category_backfill(store, "regions")
    assert rec["status"] == "completed"
    assert depths == ["frame", "detail"]
    assert calls["people"] == calls["objects"] == calls["words"] == 0
    report = coverage_report(store, "regions")
    assert report["completed"] == 1
    assert report["frame_indexed"] == 1
    assert report["detail_indexed"] == 1
    conn = connect(store)
    try:
        mask = conn.execute("SELECT COALESCE(SUM(tier_done_mask), 0) FROM work_items").fetchone()[0]
    finally:
        conn.close()
    assert int(mask or 0) == 0


def test_second_run_skips_completed_work(tmp_path, monkeypatch):
    store = _store(tmp_path, ("a.jpg",))
    calls = _install(monkeypatch)
    first = run_category_backfill(store, "words")
    second = run_category_backfill(store, "words")
    assert first["completed"] == 1
    assert second["skipped_already"] == 1
    assert calls["words"] == 1


def test_cancel_then_resume_keeps_finished_work(tmp_path, monkeypatch):
    store = _store(tmp_path)
    seen = {"n": 0}

    def gate():
        return seen["n"] >= 1

    def words(_img):
        seen["n"] += 1
        return {"text": "kept", "score": 1, "words": []}

    _install(monkeypatch, words=words)
    stopped = run_category_backfill(store, "words", gate=gate)
    assert stopped["status"] == "cancelled"
    assert "Stopped" in stopped["user_message"]
    assert "checked" in stopped["user_message"].lower() or "not finished" in stopped["user_message"]
    rows = _completed(store, "words")
    done = [row for row in rows if row["state"] == "completed"]
    assert len(done) == 1
    assert all(row["state"] != "completed" or row["outcome"] == "text" for row in rows)
    resumed = run_category_backfill(store, "words", gate=lambda: False)
    assert resumed["status"] == "completed"
    assert seen["n"] == 2
    assert coverage_report(store, "words")["completed"] == 2


def test_cancel_before_work_does_not_mark_complete(tmp_path, monkeypatch):
    store = _store(tmp_path, ("a.jpg",))
    calls = _install(monkeypatch)
    rec = run_category_backfill(store, "people", gate=lambda: True)
    assert rec["status"] == "cancelled"
    assert calls["people"] == 0
    assert coverage_report(store, "people")["completed"] == 0


def test_changed_file_and_provider_version_are_redone(tmp_path, monkeypatch):
    store = _store(tmp_path, ("a.jpg",))
    calls = _install(monkeypatch, probe=_probe("v1"))
    run_category_backfill(store, "objects")
    assert calls["objects"] == 1
    conn = connect(store)
    conn.execute("UPDATE media SET sha256=? WHERE media_id=?", ("sha-new", "a.jpg"))
    conn.commit()
    conn.close()
    run_category_backfill(store, "objects")
    assert calls["objects"] == 2
    calls2 = _install(monkeypatch, probe=_probe("v2"))
    run_category_backfill(store, "words")
    run_category_backfill(store, "words")
    assert calls2["words"] == 1
    _install(monkeypatch, probe=_probe("v9"))
    run_category_backfill(store, "words")
    rows = _completed(store, "words")
    assert rows[0]["provider_version"] == "v9"
    assert rows[0]["state"] == "completed"


def test_one_category_does_not_change_another(tmp_path, monkeypatch):
    store = _store(tmp_path, ("a.jpg",))
    _install(monkeypatch)
    run_category_backfill(store, "words")
    assert coverage_report(store, "words")["completed"] == 1
    assert coverage_report(store, "people")["completed"] == 0
    assert coverage_report(store, "objects")["completed"] == 0
    assert coverage_report(store, "regions")["completed"] == 0


def test_unsupported_and_missing_are_not_complete(tmp_path, monkeypatch):
    store = _store(tmp_path, ("clip.mp4", "gone.jpg"))
    missing = tmp_path / "gone.jpg"
    missing.unlink()
    _install(monkeypatch)
    rec = run_category_backfill(store, "words")
    rows = {row["outcome"]: row["state"] for row in _completed(store, "words")}
    # video is skipped; the missing still is skipped. Neither is completed coverage.
    assert "unsupported" in rows or any(row["state"] == "skipped" for row in _completed(store, "words"))
    report = coverage_report(store, "words")
    assert report["completed"] == 0
    assert rec["completed"] == 0
    conn = connect(store)
    try:
        states = {row["outcome"] for row in conn.execute("SELECT outcome, state FROM category_coverage")}
    finally:
        conn.close()
    assert "unsupported" in states
    assert "missing_original" in states


def test_migration_keeps_existing_rows(tmp_path):
    store = tmp_path / "old.sqlite"
    conn = connect(store)
    init_db(conn)
    assert conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0] == SCHEMA_VERSION
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id, embedding_dim, embedding_norm,
           config_json, runtime_json, arch, execution)
           VALUES ('r1','t','1','pack',128,'l2','{}','{}','x64','native')"""
    )
    conn.execute(
        "INSERT INTO media(media_id, source_type, path, sha256, width, height, mtime_ns, byte_size) VALUES (?,?,?,?,?,?,?,?)",
        ("m1", "folder", "/tmp/a.jpg", "abc", 1, 1, 1, 1),
    )
    conn.execute(
        "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES ('o1','m1',NULL,NULL,'r1')"
    )
    conn.execute(
        "INSERT INTO persons(person_id, display_name, status) VALUES ('p1','Ada','active')"
    )
    blob = np.ones(128, dtype=np.float32).tobytes()
    conn.execute(
        """INSERT INTO faces(face_id, observation_id, run_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2,
           det_score, face_w, face_h, size_band, embedding, embedding_pack, embedding_dim, status, person_id)
           VALUES ('f1','o1','r1',0,0,1,1,0.9,10,10,'ok',?,?,?,'ok','p1')""",
        (blob, "pack", 128),
    )
    conn.execute("DROP TABLE category_coverage")
    conn.execute("DELETE FROM schema_migrations WHERE version=6")
    conn.execute("UPDATE schema_meta SET value='5' WHERE key='schema_version'")
    conn.commit()
    assert apply_migrations(conn) == 6
    person = conn.execute("SELECT display_name FROM persons WHERE person_id='p1'").fetchone()[0]
    pid = conn.execute("SELECT person_id FROM faces WHERE face_id='f1'").fetchone()[0]
    media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    assert person == "Ada"
    assert pid == "p1"
    assert media == 1
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='category_coverage'"
    ).fetchone()
    conn.close()


def test_running_row_is_not_left_complete_after_interrupt(tmp_path, monkeypatch):
    store = _store(tmp_path, ("a.jpg",))
    conn = connect(store)
    init_db(conn)
    conn.execute(
        """INSERT INTO category_coverage(
             media_id, category, sha256, provider_id, provider_version, state, outcome,
             attempt_count, last_error, frame_done, detail_done, started_at, finished_at, updated_at)
           VALUES ('a.jpg','words','sha-a.jpg','words','v1','running','partial',1,NULL,0,0,'t',NULL,'t')"""
    )
    conn.commit()
    conn.close()
    _install(monkeypatch)
    rec = run_category_backfill(store, "words", gate=lambda: True)
    assert rec["status"] == "cancelled"
    states = {row["state"] for row in _completed(store, "words")}
    assert "completed" not in states
    assert "running" not in states


def test_discover_says_what_is_checked_without_scanning(tmp_path, monkeypatch):
    store = _store(tmp_path)
    calls = _install(monkeypatch, probe=_probe(objects=False))
    from semblon.category_backfill import discover_coverage_text

    conn = connect(store)
    conn.execute(
        """INSERT INTO category_coverage(
             media_id, category, sha256, provider_id, provider_version, state, outcome,
             attempt_count, last_error, frame_done, detail_done, started_at, finished_at, updated_at)
           VALUES ('a.jpg','people','sha-a.jpg','people','v1','completed','faces',1,NULL,0,0,'t','t','t')"""
    )
    conn.commit()
    conn.close()
    text = discover_coverage_text(store)
    assert "People: 1 of 2 photos checked" in text
    assert "Objects:" in text and "Nothing was downloaded" in text
    assert "Regions: not checked yet" in text
    assert "Words in photos: not checked yet" in text
    assert calls["people"] == calls["objects"] == calls["regions"] == calls["words"] == calls["ingest"] == 0


def test_search_names_a_partial_check_and_leaves_an_untracked_library_alone(tmp_path):
    from semblon.search import search_object, search_text

    store = _store(tmp_path)
    conn = connect(store)
    conn.execute(
        """INSERT INTO runs(run_id, started_at, software_version, pack_id, embedding_dim, embedding_norm,
           config_json, runtime_json, arch, execution)
           VALUES ('r1','t','1','pack',1,'l2','{}','{}','x64','native')"""
    )
    conn.execute(
        "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES ('o1','a.jpg',NULL,NULL,'r1')"
    )
    conn.execute(
        """INSERT INTO observation_items(item_id, observation_id, run_id, kind, provider, score, payload_json)
           VALUES ('t1','o1','r1','text','tesseract',1,?)""",
        ('{"text":"hello","contract_status":"SUCCESS"}',),
    )
    conn.execute(
        """INSERT INTO category_coverage(
             media_id, category, sha256, provider_id, provider_version, state, outcome,
             attempt_count, last_error, frame_done, detail_done, started_at, finished_at, updated_at)
           VALUES ('a.jpg','words','sha-a.jpg','words','v1','completed','text',1,NULL,0,0,'t','t','t')"""
    )
    conn.commit()
    hit = search_text(store, "hello")
    miss = search_text(store, "nope-xyz")
    assert hit["status"] == "SUCCESS"
    assert "1 of 2 photos checked" in hit["reason"]
    assert miss["status"] == "NO_RESULT"
    assert "No text matched in the 1 of 2 photos checked" in miss["reason"]
    conn.execute("DELETE FROM category_coverage")
    conn.commit()
    conn.close()
    legacy = search_text(store, "nope-xyz")
    assert legacy["status"] == "NO_RESULT"
    assert "coverage_clause" not in legacy
    assert legacy["reason"] == "No text matched in your photos."
    empty = search_object(store, "dog")
    assert empty["status"] == "UNAVAILABLE"
    assert "coverage_clause" not in empty


def test_region_coverage_is_visible_without_the_shared_tier_bit(tmp_path):
    from semblon.scan_tiers import coverage_note, semantic_coverage

    store = _store(tmp_path, ("a.jpg",))
    conn = connect(store)
    conn.execute(
        """INSERT INTO category_coverage(
             media_id, category, sha256, provider_id, provider_version, state, outcome,
             attempt_count, last_error, frame_done, detail_done, started_at, finished_at, updated_at)
           VALUES ('a.jpg','regions','sha-a.jpg','dinov2','v1','pending','frame_only',1,NULL,1,0,'t',NULL,'t')"""
    )
    conn.commit()
    cov = semantic_coverage(conn)
    assert cov["total"] == 1
    assert cov["searchable"] == 1
    assert cov["detailed"] == 0
    assert cov["complete"] is False
    assert "Fine-detail" in coverage_note(cov)
    masks = conn.execute("SELECT COUNT(*) FROM work_items").fetchone()[0]
    conn.close()
    assert masks == 0


def test_job_engine_uses_category_runner_not_ingest(tmp_path, monkeypatch):
    store = _store(tmp_path, ("a.jpg",))
    calls = _install(monkeypatch)
    from semblon.jobs import JobEngine

    engine = JobEngine(store)
    rec = engine._run_category  # bound later
    handle_ran = {}

    def run(store_arg, category, *, gate=None, on_event=None):
        handle_ran["category"] = category
        handle_ran["gate"] = gate
        return {"status": "completed", "user_message": "Words in photos checked. 0 of 0."}

    monkeypatch.setattr("semblon.category_backfill.run_category_backfill", run)
    from semblon.jobs import JobHandle, KIND_CATEGORY

    handle = JobHandle(kind=KIND_CATEGORY, folder=store, resume=False, store=store, category="words")
    engine._current = handle
    seen = {}

    def done(result):
        seen["status"] = result.status
        seen["message"] = result.rec["user_message"]

    engine._run_category(handle, None, done)
    assert handle_ran["category"] == "words"
    assert seen["status"] == "completed"
    assert calls["ingest"] == 0
    assert "complete" not in seen["message"].lower() or "checked" in seen["message"].lower()
