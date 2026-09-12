"""SQLite store from Contracts V1.1-corrected. Schema smoke only."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = "1"

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
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
        ("schema_version", SCHEMA_VERSION),
    )
    conn.commit()
