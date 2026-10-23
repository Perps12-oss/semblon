"""SQLite store from Contracts V1.1-corrected. Schema smoke only."""

from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "4"

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS schema_meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  run_id            TEXT PRIMARY KEY,
  started_at        TEXT NOT NULL,
  finished_at       TEXT,
  software_version  TEXT NOT NULL,
  pack_id           TEXT NOT NULL,
  embedding_dim     INTEGER NOT NULL,
  embedding_norm    TEXT NOT NULL CHECK (embedding_norm IN ('l2')),
  config_json       TEXT NOT NULL,
  runtime_json      TEXT NOT NULL,
  arch              TEXT NOT NULL,
  execution         TEXT NOT NULL CHECK (execution IN ('native','emulated')),
  ort_version       TEXT,
  peak_rss_mb       REAL,
  timings_json      TEXT,
  notes             TEXT
);

CREATE TABLE IF NOT EXISTS media (
  media_id      TEXT PRIMARY KEY,
  source_type   TEXT NOT NULL CHECK (source_type IN ('folder','video','live')),
  path          TEXT NOT NULL,
  sha256        TEXT NOT NULL,
  width         INTEGER,
  height        INTEGER,
  mtime_ns      INTEGER,
  byte_size     INTEGER,
  UNIQUE (sha256)
);

