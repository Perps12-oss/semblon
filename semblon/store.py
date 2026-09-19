"""SQLite store from Contracts V1.1-corrected. Schema smoke only."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "2"

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
  kind            TEXT NOT NULL CHECK (kind IN ('identify','merge','split','name','reject')),
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
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


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

MIGRATIONS = ((2, MIGRATION_2),)


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


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply pending schema migrations. Identity tables (faces/clusters/persons) are unchanged."""
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
             version INTEGER PRIMARY KEY,
             applied_at TEXT NOT NULL
           );"""
    )
    v = schema_version_int(conn)
    if v == 0:
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', '1')"
        )
        v = 1
    now = datetime.now(timezone.utc).isoformat()
    for version, sql in MIGRATIONS:
        if v >= version:
            continue
        conn.executescript(sql)
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)",
            (str(version),),
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, now),
        )
        v = version
    conn.commit()
    return v


def init_db(conn: sqlite3.Connection) -> None:
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
    try:
        dst_conn = sqlite3.connect(str(dest))
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
            "SELECT run_id, notes FROM runs WHERE finished_at IS NULL AND run_id != ?",
            (except_run_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT run_id, notes FROM runs WHERE finished_at IS NULL"
        ).fetchall()
    now = datetime.now(timezone.utc).isoformat()
    stamped: list[str] = []
    for row in rows:
        rid = str(row["run_id"] if isinstance(row, sqlite3.Row) else row[0])
        notes = row["notes"] if isinstance(row, sqlite3.Row) else row[1]
        if not notes:
            notes = "interrupted"
        conn.execute(
            "UPDATE runs SET finished_at=?, notes=? WHERE run_id=? AND finished_at IS NULL",
            (now, notes, rid),
        )
        stamped.append(rid)
    if stamped:
        conn.commit()
    return stamped


def integrity_report(store: Path) -> dict:
    """Read-only integrity snapshot. Does not repair. Does not write."""
    p = Path(store)
    if not p.is_file():
        raise FileNotFoundError(p)
    conn = sqlite3.connect(f"file:{p.resolve()}?mode=ro", uri=True)
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
    n_faces = conn.execute("SELECT COUNT(*) FROM faces").fetchone()[0]
    n_persons = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    conn.close()
    ok = orphan_faces == 0 and orphan_obs == 0 and faces_missing_run == 0
    return {
        "store": str(p.resolve()),
        "schema_version": None if schema is None else schema[0],
        "ok": bool(ok),
        "unfinished_runs": unfinished,
        "orphan_faces": int(orphan_faces),
        "orphan_observations": int(orphan_obs),
        "faces_missing_run": int(faces_missing_run),
        "media": int(n_media),
        "faces": int(n_faces),
        "persons": int(n_persons),
        "note": "read-only; unfinished_runs are not completed",
    }


def restore_store(src: Path, dest: Path, *, force: bool = False) -> dict:
    """Restore a backup onto dest. Refuses to overwrite unless force=True."""
    src_path = Path(src)
    dest_path = Path(dest)
    if not src_path.is_file():
        raise FileNotFoundError(src_path)
    if dest_path.exists() and not force:
        raise FileExistsError(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(str(src_path))
    try:
        dst_conn = sqlite3.connect(str(dest_path))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    return {
        "from": str(src_path.resolve()),
        "store": str(dest_path.resolve()),
        "bytes": dest_path.stat().st_size,
    }
