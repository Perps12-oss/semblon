"""Sidecar hash cache ``<store stem>.dedupe.sqlite`` for ``semblon.dedupe``.

Lives outside ``semblon/dedupe`` so the engine stays free of storage imports. The main store
schema is untouched. Rows are keyed on (path, size, mtime_ns, kind), so a changed file never
reuses a stale digest; the cache can be deleted at any time. Failures degrade to "no cache".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from semblon.dedupe import MemoryHashCache

_DDL = (
    "CREATE TABLE IF NOT EXISTS hashes ("
    "path TEXT NOT NULL, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, "
    "kind TEXT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY (path, size, mtime_ns, kind))"
)


_HISTORY_DDL = (
    "CREATE TABLE IF NOT EXISTS scans ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, started_at REAL NOT NULL, seconds REAL NOT NULL, "
    "cancelled INTEGER NOT NULL, files INTEGER NOT NULL, size_candidates INTEGER NOT NULL, "
    "partial_hashed INTEGER NOT NULL, full_hashed INTEGER NOT NULL, cache_hits INTEGER NOT NULL, "
    "bytes_read INTEGER NOT NULL, unreadable INTEGER NOT NULL, groups INTEGER NOT NULL)"
)
HISTORY_LIMIT = 50


def record_scan(store: Path, stats, *, started_at: float, seconds: float, cancelled: bool, groups: int) -> bool:
    """Append a diagnostics row (diagnostics only; never read back to decide anything)."""
    try:
        con = sqlite3.connect(sidecar_path(store))
        try:
            con.execute(_HISTORY_DDL)
            con.execute(
                "INSERT INTO scans (started_at, seconds, cancelled, files, size_candidates, partial_hashed, "
                "full_hashed, cache_hits, bytes_read, unreadable, groups) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    started_at, seconds, int(cancelled), stats.files_considered, stats.size_candidates,
                    stats.partial_hashed, stats.full_hashed, stats.cache_hits, stats.bytes_read,
                    stats.unreadable, groups,
                ),
            )
            con.execute(
                "DELETE FROM scans WHERE id NOT IN (SELECT id FROM scans ORDER BY id DESC LIMIT ?)",
                (HISTORY_LIMIT,),
            )
            con.commit()
        finally:
            con.close()
        return True
    except (sqlite3.Error, OSError):
        return False


def load_history(store: Path, limit: int = 10) -> list[dict]:
    p = sidecar_path(store)
    if not p.is_file():
        return []
    try:
        con = sqlite3.connect(p)
        try:
            con.row_factory = sqlite3.Row
            rows = con.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return []
    return [dict(r) for r in rows]


def sidecar_path(store: Path) -> Path:
    store = Path(store)
    return store.with_name(store.stem + ".dedupe.sqlite")


def load_cache(store: Path) -> MemoryHashCache:
    p = sidecar_path(store)
    if not p.is_file():
        return MemoryHashCache()
    try:
        con = sqlite3.connect(p)
        try:
            rows = con.execute("SELECT path, size, mtime_ns, kind, digest FROM hashes").fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return MemoryHashCache()
    return MemoryHashCache.load([list(r) for r in rows])


def save_cache(store: Path, cache: MemoryHashCache) -> bool:
    """Persist the cache (loaded + newly computed digests); also saved after a cancelled scan so it resumes."""
    try:
        con = sqlite3.connect(sidecar_path(store))
        try:
            con.execute(_DDL)
            con.execute("DELETE FROM hashes")
            con.executemany("INSERT OR REPLACE INTO hashes VALUES (?,?,?,?,?)", cache.export())
            con.commit()
        finally:
            con.close()
        return True
    except (sqlite3.Error, OSError):
        return False