CREATE TABLE IF NOT EXISTS observations (
  observation_id  TEXT PRIMARY KEY,
  media_id        TEXT NOT NULL REFERENCES media(media_id),
  frame_id        INTEGER,
  t_ms            INTEGER,
  run_id          TEXT NOT NULL REFERENCES runs(run_id),
  UNIQUE (media_id, frame_id, run_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_observations_still
  ON observations(media_id, run_id)
  WHERE frame_id IS NULL;

CREATE TABLE IF NOT EXISTS clusters (
  cluster_id    TEXT PRIMARY KEY,
  run_id        TEXT NOT NULL REFERENCES runs(run_id),
  strategy      TEXT NOT NULL,
  face_count    INTEGER NOT NULL,
  centroid      BLOB,
  min_intra     REAL,
  status        TEXT NOT NULL DEFAULT 'auto'
);

CREATE TABLE IF NOT EXISTS persons (
  person_id     TEXT PRIMARY KEY,
  display_name  TEXT,
  status        TEXT NOT NULL CHECK (status IN ('active','retired')),
  created_run   TEXT REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS faces (
  face_id           TEXT PRIMARY KEY,
  observation_id    TEXT NOT NULL REFERENCES observations(observation_id),
  run_id            TEXT NOT NULL REFERENCES runs(run_id),
  bbox_x1           REAL NOT NULL,
  bbox_y1           REAL NOT NULL,
  bbox_x2           REAL NOT NULL,
  bbox_y2           REAL NOT NULL,
  det_score         REAL NOT NULL,
  face_w            INTEGER NOT NULL,
  face_h            INTEGER NOT NULL,
  size_band         TEXT NOT NULL,
  blur              REAL,
  landmarks_json    TEXT,
  embedding         BLOB,
  embedding_pack    TEXT,
  embedding_dim     INTEGER,
  status            TEXT NOT NULL CHECK (status IN ('rejected','low_quality','ok')),
  cluster_id        TEXT REFERENCES clusters(cluster_id),
  person_id         TEXT REFERENCES persons(person_id),
  CHECK (
    embedding IS NULL OR (
      embedding_pack IS NOT NULL
      AND embedding_dim IS NOT NULL
      AND embedding_dim > 0
      AND length(embedding) = 4 * embedding_dim
    )
  )
);

CREATE TABLE IF NOT EXISTS cluster_person (
  cluster_id    TEXT NOT NULL REFERENCES clusters(cluster_id),
  person_id     TEXT NOT NULL REFERENCES persons(person_id),
  PRIMARY KEY (cluster_id, person_id)
);

CREATE TABLE IF NOT EXISTS decisions (
  decision_id     TEXT PRIMARY KEY,
  kind            TEXT NOT NULL CHECK (kind IN ('identify','merge','split','name','reject','note')),
  face_id         TEXT REFERENCES faces(face_id),
  person_id       TEXT REFERENCES persons(person_id),
  cluster_id      TEXT REFERENCES clusters(cluster_id),
  pack_id         TEXT NOT NULL,
  score_top1      REAL,
  score_top2      REAL,
  margin          REAL,
  policy_json     TEXT NOT NULL,
  run_id          TEXT NOT NULL REFERENCES runs(run_id),
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eval_sets (
  eval_set_id     TEXT PRIMARY KEY,
  kind            TEXT NOT NULL CHECK (kind IN (
                    'confirmatory_hard','mined_discovery','soft_impostor','genuine')),
  frozen          INTEGER NOT NULL CHECK (frozen IN (0,1)),
  pack_id         TEXT,
  notes           TEXT
);

CREATE TABLE IF NOT EXISTS eval_pairs (
  eval_set_id     TEXT NOT NULL REFERENCES eval_sets(eval_set_id),
  face_a          TEXT NOT NULL REFERENCES faces(face_id),
  face_b          TEXT NOT NULL REFERENCES faces(face_id),
  label           TEXT NOT NULL CHECK (label IN ('same','different')),
  stratum         TEXT NOT NULL,
  CHECK (face_a < face_b),
  PRIMARY KEY (eval_set_id, face_a, face_b)
);

CREATE INDEX IF NOT EXISTS ix_faces_run ON faces(run_id);
CREATE INDEX IF NOT EXISTS ix_faces_run_status ON faces(run_id, status);
CREATE INDEX IF NOT EXISTS ix_faces_cluster ON faces(cluster_id);
CREATE INDEX IF NOT EXISTS ix_faces_person ON faces(person_id);
CREATE INDEX IF NOT EXISTS ix_clusters_run ON clusters(run_id);
CREATE INDEX IF NOT EXISTS ix_observations_run ON observations(run_id);
CREATE INDEX IF NOT EXISTS ix_decisions_run_kind ON decisions(run_id, kind);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def connect_readonly(store: Path | str) -> sqlite3.Connection:
    """Open a store without writing. The path is URI-encoded.

    ``file:{path}?mode=ro`` is not read-only when the path contains ``#``
    (the query is dropped) and a literal ``%2F`` can point at another file.
    ``PRAGMA query_only`` stays on even if the URI flag is ignored.
    """
    path = Path(store).expanduser().resolve()
    conn = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


SQL_IN_CHUNK = 500
_WRITER = threading.RLock()

# Biometric and library tables. schema_meta and schema_migrations stay.
LIBRARY_TABLES = (
    "eval_pairs",
    "eval_sets",
    "decisions",
    "group_members",
    "relationships",
    "track_members",
    "embeddings",
    "observation_items",
    "faces",
    "cluster_person",
    "clusters",
    "tracks",
    "observation_groups",
    "observations",
    "events",
    "persons",
    "media",
    "runs",
)


@contextmanager
def writer_lock():
    """One SQLite writer at a time. Hold this across a short commit, not inference."""
    _WRITER.acquire()
    try:
        yield
    finally:
        _WRITER.release()


def _chunks(ids: list, size: int = SQL_IN_CHUNK):
    for i in range(0, len(ids), size):
        yield list(ids[i : i + size])


def exec_in_chunks(conn, sql_prefix: str, ids: list, params_prefix: tuple = ()) -> None:
    """Run a statement whose IN-list is appended. sql_prefix must not contain user text."""
    for chunk in _chunks(ids):
        marks = ",".join("?" * len(chunk))
        conn.execute(f"{sql_prefix} ({marks})", (*params_prefix, *chunk))


def rows_in_chunks(conn, sql_prefix: str, ids: list, params_prefix: tuple = ()) -> list:
    rows = []
    for chunk in _chunks(ids):
        marks = ",".join("?" * len(chunk))
        rows.extend(conn.execute(f"{sql_prefix} ({marks})", (*params_prefix, *chunk)).fetchall())
    return rows


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def delete_observation_tree(conn: sqlite3.Connection, observation_id: str) -> None:
    """Delete one observation and rows that reference it. No ON DELETE CASCADE."""
    item_ids = [
        r[0]
        for r in conn.execute(
            "SELECT item_id FROM observation_items WHERE observation_id=?",
            (observation_id,),
        ).fetchall()
    ]
    face_ids = [
        r[0]
        for r in conn.execute(
            "SELECT face_id FROM faces WHERE observation_id=?",
            (observation_id,),
        ).fetchall()
    ]
    if item_ids:
        exec_in_chunks(conn, "DELETE FROM group_members WHERE item_id IN", item_ids)
        exec_in_chunks(conn, "DELETE FROM track_members WHERE item_id IN", item_ids)
        exec_in_chunks(conn, "DELETE FROM embeddings WHERE item_id IN", item_ids)
        exec_in_chunks(conn, "DELETE FROM relationships WHERE src_item_id IN", item_ids)
        exec_in_chunks(conn, "DELETE FROM relationships WHERE dst_item_id IN", item_ids)
        exec_in_chunks(conn, "DELETE FROM observation_items WHERE item_id IN", item_ids)
    if face_ids:
        if _table_exists(conn, "eval_pairs"):
            exec_in_chunks(conn, "DELETE FROM eval_pairs WHERE face_a IN", face_ids)
            exec_in_chunks(conn, "DELETE FROM eval_pairs WHERE face_b IN", face_ids)
        exec_in_chunks(conn, "DELETE FROM decisions WHERE face_id IN", face_ids)
        exec_in_chunks(conn, "DELETE FROM faces WHERE face_id IN", face_ids)
    conn.execute("DELETE FROM observations WHERE observation_id=?", (observation_id,))


MIGRATION_2 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version    INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observation_items (
  item_id         TEXT PRIMARY KEY,
  observation_id  TEXT NOT NULL REFERENCES observations(observation_id),
  run_id          TEXT NOT NULL REFERENCES runs(run_id),
  kind            TEXT NOT NULL CHECK (kind IN ('face','object','text','pose','appearance','clip')),
  provider        TEXT NOT NULL,
  bbox_x1         REAL,
  bbox_y1         REAL,
  bbox_x2         REAL,
  bbox_y2         REAL,
  score           REAL,
  payload_json    TEXT NOT NULL DEFAULT '{}',
  face_id         TEXT REFERENCES faces(face_id)
);
CREATE TABLE IF NOT EXISTS embeddings (
  embedding_id    TEXT PRIMARY KEY,
  item_id         TEXT NOT NULL REFERENCES observation_items(item_id),
  modality        TEXT NOT NULL,
  pack_id         TEXT NOT NULL,
  embedding_dim   INTEGER NOT NULL,
  embedding       BLOB NOT NULL,
  CHECK (length(embedding) = 4 * embedding_dim)
);
CREATE TABLE IF NOT EXISTS tracks (
  track_id      TEXT PRIMARY KEY,
  media_id      TEXT NOT NULL REFERENCES media(media_id),
  run_id        TEXT NOT NULL REFERENCES runs(run_id),
  kind          TEXT NOT NULL,
  t_ms_start    INTEGER,
  t_ms_end      INTEGER,
  item_count    INTEGER NOT NULL,
  status        TEXT NOT NULL DEFAULT 'derived'
);
CREATE TABLE IF NOT EXISTS track_members (
  track_id  TEXT NOT NULL REFERENCES tracks(track_id),
  item_id   TEXT NOT NULL REFERENCES observation_items(item_id),
  t_ms      INTEGER,
  PRIMARY KEY (track_id, item_id)
);
CREATE TABLE IF NOT EXISTS observation_groups (
  group_id      TEXT PRIMARY KEY,
  run_id        TEXT NOT NULL REFERENCES runs(run_id),
  kind          TEXT NOT NULL,
  strategy      TEXT NOT NULL,
  member_count  INTEGER NOT NULL,
  status        TEXT NOT NULL DEFAULT 'auto'
);
CREATE TABLE IF NOT EXISTS group_members (
  group_id  TEXT NOT NULL REFERENCES observation_groups(group_id),
  item_id   TEXT NOT NULL REFERENCES observation_items(item_id),
  PRIMARY KEY (group_id, item_id)
);
CREATE TABLE IF NOT EXISTS relationships (
  relationship_id  TEXT PRIMARY KEY,
  run_id           TEXT NOT NULL REFERENCES runs(run_id),
  kind             TEXT NOT NULL,
  src_item_id      TEXT REFERENCES observation_items(item_id),
  dst_item_id      TEXT REFERENCES observation_items(item_id),
  src_person_id    TEXT REFERENCES persons(person_id),
  evidence_json    TEXT NOT NULL DEFAULT '{}',
  confirmed        INTEGER NOT NULL DEFAULT 0 CHECK (confirmed IN (0,1))
);
CREATE TABLE IF NOT EXISTS events (
  event_id       TEXT PRIMARY KEY,
  run_id         TEXT REFERENCES runs(run_id),
  label          TEXT,
  t_start        TEXT,
  t_end          TEXT,
  folder         TEXT,
  evidence_json  TEXT NOT NULL DEFAULT '{}',
  confirmed      INTEGER NOT NULL DEFAULT 0 CHECK (confirmed IN (0,1))
);
"""

MIGRATION_3 = """
CREATE INDEX IF NOT EXISTS ix_faces_run ON faces(run_id);
CREATE INDEX IF NOT EXISTS ix_faces_run_status ON faces(run_id, status);
CREATE INDEX IF NOT EXISTS ix_faces_cluster ON faces(cluster_id);
CREATE INDEX IF NOT EXISTS ix_faces_person ON faces(person_id);
CREATE INDEX IF NOT EXISTS ix_clusters_run ON clusters(run_id);
CREATE INDEX IF NOT EXISTS ix_observations_run ON observations(run_id);
CREATE INDEX IF NOT EXISTS ix_tracks_run ON tracks(run_id);
CREATE INDEX IF NOT EXISTS ix_observation_items_run ON observation_items(run_id);
CREATE INDEX IF NOT EXISTS ix_decisions_run_kind ON decisions(run_id, kind);
"""

MIGRATION_4 = """
CREATE TABLE IF NOT EXISTS decisions_new (
  decision_id     TEXT PRIMARY KEY,
  kind            TEXT NOT NULL CHECK (kind IN ('identify','merge','split','name','reject','note')),
  face_id         TEXT REFERENCES faces(face_id),
  person_id       TEXT REFERENCES persons(person_id),
  cluster_id      TEXT REFERENCES clusters(cluster_id),
  pack_id         TEXT NOT NULL,
  score_top1      REAL,
  score_top2      REAL,
  margin          REAL,
  policy_json     TEXT NOT NULL,
  run_id          TEXT NOT NULL REFERENCES runs(run_id),
  created_at      TEXT NOT NULL
);
INSERT INTO decisions_new(
  decision_id, kind, face_id, person_id, cluster_id, pack_id,
  score_top1, score_top2, margin, policy_json, run_id, created_at
)
SELECT
  decision_id, kind, face_id, person_id, cluster_id, pack_id,
  score_top1, score_top2, margin, policy_json, run_id, created_at
FROM decisions;
DROP TABLE decisions;
ALTER TABLE decisions_new RENAME TO decisions;
CREATE INDEX IF NOT EXISTS ix_decisions_run_kind ON decisions(run_id, kind);
"""

MIGRATIONS = (
    (2, MIGRATION_2),
    (3, MIGRATION_3),
    (4, MIGRATION_4),
)


def schema_version_int(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()
    if row is None:
        return 0
    try:
        return int(row[0] if not isinstance(row, sqlite3.Row) else row["value"])
    except (TypeError, ValueError):
        return 0


def _stamp_schema(conn: sqlite3.Connection, version: int, now: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
        (str(version),),
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
        (version, now),
    )


def _migration_4_copy(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE decisions_new (
             decision_id     TEXT PRIMARY KEY,
             kind            TEXT NOT NULL CHECK (kind IN ('identify','merge','split','name','reject','note')),
             face_id         TEXT REFERENCES faces(face_id),
             person_id       TEXT REFERENCES persons(person_id),
             cluster_id      TEXT REFERENCES clusters(cluster_id),
             pack_id         TEXT NOT NULL,
             score_top1      REAL,
             score_top2      REAL,
             margin          REAL,
             policy_json     TEXT NOT NULL,
             run_id          TEXT NOT NULL REFERENCES runs(run_id),
             created_at      TEXT NOT NULL
           )"""
    )
    conn.execute(
        """INSERT INTO decisions_new(
             decision_id, kind, face_id, person_id, cluster_id, pack_id,
             score_top1, score_top2, margin, policy_json, run_id, created_at)
           SELECT
             decision_id, kind, face_id, person_id, cluster_id, pack_id,
             score_top1, score_top2, margin, policy_json, run_id, created_at
           FROM decisions"""
    )
    conn.execute("DROP TABLE decisions")
    conn.execute("ALTER TABLE decisions_new RENAME TO decisions")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_decisions_run_kind ON decisions(run_id, kind)")


def _apply_migration_4(conn: sqlite3.Connection, now: str, *, fail_after: str | None = None) -> None:
    """Rebuild decisions in one transaction. A crash rolls back, or the next open finishes.

    Python executescript() commits before the script, and SQLite used to leave
    a dropped decisions table with the old schema version. This path does not.
    ``fail_after='drop'`` is for the crash-resume test: it raises inside the
    transaction so the caller can see the rollback.
    """
    conn.commit()
    previous = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS schema_meta (
                     key TEXT PRIMARY KEY, value TEXT NOT NULL)"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                     version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"""
            )
            has_old = _table_exists(conn, "decisions")
            has_new = _table_exists(conn, "decisions_new")
            if has_new and not has_old:
                conn.execute("ALTER TABLE decisions_new RENAME TO decisions")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS ix_decisions_run_kind ON decisions(run_id, kind)"
                )
            elif has_old and has_new:
                old_n = int(conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0])
                new_n = int(conn.execute("SELECT COUNT(*) FROM decisions_new").fetchone()[0])
                # An empty decisions table beside a populated decisions_new is the
                # crash window after DROP, if a later open recreated decisions.
                if old_n == 0 and new_n > 0:
                    conn.execute("DROP TABLE decisions")
                    conn.execute("ALTER TABLE decisions_new RENAME TO decisions")
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS ix_decisions_run_kind ON decisions(run_id, kind)"
                    )
                else:
                    conn.execute("DROP TABLE decisions_new")
                    _migration_4_copy(conn)
            elif has_old:
                _migration_4_copy(conn)
            else:
                raise sqlite3.OperationalError(
                    "schema migration 4 found neither decisions nor decisions_new"
                )
            if fail_after == "drop":
                raise RuntimeError("migration 4 interrupted after drop")
            _stamp_schema(conn, 4, now)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.isolation_level = previous


