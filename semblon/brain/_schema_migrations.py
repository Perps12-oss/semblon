"""BRAIN schema fragments for store.py migrations 9–12.

Imported by store.py so the migration SQL stays with the brain package
and is harder to lose if store.py is reset to schema 8.
"""

from __future__ import annotations

MIGRATION_9 = """
CREATE TABLE IF NOT EXISTS brain_benchmarks (
  id                INTEGER PRIMARY KEY,
  capability_id     TEXT NOT NULL,
  provider_name     TEXT NOT NULL,
  sample_hash       TEXT NOT NULL,
  coverage          REAL NOT NULL,
  quality           REAL,
  latency_p50_ms    REAL,
  latency_p95_ms    REAL,
  cost_class        TEXT NOT NULL,
  regressions_found INTEGER NOT NULL DEFAULT 0,
  run_at            TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS brain_capabilities (
  id                  INTEGER PRIMARY KEY,
  capability_id       TEXT NOT NULL,
  provider_name       TEXT NOT NULL,
  provider_kind       TEXT NOT NULL,
  model_pack_hash     TEXT,
  cost_class          TEXT NOT NULL,
  coverage            REAL,
  quality             REAL,
  latency_p50_ms      REAL,
  latency_p95_ms      REAL,
  benchmark_run_id    INTEGER REFERENCES brain_benchmarks(id),
  adopted             INTEGER NOT NULL DEFAULT 0,
  adopted_at          TEXT,
  notes               TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_brain_capabilities_cap_prov
  ON brain_capabilities(capability_id, provider_name);
"""

MIGRATION_10_TABLES = """
CREATE TABLE IF NOT EXISTS brain_observations (
  id                INTEGER PRIMARY KEY,
  media_id          TEXT NOT NULL REFERENCES media(media_id) ON DELETE CASCADE,
  region_x          REAL,
  region_y          REAL,
  region_w          REAL,
  region_h          REAL,
  capability_id     TEXT NOT NULL,
  provider_name     TEXT NOT NULL,
  model_pack_hash   TEXT,
  payload_json      TEXT NOT NULL,
  confidence        REAL,
  content_hash      TEXT,
  created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_brain_observations_media
  ON brain_observations(media_id);
CREATE INDEX IF NOT EXISTS ix_brain_observations_cap_prov
  ON brain_observations(capability_id, provider_name);
CREATE UNIQUE INDEX IF NOT EXISTS ux_brain_observations_media_cap_pack
  ON brain_observations(media_id, capability_id, IFNULL(model_pack_hash, ''));

CREATE TABLE IF NOT EXISTS brain_evidence (
  id                INTEGER PRIMARY KEY,
  observation_id    INTEGER NOT NULL REFERENCES brain_observations(id) ON DELETE CASCADE,
  edge_id           INTEGER,
  node_id           INTEGER,
  role              TEXT NOT NULL,
  weight            REAL NOT NULL DEFAULT 1.0,
  claim_key         TEXT NOT NULL,
  created_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_brain_evidence_observation
  ON brain_evidence(observation_id);

CREATE TRIGGER IF NOT EXISTS trg_erasure_brain_observations_bd
BEFORE DELETE ON brain_observations
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN semblon_erasure_ok('brain_observations', NULL, OLD.media_id, NULL) = 1 THEN NULL
    ELSE RAISE(ABORT, 'erasure intent required to delete brain observation')
  END;
END;

CREATE TRIGGER IF NOT EXISTS trg_erasure_brain_evidence_bd
BEFORE DELETE ON brain_evidence
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN semblon_erasure_ok('brain_evidence', NULL, NULL, NULL) = 1 THEN NULL
    ELSE RAISE(ABORT, 'erasure intent required to delete brain evidence')
  END;
END;
"""

MIGRATION_10_IDENTIFY_EVAL = """
CREATE TABLE identify_evaluations_new (
  evaluation_id     TEXT PRIMARY KEY,
  probe_face_id     TEXT REFERENCES faces(face_id) ON DELETE CASCADE,
  embedding_pack    TEXT NOT NULL,
  embedding_dim     INTEGER NOT NULL,
  run_id            TEXT NOT NULL REFERENCES runs(run_id),
  outcome           TEXT NOT NULL CHECK (outcome IN ('ACCEPT','UNKNOWN','tagged')),
  reason            TEXT,
  threshold         REAL NOT NULL,
  policy_version    TEXT NOT NULL,
  gallery_size      INTEGER,
  score_top1        REAL,
  score_top2        REAL,
  margin            REAL,
  person_id         TEXT REFERENCES persons(person_id) ON DELETE SET NULL,
  source            TEXT NOT NULL,
  created_at        TEXT NOT NULL
);
INSERT INTO identify_evaluations_new(
  evaluation_id, probe_face_id, embedding_pack, embedding_dim, run_id,
  outcome, reason, threshold, policy_version, gallery_size,
  score_top1, score_top2, margin, person_id, source, created_at
)
SELECT
  evaluation_id, probe_face_id, embedding_pack, embedding_dim, run_id,
  outcome, reason, threshold, policy_version, gallery_size,
  score_top1, score_top2, margin, person_id, source, created_at
FROM identify_evaluations;
DROP TABLE identify_evaluations;
ALTER TABLE identify_evaluations_new RENAME TO identify_evaluations;
CREATE INDEX IF NOT EXISTS ix_identify_evaluations_probe
  ON identify_evaluations(probe_face_id);
CREATE INDEX IF NOT EXISTS ix_identify_evaluations_run
  ON identify_evaluations(run_id);
"""

