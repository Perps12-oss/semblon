import threading

from semblon import detail_priority
from semblon.scan_tiers import TIER_DETAIL, TIER_LIBRARY, TIER_OBSERVE, TIER_SEMANTIC
from semblon.store import connect, init_db

LITE = TIER_LIBRARY | TIER_OBSERVE | TIER_SEMANTIC


def _store(tmp_path, masks):
    path = tmp_path / "s.sqlite"
    conn = connect(path)
    init_db(conn)
    conn.execute("PRAGMA foreign_keys=OFF")
    for name, mask in masks.items():
        conn.execute(
            "INSERT INTO work_items(path, mtime_ns, byte_size, media_id, tier_done_mask, updated_at) VALUES (?,?,?,?,?,?)",
            (f"/x/{name}.jpg", 1, 1, name, mask, "2026-01-01"),
        )
        conn.execute(
            "INSERT INTO observations(observation_id, media_id, frame_id, t_ms, run_id) VALUES (?,?,?,?,?)",
            (f"o-{name}", name, None, None, "r1"),
        )
    conn.commit()
    conn.close()
    return path


def _stub(calls, outcome=None):
    def indexer(conn, **kw):
        calls.append((kw["observation_id"], kw["depth"], kw["interactive"]))
        return outcome or {"scene": 0, "patch": 4, "region": 0, "jobs": 14, "ready": True}

    return indexer


def _mask(path, media_id):
    conn = connect(path)
    try:
        return detail_priority.mask_of(conn, media_id)
    finally:
        conn.close()


def test_promote_adds_detail_on_the_interactive_lane_and_stamps_it(tmp_path):
    detail_priority.reset_stats()
    path = _store(tmp_path, {"a": LITE, "b": LITE | TIER_DETAIL, "c": TIER_LIBRARY | TIER_OBSERVE})
    calls = []
    out = detail_priority.promote(
        path, ["a", "b", "c"], decode=lambda p: object(), indexer=_stub(calls)
    )
    assert out["done"] == 2 and out["already_done"] == 1
    assert ("o-a", "detail", True) in calls
    # A photo with no whole-picture pass gets both passes.
    assert ("o-c", "full", True) in calls
    assert _mask(path, "a") & TIER_DETAIL and _mask(path, "c") & (TIER_DETAIL | TIER_SEMANTIC)
    again = detail_priority.promote(path, ["a", "c"], decode=lambda p: object(), indexer=_stub(calls))
    assert again["done"] == 0 and again["already_done"] == 2
    assert len(calls) == 2


def test_a_failed_encode_is_not_stamped_so_it_resumes_later(tmp_path):
    path = _store(tmp_path, {"a": LITE})
    bad = {"scene": 0, "patch": 0, "region": 0, "jobs": 14, "note": "region encoder failed"}
    out = detail_priority.promote(path, ["a"], decode=lambda p: object(), indexer=_stub([], bad))
    assert out["failed"] == 1 and out["done"] == 0
    assert not _mask(path, "a") & TIER_DETAIL
    ok = detail_priority.promote(path, ["a"], decode=lambda p: object(), indexer=_stub([]))
    assert ok["done"] == 1


def test_cancel_stops_before_the_next_photo(tmp_path):
    path = _store(tmp_path, {"a": LITE, "b": LITE})
    seen = []

    def cancelled():
        return len(seen) >= 1

    out = detail_priority.promote(
        path, ["a", "b"], cancelled=cancelled, decode=lambda p: object(), indexer=_stub(seen)
    )
    assert out["cancelled"] and out["done"] == 1
    assert not _mask(path, "b") & TIER_DETAIL


def test_a_photo_already_being_worked_on_is_not_started_twice(tmp_path):
    detail_priority.reset_stats()
    path = _store(tmp_path, {"a": LITE})
    assert detail_priority.claim("a") is True
    try:
        calls = []
        out = detail_priority.promote(path, ["a"], decode=lambda p: object(), indexer=_stub(calls))
        assert out["busy"] == 1 and calls == []
        assert detail_priority.stats()["duplicates_avoided"] >= 1
    finally:
        detail_priority.release("a")


def test_two_searches_never_analyse_the_same_photo_together(tmp_path):
    path = _store(tmp_path, {"a": LITE})
    calls = []
    gate = threading.Event()

    def slow(conn, **kw):
        calls.append(kw["observation_id"])
        gate.wait(2)
        return {"scene": 0, "patch": 4, "region": 0, "jobs": 14, "ready": True}

    results = []
    first = threading.Thread(
        target=lambda: results.append(
            detail_priority.promote(path, ["a"], decode=lambda p: object(), indexer=slow)
        )
    )
    first.start()
    while not calls:
        pass
    second = detail_priority.promote(path, ["a"], decode=lambda p: object(), indexer=slow)
    gate.set()
    first.join()
    assert second["busy"] == 1 and second["done"] == 0
    assert results[0]["done"] == 1 and len(calls) == 1


class _Quality:
    whole_colour_floor = 0.0


def test_refine_reruns_only_when_detail_was_added(tmp_path, monkeypatch):
    from semblon import region_search as rs

    store = _store(tmp_path, {"a": LITE})
    reruns = []
    monkeypatch.setattr(rs, "_colour_result", lambda *a, **k: {"items": []})
    monkeypatch.setattr(
        rs, "promote_for_search", lambda *a, **k: {"requested": 1, "done": 0, "done_ids": []}
    )
    out = rs._refine_with_detail(
        store, ["a"], crop=object(), media_id="q", quality=_Quality(), cancelled=None,
        rerun=lambda: reruns.append(1) or {"items": []},
    )
    assert out is None and not reruns
    monkeypatch.setattr(
        rs, "promote_for_search", lambda *a, **k: {"requested": 1, "done": 1, "done_ids": ["a"]}
    )
    out = rs._refine_with_detail(
        store, ["a"], crop=object(), media_id="q", quality=_Quality(), cancelled=None,
        rerun=lambda: reruns.append(1) or {"items": [{"media_id": "a"}]},
    )
    assert reruns == [1] and out["detail_promoted"] == 1


def test_refine_skips_everything_when_cancelled(tmp_path):
    from semblon import region_search as rs

    store = _store(tmp_path, {"a": LITE})
    out = rs._refine_with_detail(
        store, ["a"], crop=object(), media_id="q", quality=_Quality(), cancelled=lambda: True,
        rerun=lambda: {"items": []},
    )
    assert out is None
    assert _mask(store, "a") & TIER_DETAIL == 0


def test_promote_for_search_adds_unprepared_colour_candidates(tmp_path, monkeypatch):
    from semblon import region_search as rs

    store = _store(tmp_path, {"a": LITE, "b": TIER_LIBRARY})
    seen = []
    monkeypatch.setattr(rs, "_colour_result", lambda *a, **k: {"items": [{"media_id": "b"}]})
    rs.promote_for_search(
        store, ["a"], crop=object(), media_id="q", quality=_Quality(),
        promote=lambda s, ids, **kw: seen.extend(ids) or {"requested": len(ids), "done": 0},
    )
    assert seen == ["a", "b"]
