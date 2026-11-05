# P0 — Reconciled evidence map

**Baseline HEAD:** `af0758537fdd4f5240439ef163918db14defea9d` (branch `grok/p0-invariant-evidence`, forked from `main`)  
**Reconciliation date:** 2026-11-05  
**Schema version:** `6` (`semblon/store.py` `SCHEMA_VERSION`)  
**Trace id:** `artifacts/p0/` (regenerate with commands below; large JSON is not authoritative markdown)

## Production execution path (verified in code)

```
semblon shell
  → semblon/native_shell/run.py
  → semblon/native_shell/host.py::build_shell
  → Application(store)
  → ArchiveModel + ShellBridge + QML (Table.qml)
  → JobEngine (semblon/jobs.py) for ingest / category / visual
  → process_folder (semblon/process.py) → ingest → cluster
  → run_category_backfill (semblon/category_backfill.py)
```

Job completion status is an in-process `JobResult` (`completed` / `cancelled` / `failed`). Durable progress for still tiers is `work_items.tier_done_mask`. Durable per-category progress is `category_coverage.state`. Run interruption stamps `runs.finished_at` + `notes='interrupted'` via `stamp_unfinished_runs`. Category kill recovery: `recover_interrupted` (`running` → `interrupted`).

## Source 1 — Runtime database instrumentation

**Instrument:** `tools/p0/sql_runtime_trace.py`  
- `sqlite3.connect` factory → `TracedConnection`  
- `set_authorizer` (allow-all; records action/table/column identity)  
- `set_trace_callback`  
- `execute` / `executemany` / `executescript` overrides for parameter **shape/types only** (never values)  
- Explicit caller stack capture (does not rely on trace callback for stacks)

**Activate:** `SEMBLON_P0_SQL_TRACE=1` with pytest plugin `tools/p0/pytest_plugin.py`.

### Focused suite under trace (this machine)

```
$env:PYTHONPATH='tools'
$env:SEMBLON_P0_SQL_TRACE='1'
$env:SEMBLON_P0_SQL_TRACE_OUT='artifacts/p0/sql_runtime_trace.json'
.\.venv\Scripts\python.exe -m pytest -q -p p0.pytest_plugin `
  tests/test_schema.py tests/test_category_backfill.py tests/test_scan_tiers.py `
  tests/test_identify.py tests/test_process.py tests/test_production.py `
  tests/test_review.py tests/test_run_stage_resume.py tests/test_audit_regressions.py
