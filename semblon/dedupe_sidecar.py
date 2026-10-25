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
