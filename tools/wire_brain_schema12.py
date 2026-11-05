"""Re-apply BRAIN schema-12 wiring into store / erasure_intent / forget.

Tracked copies of those three files have been silently reverted to schema 8
more than once. Run this script after a revert, then verify:

  python -c "from semblon.store import SCHEMA_VERSION; print(SCHEMA_VERSION)"
  # expect 12
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "semblon" / "store.py"
ERASURE = ROOT / "semblon" / "erasure_intent.py"
FORGET = ROOT / "semblon" / "forget.py"


ERASURE_TEXT = '''"""ErasureIntent — caller type plus connection-local DB enforcement helpers.

The dataclass alone is not enforcement. Writable connections register
``semblon_erasure_ok``; BEFORE DELETE triggers call it and fail closed when
intent is absent, invalid, or insufficient for the row.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

HUMAN_DECISION_KINDS = frozenset({"name", "reject", "merge", "split", "note"})
BRAIN_ERASURE_TABLES = frozenset(
    {
        "brain_observations",
        "brain_evidence",
        "brain_nodes",
        "brain_edges",
    }
)

_TLS = threading.local()


class ErasureAuthorizationError(RuntimeError):
    """Raised when a protected delete runs without sufficient ErasureIntent."""


@dataclass(frozen=True)
class ErasureIntent:
    """User-authorised erasure request. Not proof by itself — DB guard checks it."""

    requestor: str
    scope: str
    reason: str
    authorized_by: str
    person_id: str | None = None
    media_id: str | None = None
    face_ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        scope = str(self.scope or "").strip().lower()
        if scope not in {"person", "library", "media"}:
            raise ValueError(f"unsupported erasure scope: {self.scope!r}")
        object.__setattr__(self, "scope", scope)
        requestor = str(self.requestor or "").strip()
        reason = str(self.reason or "").strip()
        authorized_by = str(self.authorized_by or "").strip()
        if not requestor or not reason or not authorized_by:
            raise ValueError("requestor, reason, and authorized_by are required")
        object.__setattr__(self, "requestor", requestor)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "authorized_by", authorized_by)
        if scope == "person":
            person_id = str(self.person_id or "").strip()
            if not person_id:
                raise ValueError("person_id is required for scope=person")
            object.__setattr__(self, "person_id", person_id)
            faces = frozenset(str(f).strip() for f in self.face_ids if str(f).strip())
            object.__setattr__(self, "face_ids", faces)
            object.__setattr__(self, "media_id", None)
        elif scope == "media":
            media_id = str(self.media_id or "").strip()
            if not media_id:
                raise ValueError("media_id is required for scope=media")
            object.__setattr__(self, "media_id", media_id)
            object.__setattr__(self, "person_id", None)
            object.__setattr__(self, "face_ids", frozenset())
        else:
            object.__setattr__(self, "person_id", None)
            object.__setattr__(self, "media_id", None)
            object.__setattr__(self, "face_ids", frozenset())


def current_erasure_intent() -> ErasureIntent | None:
    return getattr(_TLS, "intent", None)


@contextmanager
def erasure_authorized(intent: ErasureIntent) -> Iterator[ErasureIntent]:
    """Activate intent for this thread while protected deletes run."""
    if not isinstance(intent, ErasureIntent):
        raise TypeError("ErasureIntent required")
    previous = getattr(_TLS, "intent", None)
    _TLS.intent = intent
    try:
        yield intent
    finally:
        _TLS.intent = previous


def _sql_erasure_ok(
    table: str | None,
    kind: str | None,
    person_id: str | None,
    face_id: str | None,
) -> int:
    """SQLite callback: 1 allow, 0 deny.

    For ``brain_observations``, the third argument is ``media_id``.
    """
    intent = current_erasure_intent()
    if intent is None:
        return 0
    table_name = str(table or "").strip().lower()
    if intent.scope == "library":
        return 1
    if table_name in BRAIN_ERASURE_TABLES:
        if intent.scope != "media" or not intent.media_id:
            return 0
        if table_name == "brain_observations":
            mid = str(person_id or "").strip() or None
            return 1 if mid == intent.media_id else 0
        return 1
    if intent.scope != "person" or not intent.person_id:
        return 0
    pid = str(person_id or "").strip() or None
    fid = str(face_id or "").strip() or None
    if table_name == "persons":
        return 1 if pid == intent.person_id else 0
    if table_name == "faces":
        return 1 if pid == intent.person_id else 0
    if table_name == "decisions":
        if pid and pid == intent.person_id:
            return 1
        if fid and fid in intent.face_ids:
            return 1
        return 0
    return 0


def install_erasure_guard(conn: sqlite3.Connection) -> None:
    """Register the fail-closed erasure check on a writable connection."""
    conn.create_function("semblon_erasure_ok", 4, _sql_erasure_ok, deterministic=False)
'''


FORGET_TEXT = '''"""Take pictures out of the library after their files were moved to the Recycle Bin.

The library lists only pictures that exist. When a file goes to the Bin, everything the library
learned from it (the entry, the faces found in it, their saved looks) is removed, so it can no longer
appear in the Roll, in People or in a search. Nothing on disk is touched. If the file is restored
from the Bin, looking through its folder again adds it back like any new picture.
"""