```

| Result | Value |
|---|---|
| Outcome | **120 passed** |
| Duration | 186 s |
| Events | 95 391 |
| Connections | 39 |
| Platform | Windows x64, Python 3.12.10 (repo `.venv`) |

### Workflow smoke under trace

```
.\.venv\Scripts\python.exe tools\p0\workflow_smoke.py
```

| Step | Observed |
|---|---|
| `init_db` | schema_version `6` |
| `stamp_unfinished_runs` | unfinished run stamped |
| `recover_interrupted` | `category_coverage` `running` → `interrupted` |
| `coverage_report` | durable counts read |
| `application` | `busy=false`, `state=idle` |
| `search` | `search_people` + `search_text` executed |
| `wipe_library` | library tables cleared (originals untouched) |
| SQL events | 878 |

**Not exercised under this P0 trace (explicit):** FaceKit pack-backed ingest of a real photo folder; live PySide6 shell add-folder; MSI; ARM64 OpenCV; optional OCR/CLIP/pose/SAM2 paths; full pytest suite; kill -9 crash injection (P8).

## Source 2 — Static database access inventory

```
.\.venv\Scripts\python.exe tools\p0\sql_static_inventory.py --summary
```

| Metric | Count |
|---|---|
| Connect sites | 131 |
| Exec / helper sites | 524 |
| Dynamic SQL sites | 36 |
| Writer sites (literal INSERT/UPDATE/DELETE/…) | 183 |
| Reader sites (literal SELECT) | 265 |
| Tables named in literal SQL | 30 |

Top writer/reader concentration (static): `store.py`, `review.py`, `erasure.py`, `ingest.py`, `process.py`, `cluster.py`, `category_backfill.py`, `visual/persist.py`, `observers.py`, `eval.py`, `search.py`, `native_shell/bridge.py` (many connects; few direct execs — uses Application/domain).

Full machine-readable inventory: `artifacts/p0/sql_static_inventory.json`.

## Source 3 — Workflow and failure-path tests

Existing tests exercised in the focused run already cover:

| Path | Evidence |
|---|---|
| Schema init / migrations incl. crash-resume of migration 4 | `tests/test_schema.py` |
| Category backfill states, missing original, unsupported outcome, interrupt recovery | `tests/test_category_backfill.py` |
| `work_items` tier mask resume | `tests/test_scan_tiers.py` |
| Identify ACCEPT/UNKNOWN, pack mismatch refusals | `tests/test_identify.py`, `tests/test_audit_regressions.py` |
| Process cancel / stage resume | `tests/test_process.py`, `tests/test_run_stage_resume.py` |
| Unfinished run stamp | `tests/test_production.py` |
| Name / merge / split / reject decisions | `tests/test_review.py` |
| Scripted store lifecycle without packs | `tools/p0/workflow_smoke.py` |

## Reconciliation

Machine summary: `artifacts/p0/reconcile.json` (from `tools/p0/reconcile.py`).

| Class | Tables / notes |
|---|---|
| Observed in both static + focused runtime | Core library tables including `media`, `runs`, `observations`, `faces`, `clusters`, `cluster_person`, `persons`, `decisions`, `embeddings`, `observation_items`, `work_items`, `category_coverage`, … |
| Static only in this trace | `hashes`, `scans` — live in `semblon/dedupe_sidecar.py` (dedupe sidecar DB). Not exercised by the focused suite. **Classified:** statically identified; runtime coverage deferred to `tests/test_dedupe_*.py` under a future P0 re-trace. Not a divergence mystery. |
| Runtime-only names | Transient/temp helpers (`tmp_*`) and SQLite internals may appear in authorizer/trace; not schema authorities. |
| Unexplained divergence | **None remaining after classifying `hashes`/`scans`.** |

### Writer classification (identity / lifecycle critical)

| Writer | Observed at runtime? | Classification |
|---|---|---|
| `ingest._persist_faces` / media claim | Yes (process/identify paths) | Classified |
| `cluster.cluster_run` + `_clear_unprotected_clusters` | Yes | Classified — severs `cluster_id` on some decisions; preserves `former_cluster_id` in policy_json for identify/note |
| `review.name_*` / merge / split / reject | Yes | Classified — human decision writers |
| `identify._write_decision` | Yes | Classified — machine identify into `decisions.kind='identify'` |
| `category_backfill._clear_unnamed_faces` | Yes (backfill tests) | Classified — **deletes `decisions` for unnamed faces** (I2 risk for P2) |
| `store.delete_observation_tree` | Present statically; exercised via erasure/forget paths in other tests | Classified — deletes `decisions` by face_id |
| `erasure.delete_person` / `wipe_library` | Yes (smoke + static) | Classified — explicit erasure; **no ErasureIntent DB gate today** |
| `reembed.py` face rewrite | Static yes; not in focused runtime | Classified: statically identified; needs P0/P2 re-trace |
| `live.py` face/decision delete | Static yes; not production shell path | Classified: research/live overlay; not production door |
| `dedupe_sidecar` hashes/scans | Static yes; runtime deferred | Classified: sidecar, not main store |

Green CI on the focused set means **that covered set** passed. It does not prove every static writer ran.

## Existing instrumentation before P0

No production use of `set_authorizer` / `set_trace_callback` existed. P0 adds opt-in tools only; they are not wired into normal `semblon shell` runs.

## CI entry points

| Entry | Role |
|---|---|
| `.github/workflows/ci.yml` | Windows `pytest -q` (no live InsightFace) |
| `tests/conftest.py` | `QT_QPA_PLATFORM=offscreen`, search sync, signal guard |
| Owner workflows | `facekit-owner`, `msi-release` (dispatch only) |

## Unresolved coverage (explicit)

1. Full pytest suite under SQL trace — **not run** (time); focused subset used.  
2. Production shell GUI smoke with real folder — **not run** on this pass.  
3. Dedupe sidecar runtime reconcile — deferred.  
4. `reembed.py` / `live.py` / `forget.py` under trace — deferred.  
5. Kill -9 job recovery — P8, not P0.  
6. FaceKit-weighted end-to-end identify on owner dump — owner machine only; not claimed here.
