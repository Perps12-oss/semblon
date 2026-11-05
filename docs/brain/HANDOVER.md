# BRAIN handover — cold start for next agent

**Date:** 2026-11-05  
**Branch:** `grok/p4-capability-manifest` (uncommitted BRAIN work sits on top of P4)  
**Schema:** **12** (`semblon.store.SCHEMA_VERSION`)  
**Owner intent:** Inc 1–4 accepted. Next work is **not** Inc 5 until the 100k pilot plan is explicit.

Read this file first, then `INC4.md` → `INC3.md` → `INVENTORY.md`. Do **not** invent OBS/SIM tickets or reopen identity thresholds.

---

## Two workstreams on this branch (do not conflate)

| Stream | Status | Schema claim | Docs |
|---|---|---|---|
| **Invariant P4** capability manifest | Implemented earlier on this branch | Was 8 before BRAIN | `docs/invariants/P4-COMPLETION.md`, top of `docs/BUILD-STATUS.md` |
| **BRAIN Inc 1–4** | Inc 1–4 accepted (tag sync reconciles) | **12** | `docs/brain/*` |

P4 and BRAIN share the branch by accident of sequence. BRAIN raised schema 8→12 and touched `store.py` / `erasure_intent.py` / `forget.py`. When splitting PRs, separate P4 commits from BRAIN commits if possible.

---

## Increment status board

| Inc | What | Status |
|---|---|---|
| **1** | Inventory C1–C9, registry seed, `adopted=0`, zero new models | **DONE** — `INVENTORY.md`, `registry.py`, schema 9 |
| **2** | `brain_observations` / `brain_evidence`, NanoDet wrap, `tagged` outcome, erasure gate | **DONE** — schema 10 |
| **3** | NanoDet C1 first-adoption (UNMEASURED), `FaceSuggestObserver`, `suggested` outcome, `suggest_floor=0.40` | **ACCEPTED** — schema 11; notes in `INC3.md` |
| **4** | `brain_nodes` / `brain_edges`, Tag/Photo/ObjectCluster, batch DBSCAN, C5 `existing_object_dbscan` | **ACCEPTED** — schema 12; tag sync is delete-then-insert per photo; plan `INC4.md` |
| **5+** | Temporal / re-ID / etc. | **NOT STARTED** |
| **100k pilot** | Measure C1/C4 candidates + `suggest_floor` + latency | **DEFERRED** — between Inc 4 and Inc 5 |

---

## Binding decisions (do not rediscover)

1. **Identity firewall unchanged.** No `tools/p0` edits. No `DEFAULT_THRESHOLD` / confirm retune. Geometry/objects never silently affect face identity.
2. **`suggested`** = confirmed Person with `suggest_floor ≤ score < confirm`. Reason `below_confirm_threshold`. Not “we embedded a face.”
3. **`suggest_floor=0.40` is provisional** (`provisional_until: 100k pilot`). Constant: `semblon/brain/suggest_policy.py`.
4. **Outcome casing:** P1 uppercase (`ACCEPT`, `UNKNOWN`); brain lowercase (`tagged`, `suggested`). Never ship `SUGGESTED`.
5. **`edge_type` / `node_type` / `status` = TEXT**, enums in `semblon/brain/edges.py` frozensets — **no SQLite CHECK**. Avoids a migration per new edge type.
6. **One Tag node per normalised label** (`dog`, not per-photo). Confidence aggregates support.
7. **ObjectCluster = batch-only** via `rebuild_object_clusters(conn)`. No ingest `approximate_predict` (that is Inc 11).
8. **In-house DBSCAN**, not `hdbscan` package. Provider name: `existing_object_dbscan` (C5). HDBSCAN stays dormant.
9. **Singleton `n=1` → ObjectCluster `candidate`**, not dropped.
10. **No `identify_evaluations` row for clustering.** Graph state ≠ evaluation.
11. **`confidence_model_version=1`** in `semblon/brain/confidence.py`.
12. **Zero new inference models** through Inc 4. Region embeddings already in SQLite (`modality` `region` / `region_patch`).

---

## Schema map

| Ver | Tables / change |
|---|---|
| 9 | `brain_benchmarks`, `brain_capabilities` |
| 10 | `brain_observations`, `brain_evidence` + erasure triggers; outcome adds `tagged` |
| 11 | outcome adds `suggested` |
| 12 | `brain_nodes`, `brain_edges` + erasure triggers |

SQL lives in `semblon/brain/_schema_migrations.py`.  
`store.py` loads that file via **`importlib` file path** (not `from semblon.brain…`) to avoid circular import: `store → brain.__init__ → object_cluster → cluster → store`.

Erasure: `ErasureIntent.scope` ∈ `{person, library, media}`. Brain deletes need `media` or `library`. `forget_files` wraps media delete in media-scope intent and removes Photo node + edges.

---

## Code map (BRAIN)

