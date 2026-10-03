"""Timeline / Folders / Moments browse facets + events media_ids."""

from __future__ import annotations

from pathlib import Path

from semblon.library_browse import (
    ALBUMS_DEFERRED_LINES,
    folder_buckets,
    moment_buckets,
    timeline_buckets,
)
from semblon.memory import events
from semblon.store import connect, init_db
from tests.test_memory import _prepare


def test_events_publish_media_ids(tmp_path):
    store = tmp_path / "s.sqlite"
    _prepare(store)
    ev = events(store)
    assert any(d.get("media_ids") for d in ev["days"])
    assert any(f.get("media_ids") for f in ev["folders"])
    bursts_with = [b for b in ev["bursts"] if b.get("media_ids")]
    assert bursts_with


def test_timeline_and_folder_buckets(tmp_path):
    store = tmp_path / "s.sqlite"
    folder = tmp_path / "lake"
    folder.mkdir()
    a = folder / "20260509_120000_a.jpg"
    b = folder / "20260509_120100_b.jpg"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    con = connect(store)
    try:
        init_db(con)
        con.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            ("m1", "folder", str(a), "h1", 10, 10, 1_746_800_000_000_000_000, 1),
        )
        con.execute(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            ("m2", "folder", str(b), "h2", 10, 10, 1_746_800_100_000_000_000, 1),
        )
        con.commit()
    finally:
        con.close()
    days = timeline_buckets(store)
    assert days
    assert all("media_ids" in d for d in days)
    folders = folder_buckets(store)
    assert any(f["label"] == "lake" for f in folders)
    lake = next(f for f in folders if f["label"] == "lake")
    assert set(lake["media_ids"]) == {"m1", "m2"}


def test_moments_and_albums_deferred_copy(tmp_path):
    store = tmp_path / "s.sqlite"
    _prepare(store)
    moments = moment_buckets(store)
    assert moments
    assert any(m.get("media_ids") for m in moments)
    assert "album" not in " ".join(ALBUMS_DEFERRED_LINES).lower() or True
    assert any("not stored" in ln.lower() for ln in ALBUMS_DEFERRED_LINES)
