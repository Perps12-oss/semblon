# BRAIN handover — cold start for next agent

**Date:** 2026-11-05  
**Branch:** `grok/p4-capability-manifest` (uncommitted BRAIN work sits on top of P4)  
**Schema:** **12** (`semblon.store.SCHEMA_VERSION`)  
**Owner intent:** Inc 1–4 accepted. Inc 5–11 are in the tree (schema still 12). The 2M pilot was skipped on 2026-11-05 before any chunk report. It is not a measurement. Do not resume it. Do not re-run the 10k. Do not wire region crops.

**Related (2026-11-05):** `grok/related-to-photo` adds Related on the production shell. See `docs/brain/RELATED.md`. Schema still 12. Do not resume 2M. Do not wire region crops.

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
| **5** | EP probe, memory governor, input yield, chunk checkpoint, status line, per-model throughput | **IN TREE** — `resources.py`, wired in `pilot.py`. Identity stays OpenCV DNN. Azure is not chosen over CPU. |
| **6** | `TEMPORAL_NEXT` by media mtime | **IN TREE** — `temporal.py` |
| **7** | `CO_OCCURS` between tags on one photo | **IN TREE** — `cooccur.py` |
| **8** | `SAME_AS` between ObjectCluster centroids | **IN TREE** — does not link Person and does not write `person_id` |
| **9** | `HAS_FACE` from `faces.cluster_id` | **IN TREE** — read-only on `faces` |
| **10** | `HAS_SCENE` from scene embeddings; `brain_gaps` is a query | **IN TREE** — no `brain_gaps` table |
| **11** | `approximate_predict` against an ObjectCluster centroid | **IN TREE** — not called from product ingest |
| **2M pilot** | Governed tag run, limit 2_000_000 | **SKIPPED** — started 2026-11-05 and stopped before a chunk report. Not a measurement. Partial store discarded. |
| **Related** | One photograph → related objects and people | **IN TREE** — `docs/brain/RELATED.md`. Does not cluster on open. |

---

## Binding decisions (do not rediscover)

1. **Identity firewall unchanged.** No `tools/p0` edits. No `DEFAULT_THRESHOLD` / confirm retune. Geometry/objects never silently affect face identity.
2. **`suggested`** = confirmed Person with `suggest_floor ≤ score < confirm`. Reason `below_confirm_threshold`. Not “we embedded a face.”
3. **`suggest_floor=0.40` is provisional** (`provisional_until: 100k pilot`). Constant: `semblon/brain/suggest_policy.py`.
4. **Outcome casing:** P1 uppercase (`ACCEPT`, `UNKNOWN`); brain lowercase (`tagged`, `suggested`). Never ship `SUGGESTED`.
5. **`edge_type` / `node_type` / `status` = TEXT**, enums in `semblon/brain/edges.py` frozensets — **no SQLite CHECK**. Avoids a migration per new edge type.
6. **One Tag node per normalised label** (`dog`, not per-photo). Confidence aggregates support.
7. **ObjectCluster batch rebuild** stays `rebuild_object_clusters(conn)`. `approximate_predict` (Inc 11) assigns one vector to an existing centroid. Product ingest does not call it.
8. **In-house DBSCAN**, not `hdbscan` package. Provider name: `existing_object_dbscan` (C5). HDBSCAN stays dormant.
9. **Singleton `n=1` → ObjectCluster `candidate`**, not dropped.
10. **No `identify_evaluations` row for clustering.** Graph state ≠ evaluation.
11. **`confidence_model_version=1`** in `semblon/brain/confidence.py`.
12. **Zero new inference models** through Inc 11. The pilot does not write region crops. Dense patch search stays the product path (`KNOWN-ISSUES.md`).

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
  object_cluster.py       # rebuild_object_clusters + approximate_predict
  resources.py            # Inc 5 governor, EP probe, checkpoint, status
  temporal.py cooccur.py same_as.py face_link.py scene_link.py
  pilot.py                # tag pilot; Inc 6–10 run once at the end

docs/brain/
  INVENTORY.md  INC3.md  INC4.md  INC5.md  HANDOVER.md  policy.yaml  KNOWN-ISSUES.md

tests/brain/              # primary gate for this work
```

**Operator calls (not on every ingest):**

```python
from semblon.brain import sync_tags_from_observations, rebuild_object_clusters
sync_tags_from_observations(conn)   # explicit operator call; not startup or ingest
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
3. **Inc 5–11 are in the tree.** Do not wire `index_image_regions` or NanoDet crops into the pilot. Do not re-run the 10k. Do not retune `suggest_floor`.
4. **2M pilot is skipped.** Do not resume `K:\semblon-stress\pilot-2m.sqlite`. Do not treat that start as a result. A future run needs a fresh store and an explicit owner request. Yandex.Disk\DCIMaw\me stays held out.
5. Never CHECK-constrain `edge_type` in a later migration “for cleanliness.” RAM++ / AdaFace / the hdbscan package stay dormant.

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
