"""Session for one archive viewed through a lens.

Owns lens, history, scroll, selection, focus, and at most one desk.
Does not open a route table, write identity, or invent search results.
The Time lens reads media rows already in the store, ordered by stored
mtime (the same clock as library timeline browse). Capture EXIF is not a
column; this does not scan every file to invent a finer clock.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from semblon.store import connect_readonly

__all__ = [
    "Desk",
    "Lens",
    "MediaRef",
    "ArchiveSession",
    "ViewState",
    "time_lens",
]


@dataclass(frozen=True)
class Lens:
    """Semantic projection. Scroll and focus are not part of a lens."""

    kind: str
    label: str
    parameters: tuple[tuple[str, str], ...] = ()
    order: str = "time"

    def parameter(self, key: str) -> str | None:
        for name, value in self.parameters:
            if name == key:
                return value
        return None


def time_lens() -> Lens:
    return Lens(kind="time", label="Time", parameters=(), order="time")


def day_key(mtime_ns: int | None) -> str:
    """The day a picture belongs to on the timeline: the local day, same clock everywhere."""
    from .clock import local_day

    return local_day(mtime_ns)


@dataclass(frozen=True)
class MediaRef:
    media_id: str
    path: str
    source_type: str
    mtime_ns: int | None
    width: int | None
    height: int | None

    @property
    def name(self) -> str:
        return Path(self.path).name or self.media_id

    @property
    def day(self) -> str:
        return day_key(self.mtime_ns)


@dataclass(frozen=True)
class Desk:
    kind: str
    bound_id: str | None = None
    pinned: bool = False


@dataclass(frozen=True)
class ViewState:
    lens: Lens
    scroll: float
    selection: tuple[str, ...]
    focus_id: str | None
    desk: Desk | None


class JobPort(Protocol):
    @property
    def busy(self) -> bool: ...

    @property
    def state(self) -> str: ...

    def submit_ingest(self, folder: Path, *, on_done=None, open_review: bool = False, **kwargs): ...


class ArchiveSession:
    """Python-owned view of one store. QML renders this; it does not own it."""

    def __init__(self, store: Path, jobs: JobPort | None = None):
        self.store = Path(store)
        self._jobs = jobs
        self.lens: Lens = time_lens()
        self.scroll: float = 0.0
        self.selection: tuple[str, ...] = ()
        self.focus_id: str | None = None
        self.desk: Desk | None = None
        self._history: list[ViewState] = []
        self._local = threading.local()
        self._cache_lock = threading.Lock()
        self._read_gen = 0
        self._count_cache: int | None = None
        self._media_cache: dict[str, MediaRef | None] = {}
        self._days_cache: list[str] | None = None

    def invalidate_reads(self) -> None:
        """Drop cached media rows after the archive changes."""
        with self._cache_lock:
            self._count_cache = None
            self._media_cache.clear()
            self._days_cache = None
            self._read_gen += 1

    def _read_conn(self):
        """One read-only connection per thread. Opening SQLite on every thumb stalls the UI."""
        if not self.store.is_file():
            return None
        store = str(self.store.resolve())
        gen = self._read_gen
        local = self._local
        conn = getattr(local, "conn", None)
        if conn is not None and getattr(local, "key", None) == (store, gen):
            return conn
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        try:
            conn = connect_readonly(self.store)
            conn.execute("PRAGMA busy_timeout=80")
        except sqlite3.Error:
            local.conn = None
            local.key = None
            return None
        local.conn = conn
        local.key = (store, gen)
        return conn

    @property
    def lens_history(self) -> tuple[ViewState, ...]:
        return tuple(self._history)

    def count(self) -> int:
        if self.lens.kind != "time":
            return 0
        if not self.store.is_file():
            return 0
        with self._cache_lock:
            if self._count_cache is not None:
                return self._count_cache
        conn = self._read_conn()
        if conn is None:
            return 0
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM media WHERE source_type='folder'"
            ).fetchone()
            value = int(row[0] if row else 0)
        except sqlite3.Error:
            return 0
        with self._cache_lock:
            self._count_cache = value
        return value

    def window(self, offset: int, limit: int) -> list[MediaRef]:
        """One ordered slice. Never the whole library."""
        if self.lens.kind != "time" or limit <= 0 or offset < 0:
            return []
        if not self.store.is_file():
            return []
        conn = self._read_conn()
        if conn is None:
            return []
        try:
            rows = conn.execute(
                """
                SELECT media_id, path, source_type, mtime_ns, width, height
                FROM media
                WHERE source_type='folder'
                ORDER BY (mtime_ns IS NULL), mtime_ns DESC, media_id
                LIMIT ? OFFSET ?
                """,
                (int(limit), int(offset)),
            ).fetchall()
        except sqlite3.Error:
            return []
        return [_media(row) for row in rows]

    def days(self) -> list[str]:
        """Every picture's day key in display order. One cheap column, so sections can be laid out."""
        if self.lens.kind != "time" or not self.store.is_file():
            return []
        with self._cache_lock:
            if self._days_cache is not None:
                return list(self._days_cache)
        conn = self._read_conn()
        if conn is None:
            return []
        try:
            rows = conn.execute(
                """
                SELECT mtime_ns FROM media
                WHERE source_type='folder'
                ORDER BY (mtime_ns IS NULL), mtime_ns DESC, media_id
                """
            ).fetchall()
        except sqlite3.Error:
            return []
        out = [day_key(row[0]) for row in rows]
        with self._cache_lock:
            self._days_cache = out
        return list(out)

    def media(self, media_id: str) -> MediaRef | None:
        if not media_id or not self.store.is_file():
            return None
        with self._cache_lock:
            if media_id in self._media_cache:
                return self._media_cache[media_id]
        conn = self._read_conn()
        if conn is None:
            return None
        try:
            row = conn.execute(
                """
                SELECT media_id, path, source_type, mtime_ns, width, height
                FROM media WHERE media_id=?
                """,
                (media_id,),
            ).fetchone()
        except sqlite3.Error:
            return None
        item = None if row is None else _media(row)
        with self._cache_lock:
            if len(self._media_cache) > 4000:
                self._media_cache.clear()
            self._media_cache[media_id] = item
        return item

    def index_of(self, media_id: str) -> int | None:
        item = self.media(media_id)
        if item is None or not self.store.is_file():
            return None
        if item.source_type != "folder":
            return None
        conn = self._read_conn()
        if conn is None:
            return None
        try:
            if item.mtime_ns is None:
                row = conn.execute(
                    """
                    SELECT COUNT(*) FROM media
                    WHERE source_type='folder' AND (
                       mtime_ns IS NOT NULL
                       OR (mtime_ns IS NULL AND media_id < ?)
                    )
                    """,
                    (item.media_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT COUNT(*) FROM media
                    WHERE source_type='folder' AND mtime_ns IS NOT NULL
                      AND (mtime_ns > ? OR (mtime_ns = ? AND media_id < ?))
                    """,
                    (item.mtime_ns, item.mtime_ns, item.media_id),
                ).fetchone()
        except sqlite3.Error:
            return None
        return int(row[0] if row else 0)

    def open_focus(self, media_id: str) -> None:
        item = self.media(media_id)
        if item is None or item.source_type != "folder":
            return
        self._set_focus(media_id)

    def move_focus(self, delta: int) -> None:
        if not self.focus_id or delta == 0:
            return
        index = self.index_of(self.focus_id)
        if index is None:
            return
        target = index + int(delta)
        if target < 0 or target >= self.count():
            return
        rows = self.window(target, 1)
        if not rows:
            return
        self._set_focus(rows[0].media_id)

    def clear_focus(self) -> None:
        self.focus_id = None

    def push_lens(self, lens: Lens) -> None:
        """Replace the lens and remember the view being left."""
        self._history.append(self._snapshot())
        self.lens = lens
        self.scroll = 0.0
        self.selection = ()
        self.focus_id = None
        self.desk = None

    def back(self) -> bool:
        if not self._history:
            return False
        self._restore(self._history.pop())
        return True

    def wordmark(self) -> None:
        """Time clears focus and desk. Any other lens steps back."""
        if self.lens.kind == "time":
            self.desk = None
            self.focus_id = None
            return
        self.back()

    def escape(self) -> str:
        """Desk, then Focus, then stay on the Field."""
        if self.desk is not None:
            self.desk = None
            return "desk"
        if self.focus_id is not None:
            self.focus_id = None
            return "focus"
        return "field"

    def open_desk(self, kind: str, bound_id: str | None = None, *, pinned: bool = False) -> None:
        self.desk = Desk(kind=kind, bound_id=bound_id, pinned=pinned)

    def add_folder(self, folder: Path, *, on_done=None):
        """Existing ingest door. Does not start a second pipeline."""
        if self._jobs is None:
            raise RuntimeError("archive session has no job port")
        return self._jobs.submit_ingest(Path(folder), on_done=on_done, open_review=False)

    def job_active(self) -> bool:
        jobs = self._jobs
        if jobs is None:
            return False
        return bool(jobs.busy)

    def job_state(self) -> str:
        jobs = self._jobs
        if jobs is None or not jobs.busy:
            return "idle"
        return str(jobs.state or "running")

    def _set_focus(self, media_id: str) -> None:
        if self.desk is not None and not self.desk.pinned:
            self.desk = None
        self.focus_id = media_id
        self.selection = (media_id,)

    def _snapshot(self) -> ViewState:
        return ViewState(
            lens=self.lens,
            scroll=float(self.scroll),
            selection=tuple(self.selection),
            focus_id=self.focus_id,
            desk=self.desk,
        )

    def _restore(self, frame: ViewState) -> None:
        self.lens = frame.lens
        self.scroll = float(frame.scroll)
        self.selection = tuple(frame.selection)
        self.focus_id = frame.focus_id
        self.desk = frame.desk


def _media(row) -> MediaRef:
    mtime = row["mtime_ns"]
    return MediaRef(
        media_id=str(row["media_id"]),
        path=str(row["path"] or ""),
        source_type=str(row["source_type"] or "folder"),
        mtime_ns=int(mtime) if mtime is not None else None,
        width=int(row["width"]) if row["width"] is not None else None,
        height=int(row["height"]) if row["height"] is not None else None,
    )
