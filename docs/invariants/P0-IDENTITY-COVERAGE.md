# P0 — Identity invariant (I1) coverage manifest

**Invariant:** Invalid, incompatible, corrupted or insufficient evidence can never produce identity acceptance.

**Baseline HEAD:** `af0758537fdd4f5240439ef163918db14defea9d`  
**Reconciled:** 2026-11-05  
**Trace:** focused pytest + workflow smoke under `SEMBLON_P0_SQL_TRACE=1`

Green means the listed detectors/paths were exercised or explicitly deferred — not that every possible path is proven.

## Identity space (current design)

| Concept | Implementation |
|---|---|
| Compare contract | `semblon/compare.py::compare` — pack_id equality, dim equality, blob length `4*dim`, dot product |
| Face rows | `faces.embedding`, `embedding_pack`, `embedding_dim`, CHECK length |
| Run pack | `runs.pack_id` |
| Identify | `semblon/identify.py` — gallery = active persons’ ok faces with matching pack; ACCEPT only if exactly one person ≥ threshold |
| Threshold | `semblon/eval.py::DEFAULT_THRESHOLD` (frozen; do not retune in P1) |
| Cluster ≠ person | `cluster_run` groups faces; naming via `review` writes `persons` / `cluster_person` / `faces.person_id` |
| Decisions | `decisions.kind` includes machine `identify` and human `name|reject|merge|split|note` |

**Absent today (P1 candidates, not implemented in P0):** typed `IdentityVector`; NaN/Inf rejection in `compare`; explicit L2-norm check; `identify_evaluations` table; durable UNKNOWN distinct from “never evaluated” outside optional `decisions` rows.

## Writers

| Writer | File | What it writes | Detector / test | Runtime in P0 trace? |
|---|---|---|---|---|
| Face persist (ingest) | `ingest._persist_faces` | `faces` (+ observation_items via `ensure_face_item`) | `tests/test_process.py`, ingest worker tests | Partial (process tests) |
| Face persist (people backfill) | `category_backfill.process_people` → `_persist_faces` | faces only; no person_id | `tests/test_category_backfill.py` | Yes |
| Cluster assign | `cluster.cluster_run` | `clusters`, `faces.cluster_id` | `tests/test_cluster.py` (**not** in focused P0 run) | No this trace |
| Clear unprotected clusters | `cluster._clear_unprotected_clusters` | NULL cluster_id; rewrite some decisions; delete clusters | review/process paths | Yes (process) |
| Name / merge / split | `review.py` | persons, cluster_person, faces.person_id, decisions | `tests/test_review.py` | Yes |
| Reject / rule-out | `review.py` | decisions.kind=`reject` | `tests/test_review.py`, product surface | Yes |
| Identify decision | `identify._write_decision` | decisions.kind=`identify` | `tests/test_identify.py` | Yes |
| Reembed rewrite | `reembed.py` | UPDATE/INSERT faces | dedicated reembed tests | **No this trace** |
| Live overlay cleanup | `live.py` | DELETE faces/decisions | live tests | **No this trace** (not production shell) |
| Observation tree delete | `store.delete_observation_tree` | DELETE decisions + faces + … | erasure/forget | Static; smoke wipe path |
| Person erasure | `erasure.delete_person` | DELETE person graph | erasure tests | Static + API exists |
| People backfill clear | `category_backfill._clear_unnamed_faces` | DELETE unnamed faces **and their decisions** | backfill tests | Yes — **I2 flag** |
| Eval pairs | `eval.py` | eval_sets / eval_pairs | `tests/test_eval.py` | **No this trace** |
| Embeddings non-face | `observers.persist_item` / region persist | `embeddings.modality` ≠ face identity vote | observer/region tests | Partial |

## Readers

| Reader | File | Use | Detector / test | Runtime? |
|---|---|---|---|---|
| Gallery load | `identify._gallery` | 1:N identify | `test_identify` | Yes |
| Compare | `compare.compare` | score | unit + identify | Yes |
| Cluster load ok faces | `cluster._load_ok_faces` | DBSCAN input | `test_cluster` | Deferred |
| Review board | `review_board` / adapter unresolved | UI people / Not sure | shell/people tests | Partial |
| Search people | `search.search_people` | people desk | search tests | Smoke yes |
| Eval | `eval.py` | precision | `test_eval` confirmatory policy | Deferred |
| Pack probes | `engine.discover_weight_hashes` / `pack_id` | refuse missing/mismatch | `test_audit_regressions` | Yes |

## Embedding generation paths

| Path | Notes | Coverage |
|---|---|---|
| `engine.embed_bgr` (YuNet/SFace) | Production identity embed | Needs weights; CI mostly mocked / skipped live |
| People category backfill | Same embed path | Tests mock/detect stubs |
| `identify_image` live embed | Must match run pack | `test_identify_refuses_pack_mismatch_without_writing_faces` |
| Non-face embeddings | Must not call `compare()` for face | `compare_space` refuses face |

## Pack / contract checks (today)

| Check | Where | Gap vs P1 brief |
|---|---|---|
| pack_id mismatch | `compare` raises | Same-dim different pack rejected — **yes** |
| dim mismatch | `compare` raises | **yes** |
| blob length | `compare._norm` + faces CHECK | **yes** |
| NaN / Inf | not checked | **gap** — float unpack can yield NaN; acceptance possible if scores compare oddly |
| Normalization L2 | not enforced at compare | **gap** — contract says l2 on runs; compare assumes caller |
| Threshold validation | caller supplies float | **gap** — no typed policy guard |
| Unknown contract | N/A | **gap** for P1 fail-closed envelope |
| Resume pack mismatch | ingest/audit tests | Covered for resume refuse |

## Decision / evaluation paths

| Path | Durable record | Gap |
|---|---|---|
| ACCEPT identify | `decisions` kind=identify, person_id set | Machine outcome overloaded into decisions |
| UNKNOWN identify | `decisions` kind=identify, person_id NULL when `record=True` | If `record=False`, UNKNOWN is ephemeral — **never evaluated vs UNKNOWN not distinguished** |
| Human name | decisions kind=name | OK |
| Human reject | decisions kind=reject | OK |
| Cluster rebuild | may NULL `decisions.cluster_id` for identify/note | History partially preserved via `former_cluster_id` |

## Human review paths

Covered by `review.py` + People QML (“Not sure yet”). Production door: `ShellBridge` → adapter → Application/review. Tk Home / review-ui retired.

## Migrations / cleanup / deletion

| Path | Risk to I1/I2 | Status |
|---|---|---|
| Schema migrations 2–6 | Identity tables unchanged by design | Covered `test_schema` |
| `wipe_library` | Clears biometric tables | Explicit; no ErasureIntent gate |
| `delete_person` | Removes person + faces + decisions | Explicit |
| `_clear_unnamed_faces` | Deletes decisions on unnamed faces during people redo | **P2 detector target** |
| `delete_observation_tree` | Deletes decisions | Maintenance risk |

## Missing tests (manifest debt)

1. Detector: NaN / Inf / denorm embeddings cannot ACCEPT (baseline should fail today).  
2. Detector: cross-pack same-dim acceptance impossible on every path including any missed compare call sites.  
3. Durable UNKNOWN without requiring `decisions` overload.  
4. Runtime trace of `reembed.py` and full `test_cluster.py` under P0 plugin.  
5. Guarantee every writable connection registers future P2 erasure authorizer (P2).  

## Claim limits

This manifest does **not** claim I1 is enforced. It claims the writers/readers/paths above are inventoried against baseline `af075853…` with the stated trace coverage.