def apply_migrations(conn: sqlite3.Connection, *, fail_after: str | None = None) -> int:
    """Apply pending schema migrations. Identity tables (faces/clusters/persons) are unchanged."""
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS schema_meta (
             key   TEXT PRIMARY KEY,
             value TEXT NOT NULL
           );
           CREATE TABLE IF NOT EXISTS schema_migrations (
             version INTEGER PRIMARY KEY,
             applied_at TEXT NOT NULL
           );"""
    )
    v = schema_version_int(conn)
    if v == 0:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', '1')")
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (1, now),
        )
        v = 1
    now = datetime.now(timezone.utc).isoformat()
    for version, sql in MIGRATIONS:
        if v >= version:
            continue
        if version == 4:
            _apply_migration_4(conn, now, fail_after=fail_after)
        else:
            conn.executescript(sql)
            _stamp_schema(conn, version, now)
        v = version
    conn.commit()
    return v


def init_db(conn: sqlite3.Connection) -> None:
    # Rescue before DDL. CREATE TABLE IF NOT EXISTS decisions would otherwise
    # invent an empty decisions table and hide the rows sitting in decisions_new.
    if _table_exists(conn, "decisions_new") and not _table_exists(conn, "decisions"):
        _apply_migration_4(conn, datetime.now(timezone.utc).isoformat())
    conn.executescript(DDL)
    apply_migrations(conn)


def backup_store(store: Path, out: Path) -> dict:
    """Online SQLite backup (WAL-aware). Does not write the source store."""
    src = Path(store)
    if not src.is_file():
        raise FileNotFoundError(src)
    dest = Path(out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(str(src))
    src_conn.execute("PRAGMA busy_timeout=5000")
    try:
        dst_conn = sqlite3.connect(str(dest))
        dst_conn.execute("PRAGMA busy_timeout=5000")
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    return {
        "store": str(src.resolve()),
        "out": str(dest.resolve()),
        "bytes": dest.stat().st_size,
    }


def stamp_unfinished_runs(conn: sqlite3.Connection, *, except_run_id: str | None = None) -> list[str]:
    """Mark leftover runs (finished_at NULL) as interrupted. Never touches except_run_id.

    A killed process must not look completed. The live run is excluded.
    Existing notes (e.g. cancelled) are preserved.
    """
    if except_run_id:
        rows = conn.execute(
            "SELECT run_id FROM runs WHERE finished_at IS NULL AND run_id != ?",
            (except_run_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT run_id FROM runs WHERE finished_at IS NULL").fetchall()
    now = datetime.now(timezone.utc).isoformat()
    stamped = [str(row["run_id"] if isinstance(row, sqlite3.Row) else row[0]) for row in rows]
    if stamped:
        if except_run_id:
            conn.execute(
                """
                UPDATE runs
                SET finished_at=?, notes=COALESCE(NULLIF(notes, ''), 'interrupted')
                WHERE finished_at IS NULL AND run_id != ?
                """,
                (now, except_run_id),
            )
        else:
            conn.execute(
                """
                UPDATE runs
                SET finished_at=?, notes=COALESCE(NULLIF(notes, ''), 'interrupted')
                WHERE finished_at IS NULL
                """,
                (now,),
            )
        conn.commit()
    return stamped


def integrity_report(store: Path) -> dict:
    """Read-only integrity snapshot. Does not repair. Does not write."""
    p = Path(store)
    if not p.is_file():
        raise FileNotFoundError(p)
    conn = connect_readonly(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    schema = conn.execute(
        "SELECT value FROM schema_meta WHERE key='schema_version'"
    ).fetchone()
    unfinished = [
        r["run_id"]
        for r in conn.execute("SELECT run_id FROM runs WHERE finished_at IS NULL")
    ]
    orphan_faces = conn.execute(
        """SELECT COUNT(*) AS n FROM faces f
           WHERE NOT EXISTS (SELECT 1 FROM observations o WHERE o.observation_id=f.observation_id)"""
    ).fetchone()["n"]
    orphan_obs = conn.execute(
        """SELECT COUNT(*) AS n FROM observations o
           WHERE NOT EXISTS (SELECT 1 FROM media m WHERE m.media_id=o.media_id)"""
    ).fetchone()["n"]
    faces_missing_run = conn.execute(
        """SELECT COUNT(*) AS n FROM faces f
           WHERE NOT EXISTS (SELECT 1 FROM runs r WHERE r.run_id=f.run_id)"""
    ).fetchone()["n"]
    n_media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
    media_missing_observations = conn.execute(
        """SELECT COUNT(*) FROM media m
           WHERE NOT EXISTS (
               SELECT 1 FROM observations o WHERE o.media_id=m.media_id
           )"""
    ).fetchone()[0]
    n_faces = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
    n_persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    pragma_row = conn.execute("PRAGMA integrity_check").fetchone()
    pragma_integrity = "ok" if pragma_row is None else str(pragma_row[0])
    pragma_ok = pragma_integrity == "ok"
    media_missing_path = 0
    for row in conn.execute("SELECT path FROM media"):
        src = row["path"] if isinstance(row, sqlite3.Row) else row[0]
        if not src or not Path(src).is_file():
            media_missing_path += 1
    conn.close()
    ok = (
        orphan_faces == 0
        and orphan_obs == 0
        and faces_missing_run == 0
        and pragma_ok
    )
    return {
        "store": str(p.resolve()),
        "schema_version": None if schema is None else schema[0],
        "ok": bool(ok),
        "unfinished_runs": unfinished,
        "orphan_faces": int(orphan_faces),
        "orphan_observations": int(orphan_obs),
        "faces_missing_run": int(faces_missing_run),
        "pragma_integrity": pragma_integrity,
        "media_missing_path": int(media_missing_path),
        "media_missing_observations": int(media_missing_observations),
        "media": int(n_media),
        "faces": int(n_faces),
        "persons": int(n_persons),
        "note": (
            "read-only; unfinished_runs are not completed; "
            "media_missing_path and media_missing_observations do not fail ok"
        ),
    }


def _backup_into(src: Path, dest: Path) -> None:
    src_conn = sqlite3.connect(str(src))
    src_conn.execute("PRAGMA busy_timeout=5000")
    try:
        dst_conn = sqlite3.connect(str(dest))
        dst_conn.execute("PRAGMA busy_timeout=5000")
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def restore_store(src: Path, dest: Path, *, force: bool = False) -> dict:
    """Restore a backup onto dest. The live file stays until the copy is complete."""
    src_path = Path(src)
    dest_path = Path(dest)
    if not src_path.is_file():
        raise FileNotFoundError(src_path)
    if dest_path.exists() and not force:
        raise FileExistsError(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest_path.with_name(dest_path.name + ".restore-tmp")
    if tmp.exists():
        tmp.unlink()
    try:
        _backup_into(src_path, tmp)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise
    if dest_path.exists():
        try:
            live = sqlite3.connect(str(dest_path))
            live.execute("PRAGMA busy_timeout=5000")
            try:
                live.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                live.close()
        except sqlite3.Error:
            if tmp.exists():
                tmp.unlink()
            raise
    os.replace(tmp, dest_path)
    for sidecar in (Path(str(dest_path) + "-wal"), Path(str(dest_path) + "-shm")):
        try:
            if sidecar.exists():
                sidecar.unlink()
        except OSError:
            pass
    return {
        "from": str(src_path.resolve()),
        "store": str(dest_path.resolve()),
        "bytes": dest_path.stat().st_size,
    }