```
semblon/brain/
  _schema_migrations.py   # MIGRATION_9..12 SQL
  registry.py             # baselines + adopt gates
  adoption.py             # adopt_existing_nanodet_tags / adopt_existing_object_dbscan
  nanodet_observer.py     # C1 wrap
  face_suggest.py         # suggested band
  suggest_policy.py       # SUGGEST_FLOOR provisional
  evidence.py / cache.py / evaluations.py / pipeline.py / policy.py
  edges.py                # VALID_* frozensets
  confidence.py           # v1
  quantize.py             # mean L2 → int8
  graph.py                # sync_tags_from_observations, Photo/Tag/HAS_TAG
  object_cluster.py       # rebuild_object_clusters (batch DBSCAN)

docs/brain/
  INVENTORY.md  INC3.md  INC4.md  HANDOVER.md  policy.yaml

tests/brain/              # primary gate for this work
```

**Operator calls (not on every ingest):**

```python
from semblon.brain import sync_tags_from_observations, rebuild_object_clusters
sync_tags_from_observations(conn)   # C1 observations → Tag/Photo/HAS_TAG
rebuild_object_clusters(conn)       # region embeddings → ObjectCluster/HAS_OBJECT
```

---

## Verify (Windows)

```powershell
.\.venv\Scripts\python.exe -c "from semblon.store import SCHEMA_VERSION; print(SCHEMA_VERSION)"
# expect: 12

.\.venv\Scripts\python.exe -m pytest tests/brain -q --basetemp=.pytest-tmp-brain
# expect: 53 passed
```

Also updated pins: `tests/test_schema.py` → `"12"`; `tests/test_p2_decision_erasure.py` → `>= 8`.

**Known unrelated failure:** `tests/test_audit_regressions.py::test_still_byte_and_pixel_caps_do_not_store_media` fails on clean schema **8** too — do not chase as BRAIN regression.

---

## Uncommitted state (as of handover)

**Modified (BRAIN-critical):**

- `semblon/store.py` — SCHEMA 12, LIBRARY_TABLES brain_*, migrations 9–12
- `semblon/erasure_intent.py` — `scope=media` + brain tables
- `semblon/forget.py` — gated brain/Photo cleanup
- `tests/test_schema.py`, `tests/test_p2_decision_erasure.py`

**Untracked (BRAIN):**

- `semblon/brain/` entire package
- `docs/brain/`
- `tests/brain/`

**Also on branch (P4 / other — leave alone unless asked):**

- `semblon/capability_manifest.py`, Settings/preflight/identify/category_backfill, `docs/invariants/P4-COMPLETION.md`, etc.

**Do not commit** `.pytest-tmp-*` or `.rescue-compare/`.

**Operational hazard:** `store.py` / `erasure_intent.py` / `forget.py` have been silently reverted to schema 8 **multiple times** mid-session (working tree matched HEAD again). Migration SQL is durable in `semblon/brain/_schema_migrations.py`.

**If `SCHEMA_VERSION` is not `12`, re-wire immediately:**

```powershell
.\.venv\Scripts\python.exe tools\wire_brain_schema12.py
.\.venv\Scripts\python.exe -c "from semblon.store import SCHEMA_VERSION; print(SCHEMA_VERSION)"
# expect: 12
```

Then re-run `pytest tests/brain`. Do not continue coding until that prints `12`.

---

## What to do next (ordered)

1. **Inc 4 is ACCEPTED** in `INC4.md`, including the tag-sync reconcile fix (delete-then-insert per photo, `support_count=1`).
2. **Commit strategy:** prefer BRAIN commits separate from P4. Stop before push.
3. **Do not start Inc 5** until the 100k pilot scope is agreed. Pass measures (from owner notes):

   | Capability | Measure | Acceptance |
   |---|---|---|
   | C1 | NanoDet tag recall @150 | ≥ baseline |
   | C4 | Face embed quality @150 | FaceKit baseline |
   | C1 candidate | RAM++ vs NanoDet | adopt if > baseline+ε |
   | C4 candidate | AdaFace vs FaceKit | adopt if > baseline+ε |
   | `suggest_floor` | false-suggest rate | tune |
   | latency | p50/p95 | fill UNMEASURED |

4. **Inc 5** (temporal) only after that baseline exists.
5. Never CHECK-constrain `edge_type` in a later migration “for cleanliness.”

---

## Covenant reminders

- False merge > false split is **wrong** for faces — product is false split preferred; Unknown is valid.
- `cluster ≠ person`. Graph `ObjectCluster` ≠ Person.
- `report` must not write the store.
- FaceKit remains the only identity engine; pack_id includes weight hashes.
- Windows paths; space after `--out`.

---

## One-line thesis for Inc 4

The first testable BRAIN value is: **does the graph tell the user something a flat tag list cannot?** — shared Tag vocabulary + ObjectCluster over stored region embeddings, still zero new models.