from __future__ import annotations

from pathlib import Path

from semblon.erasure_intent import ErasureIntent, erasure_authorized
from semblon.store import (
    connect,
    delete_observation_tree,
    exec_in_chunks,
    init_db,
    rows_in_chunks,
    writer_lock,
)


def forget_files(store: Path, paths: list[str], keep: list[str] | None = None) -> int:
    """Remove the library entries for these file paths. Returns how many pictures were removed.

    ``keep`` lists files that stay. An exact copy shares its entry with the copy that stays, so that
    entry is pointed at the kept file instead of being removed.
    """
    wanted = [str(p) for p in paths if p]
    if not wanted or not Path(store).is_file():
        return 0
    conn = connect(Path(store))
    init_db(conn)
    removed = 0
    try:
        with writer_lock():
            media_ids = [
                r[0]
                for r in rows_in_chunks(conn, "SELECT media_id FROM media WHERE path IN", wanted)
            ]
            clusters: set[str] = set()
            for media_id in media_ids:
                if keep:
                    marks = ",".join("?" * len(keep))
                    kept = conn.execute(
                        f"SELECT path FROM work_items WHERE media_id=? AND path IN ({marks})",
                        (media_id, *keep),
                    ).fetchone()
                    if kept:
                        conn.execute("UPDATE media SET path=? WHERE media_id=?", (kept[0], media_id))
                        continue
                for (obs_id,) in conn.execute(
                    "SELECT observation_id FROM observations WHERE media_id=?", (media_id,)
                ).fetchall():
                    for (cid,) in conn.execute(
                        "SELECT DISTINCT cluster_id FROM faces WHERE observation_id=? AND cluster_id IS NOT NULL",
                        (obs_id,),
                    ).fetchall():
                        clusters.add(cid)
                    delete_observation_tree(conn, obs_id)
                track_ids = [r[0] for r in conn.execute("SELECT track_id FROM tracks WHERE media_id=?", (media_id,))]
                if track_ids:
                    exec_in_chunks(conn, "DELETE FROM track_members WHERE track_id IN", track_ids)
                    exec_in_chunks(conn, "DELETE FROM tracks WHERE track_id IN", track_ids)
                brain_intent = ErasureIntent(
                    requestor="user",
                    scope="media",
                    reason="forget media",
                    authorized_by="forget.forget_files",
                    media_id=str(media_id),
                )
                with erasure_authorized(brain_intent):
                    if conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='brain_observations'"
                    ).fetchone():
                        conn.execute(
                            "DELETE FROM brain_observations WHERE media_id=?",
                            (media_id,),
                        )
                    if conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='brain_nodes'"
                    ).fetchone():
                        photo = conn.execute(
                            "SELECT id FROM brain_nodes WHERE node_type='Photo' AND label=?",
                            (media_id,),
                        ).fetchone()
                        if photo:
                            pid = int(photo[0])
                            conn.execute(
                                "DELETE FROM brain_edges WHERE source_node_id=? OR target_node_id=?",
                                (pid, pid),
                            )
                            conn.execute("DELETE FROM brain_nodes WHERE id=?", (pid,))
                    conn.execute("DELETE FROM media WHERE media_id=?", (media_id,))
                removed += 1
            exec_in_chunks(conn, "DELETE FROM work_items WHERE path IN", wanted)
            if clusters:
                from semblon.erasure import _clear_centroids_after_erasure

                _clear_centroids_after_erasure(conn, sorted(clusters))
            conn.commit()
    finally:
        conn.close()
    return removed