# Pre-Inc3: ACCEPT | UNKNOWN | tagged. Inc 3 adds suggested (strict superset).
MIGRATION_11_IDENTIFY_EVAL = """
CREATE TABLE identify_evaluations_new (
  evaluation_id     TEXT PRIMARY KEY,
  probe_face_id     TEXT REFERENCES faces(face_id) ON DELETE CASCADE,
  embedding_pack    TEXT NOT NULL,
  embedding_dim     INTEGER NOT NULL,
  run_id            TEXT NOT NULL REFERENCES runs(run_id),
  outcome           TEXT NOT NULL CHECK (
                      outcome IN ('ACCEPT','UNKNOWN','tagged','suggested')),
  reason            TEXT,
  threshold         REAL NOT NULL,
  policy_version    TEXT NOT NULL,
  gallery_size      INTEGER,
  score_top1        REAL,
  score_top2        REAL,
  margin            REAL,
  person_id         TEXT REFERENCES persons(person_id) ON DELETE SET NULL,
  source            TEXT NOT NULL,
  created_at        TEXT NOT NULL
);
INSERT INTO identify_evaluations_new(
  evaluation_id, probe_face_id, embedding_pack, embedding_dim, run_id,
  outcome, reason, threshold, policy_version, gallery_size,
  score_top1, score_top2, margin, person_id, source, created_at
)
SELECT
  evaluation_id, probe_face_id, embedding_pack, embedding_dim, run_id,
  outcome, reason, threshold, policy_version, gallery_size,
  score_top1, score_top2, margin, person_id, source, created_at
FROM identify_evaluations;
DROP TABLE identify_evaluations;
ALTER TABLE identify_evaluations_new RENAME TO identify_evaluations;
CREATE INDEX IF NOT EXISTS ix_identify_evaluations_probe
  ON identify_evaluations(probe_face_id);
CREATE INDEX IF NOT EXISTS ix_identify_evaluations_run
  ON identify_evaluations(run_id);
"""

MIGRATION_12 = """
CREATE TABLE IF NOT EXISTS brain_nodes (
  id                    INTEGER PRIMARY KEY,
  node_type             TEXT NOT NULL,
  label                 TEXT,
  canonical_embedding   BLOB,
  embedding_pack_hash   TEXT,
  confidence            REAL NOT NULL,
  status                TEXT NOT NULL,
  first_seen            TEXT NOT NULL,
  last_seen             TEXT NOT NULL,
  member_count          INTEGER NOT NULL DEFAULT 0,
  confidence_model_version INTEGER NOT NULL DEFAULT 1,
  created_at            TEXT NOT NULL,
  updated_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_brain_nodes_type_status
  ON brain_nodes(node_type, status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_brain_nodes_type_label
  ON brain_nodes(node_type, IFNULL(label, ''));

CREATE TABLE IF NOT EXISTS brain_edges (
  id                  INTEGER PRIMARY KEY,
  source_node_id      INTEGER NOT NULL REFERENCES brain_nodes(id) ON DELETE CASCADE,
  target_node_id      INTEGER NOT NULL REFERENCES brain_nodes(id) ON DELETE CASCADE,
  edge_type           TEXT NOT NULL,
  confidence          REAL NOT NULL,
  support_count       INTEGER NOT NULL DEFAULT 0,
  contradict_count    INTEGER NOT NULL DEFAULT 0,
  first_seen          TEXT NOT NULL,
  last_seen           TEXT NOT NULL,
  contradiction_state TEXT NOT NULL DEFAULT 'none',
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_brain_edges_src_tgt_type
  ON brain_edges(source_node_id, target_node_id, edge_type);
CREATE INDEX IF NOT EXISTS ix_brain_edges_type
  ON brain_edges(edge_type);

CREATE TRIGGER IF NOT EXISTS trg_erasure_brain_nodes_bd
BEFORE DELETE ON brain_nodes
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN semblon_erasure_ok('brain_nodes', NULL, OLD.label, NULL) = 1 THEN NULL
    ELSE RAISE(ABORT, 'erasure intent required to delete brain node')
  END;
END;

CREATE TRIGGER IF NOT EXISTS trg_erasure_brain_edges_bd
BEFORE DELETE ON brain_edges
FOR EACH ROW
BEGIN
  SELECT CASE
    WHEN semblon_erasure_ok('brain_edges', NULL, NULL, NULL) = 1 THEN NULL
    ELSE RAISE(ABORT, 'erasure intent required to delete brain edge')
  END;
END;
"""

BRAIN_LIBRARY_TABLES = (
    "brain_evidence",
    "brain_edges",
    "brain_nodes",
    "brain_observations",
    "brain_capabilities",
    "brain_benchmarks",
)
