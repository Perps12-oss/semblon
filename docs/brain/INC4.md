# BRAIN Increment 4 — plan (pre-questions answered)

## Edge / node vocabulary decisions (before MIGRATION_12)

### a. `edge_type` / `node_type` / `status` = TEXT + app frozensets
**Decision:** columns are `TEXT NOT NULL` (no SQLite CHECK enum).  
Enforcement: `VALID_EDGE_TYPES`, `VALID_NODE_TYPES`, `VALID_STATUSES` in `semblon/brain/edges.py`.  
Inc 4 writes only `{HAS_TAG, HAS_OBJECT}`. Later types (`HAS_FACE`, `CO_OCCURS`, …) do not require schema migrations.

### b. Tag node identity
**Decision:** **one `Tag` node per normalised label** (e.g. `Tag(label='dog')`).  
Confidence is aggregate over supporting `HAS_TAG` edges / observations (`confidence_model_version=1`).  
Not one node per (tag, photo) — that defeats the graph.

---

## Five pre-questions

### 1. ObjectCluster creation schedule
**Decision: batch-only in Inc 4.**  
`rebuild_object_clusters(conn)` runs on demand (test / explicit call).  
No ingest-path `approximate_predict`. Weekly/incremental = Inc 11.  
Named so a 500k library is not silently re-clustered on every photo.

### 2. First confidence function
**Decision:** `semblon/brain/confidence.py` with `CONFIDENCE_MODEL_VERSION = 1`.

| node_type | f_v1 |
|---|---|
| Tag | `min(1.0, 0.5 + 0.1 * support_count)` clipped from supporting edges |
| ObjectCluster | `1.0 if member_count >= 3 else 0.5` (`candidate` when &lt; 3) |
| Photo | `1.0` |

### 3. `canonical_embedding` semantics
| node_type | blob |
|---|---|
| ObjectCluster | mean of member L2 float32 vectors → **int8 quantised** (`embedding_pack_hash` = source pack) |
| Tag | **NULL** |
| Photo | **NULL** |
| Scene | not created in Inc 4 |

### 4. Empty / singleton category
**Decision:** `n=1` **produces** an `ObjectCluster` with `member_count=1`, `status='candidate'`.  
Unknown is first-class; later `brain_gaps` can surface it. No silent drop.

### 5. `identify_evaluations` for object clusters?
**Decision: no.** Graph state ≠ evaluation. No `object_clustered` outcome.

---

## HDBSCAN vs covenant (pushback)

Spec names HDBSCAN; inventory has `hdbscan` at `adopted=0` and it is **not** a product dependency.  
**Inc 4 uses in-house DBSCAN** (same algorithm family as `cluster.py`) over stored DINOv2 region vectors — registered/adopted as `existing_object_dbscan` for C5 via §6 first-adoption + UNMEASURED benchmark (same pattern as NanoDet).  
`hdbscan` package stays dormant until the 100k pilot.

Embedding source: existing SQLite `embeddings` (`modality` in `region` / `region_patch`) — **zero new inference**.

---

## Ships

- Schema 12: `brain_nodes`, `brain_edges`
- Tag + Photo nodes; `HAS_TAG` from C1 `brain_observations`
- Batch ObjectCluster rebuild; `HAS_OBJECT`
- `confidence_model_version=1`
- C5 first-adoption of `existing_object_dbscan` (UNMEASURED)
- Tests: shared Tag across photos; singleton cluster; no eval rows; types frozenset; adoption gate

## Does not ship

- CO_OCCURS / TEMPORAL / SAME_AS / HAS_FACE / HAS_SCENE  
- Incremental cluster predict  
- HDBSCAN package / AdaFace / RAM++  
- `brain_gaps` / identity_candidates  
- 100k pilot (scheduled between Inc 4 and Inc 5)

---

## Implementation status — 2026-11-05

**ACCEPTED** on `grok/p4-capability-manifest`.

Tag-sync reconcile bug found in audit and fixed before this stamp. `sync_tags_from_observations` deletes a photo's `HAS_TAG` edges and inserts one edge per current C1 label with `support_count=1`. Tag `member_count` is the count of those edges. A second sync does not raise confidence. A label removed from the C1 payload loses its edge. The Tag row stays; `member_count=0` sets `status='retracted'`, and one supporting photo sets `candidate` again (`tentative` at 2 or more).

No-argument `sync_tags_from_observations(conn)` is an explicit operator call. Ingest, startup, and `BrainPipeline` do not call it.

| Check | Evidence |
|---|---|
| Schema 12 | `SCHEMA_VERSION == "12"`; migrations 9–12 applied by `init_db` |
| Graph tables + erasure triggers | `tests/brain/test_inc4_graph.py::test_schema_12_graph_tables` |
| TEXT edge types + frozensets | `test_edge_type_text_not_check_constrained` |
| Shared Tag node | `test_shared_tag_node_across_photos` |
| Singleton ObjectCluster candidate | `test_singleton_object_cluster_candidate` |
| DBSCAN merge + singleton | `test_object_dbscan_merges_similar_regions` |
| C5 UNMEASURED adoption; hdbscan dormant | `test_adopt_object_dbscan_unmeasured` |
| No cluster eval outcomes | asserted in shared-tag + singleton tests |
| Idempotent tag sync | `test_sync_tags_is_idempotent` |
| Stale HAS_TAG removed | `test_sync_tags_removes_stale_edges` |
| Full brain suite | `pytest tests/brain` → **53 passed** |

**Entry points (batch, not ingest):** `sync_tags_from_observations(conn)`, `rebuild_object_clusters(conn)`.

**Cold-start for next agent:** `docs/brain/HANDOVER.md`.