'''


def patch_store(text: str) -> str:
    if 'SCHEMA_VERSION = "12"' in text and "MIGRATION_12" in text:
        return text
    if 'SCHEMA_VERSION = "8"' not in text:
        raise SystemExit("store.py: unexpected SCHEMA_VERSION (expected 8 to patch)")
    text = text.replace('SCHEMA_VERSION = "8"', 'SCHEMA_VERSION = "12"', 1)

    old_lib = '''LIBRARY_TABLES = (
    "category_coverage",
    "work_items",
    "eval_pairs",
    "eval_sets",
    "identify_evaluations",'''
    new_lib = '''LIBRARY_TABLES = (
    "category_coverage",
    "work_items",
    "eval_pairs",
    "eval_sets",
    "brain_evidence",
    "brain_edges",
    "brain_nodes",
    "brain_observations",
    "brain_capabilities",
    "brain_benchmarks",
    "identify_evaluations",'''
    if old_lib not in text:
        raise SystemExit("store.py: LIBRARY_TABLES block not found")
    text = text.replace(old_lib, new_lib, 1)

    old_mig = '''MIGRATIONS = (
    (2, MIGRATION_2),
    (3, MIGRATION_3),
    (4, MIGRATION_4),
    (5, MIGRATION_5),
    (6, MIGRATION_6),
    (7, MIGRATION_7),
    (8, MIGRATION_8),
)'''
    new_mig = '''# BRAIN migrations 9-12. Loaded by file path to avoid circular import
# (store -> brain.__init__ -> object_cluster -> cluster -> store).
import importlib.util as _ilu
from pathlib import Path as _Path

_brain_mig = _Path(__file__).resolve().parent / "brain" / "_schema_migrations.py"
_spec = _ilu.spec_from_file_location("semblon_brain_schema_migrations", _brain_mig)
_mod = _ilu.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
MIGRATION_9 = _mod.MIGRATION_9
MIGRATION_10_IDENTIFY_EVAL = _mod.MIGRATION_10_IDENTIFY_EVAL
MIGRATION_10_TABLES = _mod.MIGRATION_10_TABLES
MIGRATION_11_IDENTIFY_EVAL = _mod.MIGRATION_11_IDENTIFY_EVAL
MIGRATION_12 = _mod.MIGRATION_12
del _ilu, _Path, _brain_mig, _spec, _mod

MIGRATIONS = (
    (2, MIGRATION_2),
    (3, MIGRATION_3),
    (4, MIGRATION_4),
    (5, MIGRATION_5),
    (6, MIGRATION_6),
    (7, MIGRATION_7),
    (8, MIGRATION_8),
    (9, MIGRATION_9),
    (10, None),
    (11, None),
    (12, None),
)'''
    if old_mig not in text:
        raise SystemExit("store.py: MIGRATIONS block not found")
    text = text.replace(old_mig, new_mig, 1)

    old_loop = '''        if version == 4:
            _apply_migration_4(conn, now, fail_after=fail_after)
        else:
            conn.executescript(sql)
            _stamp_schema(conn, version, now)
        v = version
    conn.commit()
    return v


def init_db(conn: sqlite3.Connection) -> None:'''
    new_loop = '''        if version == 4:
            _apply_migration_4(conn, now, fail_after=fail_after)
        elif version == 10:
            _apply_migration_10(conn, now)
        elif version == 11:
            _apply_migration_11(conn, now)
        elif version == 12:
            _apply_migration_12(conn, now)
        else:
            conn.executescript(sql)
            _stamp_schema(conn, version, now)
        v = version
    conn.commit()
    return v


def _apply_migration_10(conn: sqlite3.Connection, now: str) -> None:
    conn.executescript(MIGRATION_10_TABLES)
    if _table_exists(conn, "identify_evaluations"):
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='identify_evaluations'"
        ).fetchone()
        ddl = (row[0] if row else "") or ""
        if "'tagged'" not in ddl:
            conn.executescript(MIGRATION_10_IDENTIFY_EVAL)
    _stamp_schema(conn, 10, now)


def _apply_migration_11(conn: sqlite3.Connection, now: str) -> None:
    if _table_exists(conn, "identify_evaluations"):
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='identify_evaluations'"
        ).fetchone()
        ddl = (row[0] if row else "") or ""
        if "'suggested'" not in ddl:
            conn.executescript(MIGRATION_11_IDENTIFY_EVAL)
    _stamp_schema(conn, 11, now)


def _apply_migration_12(conn: sqlite3.Connection, now: str) -> None:
    conn.executescript(MIGRATION_12)
    _stamp_schema(conn, 12, now)


def init_db(conn: sqlite3.Connection) -> None:'''
    if old_loop not in text:
        raise SystemExit("store.py: apply_migrations loop not found")
    return text.replace(old_loop, new_loop, 1)


def patch_schema_pins() -> None:
    schema_test = ROOT / "tests" / "test_schema.py"
    text = schema_test.read_text(encoding="utf-8")
    text2 = text.replace('assert SCHEMA_VERSION == "8"', 'assert SCHEMA_VERSION == "12"', 1)
    if text2 != text:
        schema_test.write_text(text2, encoding="utf-8")
    p2 = ROOT / "tests" / "test_p2_decision_erasure.py"
    text = p2.read_text(encoding="utf-8")
    old = '''        assert SCHEMA_VERSION == "8"
        ver = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert ver == "8"'''
    new = '''        assert int(SCHEMA_VERSION) >= 8
        ver = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert int(ver) >= 8'''
    if old in text:
        p2.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    mig = ROOT / "semblon" / "brain" / "_schema_migrations.py"
    if not mig.is_file():
        raise SystemExit(f"missing {mig}")
    store_text = patch_store(STORE.read_text(encoding="utf-8"))
    STORE.write_text(store_text, encoding="utf-8")
    ERASURE.write_text(ERASURE_TEXT, encoding="utf-8")
    FORGET.write_text(FORGET_TEXT, encoding="utf-8")
    patch_schema_pins()
    import importlib
    import sys

    for name in list(sys.modules):
        if name == "semblon.store" or name.startswith("semblon.store"):
            del sys.modules[name]
    store = importlib.import_module("semblon.store")
    assert store.SCHEMA_VERSION == "12", store.SCHEMA_VERSION
    assert [v for v, _ in store.MIGRATIONS] == list(range(2, 13))
    print("wired SCHEMA_VERSION=12")


if __name__ == "__main__":
    main()
