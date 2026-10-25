"""Archive session: Time lens, focus, history, escape. No identity writes."""

from __future__ import annotations

import inspect
from pathlib import Path

from semblon.archive_session import ArchiveSession, Lens, time_lens
from semblon.store import connect, init_db


class _Jobs:
    def __init__(self):
        self.busy = False
        self.state = "idle"
        self.calls: list[Path] = []

    def submit_ingest(self, folder: Path, *, on_done=None, open_review: bool = False, **kwargs):
        assert open_review is False
        self.calls.append(Path(folder))
        self.busy = True
        self.state = "running"
        return folder


def _store(tmp_path: Path, rows: list[tuple]) -> Path:
    path = tmp_path / "s.sqlite"
    conn = connect(path)
    try:
        init_db(conn)
        conn.executemany(
            "INSERT INTO media VALUES (?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _row(media_id: str, mtime: int | None, kind: str = "folder", name: str = "a.jpg") -> tuple:
    return (
        media_id,
        kind,
        str(name),
        media_id + "hash",
        100,
        80,
        mtime,
        10,
    )


def test_time_lens_is_session_owned_and_deterministic():
    lens = time_lens()
    assert lens.kind == "time"
    assert lens.label == "Time"
    assert lens.parameters == ()
    assert lens.order == "time"
    assert lens == time_lens()


def test_time_window_is_chronological_and_limited(tmp_path):
    store = _store(
        tmp_path,
        [
            _row("old", 1, name="old.jpg"),
            _row("new", 30, name="new.jpg"),
            _row("mid", 10, name="mid.jpg"),
            _row("none", None, name="none.jpg"),
        ],
    )
    session = ArchiveSession(store)
    assert session.lens == time_lens()
    assert session.count() == 4
    window = session.window(0, 2)
    assert [item.media_id for item in window] == ["new", "mid"]
    assert session.window(2, 2)[0].media_id == "old"
    assert session.window(3, 2)[0].media_id == "none"
    assert len(session.window(0, 2)) == 2


def test_large_library_window_does_not_return_every_row(tmp_path):
    rows = [_row(f"m{i:05d}", i, name=f"{i}.jpg") for i in range(1000)]
    store = _store(tmp_path, rows)
    session = ArchiveSession(store)
    assert session.count() == 1000
    page = session.window(100, 40)
    assert len(page) == 40
    assert page[0].media_id == "m00899"
    # a page is a slice of the date-ordered timeline: the end is short, past the end is empty
    assert len(session.window(990, 40)) == 10
    assert session.window(1000, 40) == []


def test_focus_stays_inside_the_current_lens(tmp_path):
    store = _store(
        tmp_path,
        [_row("a", 1), _row("b", 2), _row("c", 3)],
    )
    session = ArchiveSession(store)
    session.open_focus("b")
    assert session.focus_id == "b"
    assert session.lens.kind == "time"
    assert session.lens_history == ()
    session.move_focus(1)
    assert session.focus_id == "a"
    session.move_focus(-1)
    assert session.focus_id == "b"
    session.move_focus(-1)
    assert session.focus_id == "c"
    session.move_focus(-1)
    assert session.focus_id == "c"
    assert session.lens_history == ()


def test_lens_history_restores_scroll_selection_and_focus(tmp_path):
    store = _store(tmp_path, [_row("a", 1), _row("b", 2)])
    session = ArchiveSession(store)
    session.open_focus("a")
    session.scroll = 240
    session.selection = ("a", "b")
    session.push_lens(Lens(kind="person", label="Person · Maya", parameters=(("id", "p1"),), order="time"))
    assert session.lens.label == "Person · Maya"
    assert session.focus_id is None
    assert session.scroll == 0
    assert session.back() is True
    assert session.lens.kind == "time"
    assert session.scroll == 240
    assert session.selection == ("a", "b")
    assert session.focus_id == "a"
    assert session.back() is False


def test_escape_closes_desk_before_focus(tmp_path):
    store = _store(tmp_path, [_row("a", 1)])
    session = ArchiveSession(store)
    session.open_focus("a")
    session.open_desk("metadata", "a")
    assert session.escape() == "desk"
    assert session.desk is None
    assert session.focus_id == "a"
    assert session.escape() == "focus"
    assert session.focus_id is None
    assert session.escape() == "field"


def test_wordmark_clears_time_focus_and_backs_out_of_other_lenses(tmp_path):
    store = _store(tmp_path, [_row("a", 1)])
    session = ArchiveSession(store)
    session.scroll = 80
    session.open_focus("a")
    session.wordmark()
    assert session.focus_id is None
    assert session.lens.kind == "time"
    assert session.scroll == 80
    assert session.lens_history == ()
    session.scroll = 12
    session.push_lens(Lens(kind="search", label="Search · dog", parameters=(("q", "dog"),)))
    session.wordmark()
    assert session.lens.kind == "time"
    assert session.scroll == 12


def test_empty_library_and_add_folder_use_the_job_port(tmp_path):
    store = tmp_path / "empty.sqlite"
    jobs = _Jobs()
    session = ArchiveSession(store, jobs=jobs)
    assert session.count() == 0
    assert session.job_active() is False
    folder = tmp_path / "photos"
    session.add_folder(folder)
    assert jobs.calls == [folder]
    assert session.job_active() is True
    assert session.job_state() == "running"


def test_unpinned_desk_closes_when_focus_moves(tmp_path):
    store = _store(tmp_path, [_row("a", 1), _row("b", 2)])
    session = ArchiveSession(store)
    session.open_focus("b")
    session.open_desk("metadata", "b", pinned=True)
    session.move_focus(1)
    assert session.desk is not None
    assert session.desk.pinned is True
    session.desk = None
    session.open_desk("metadata", session.focus_id or "", pinned=False)
    session.move_focus(-1)
    assert session.desk is None


def test_session_source_does_not_write_identity_or_invent_search():
    root = Path(__file__).resolve().parents[1] / "semblon"
    text = (root / "archive_session.py").read_text(encoding="utf-8")
    assert "person_id" not in text
    assert "UPDATE faces" not in text
    assert "search_text" not in text
    assert "from semblon.process import process_folder" not in text
