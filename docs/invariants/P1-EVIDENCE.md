# P1a evidence — Identity trust boundary

**Status:** P1a implementation evidence (Gate B + S5 CONFIRMED + adjudicator C.G.T).  
**P1 programme:** **NOT COMPLETE** — GUI (A15 / G1) and P1b (B2 → A11; A12 live disposition) remain open.  
**Freeze base:** `50722efa8a9522867e37db352c30bc5d786ec1e2`  
**Spot-check SHA:** `8f0484778d575e359b362b4ffadea716891987d3`  
**Schema:** 7 (`identify_evaluations`)  
**P0 tools modified:** no  

## Authorisation chain

| Gate | Record |
|---|---|
| P0 + incident-defender | `P0-COMPLETION-ADDENDUM.md` — B.H SIGNED |
| S5 permit list | CONFIRMED 2026-11-05; fixture amendment below |
| Adjudicator | C.G.T |
| PROCEED | User 2026-11-05 |

## A-number → brief mapping

| Plan ID | Brief / deliverable | P1a status | Notes |
|---|---|---|---|
| A1 | Fail-closed `compare()` (NaN/Inf/L2/empty pack) | **PASS** | R4–R6, R8 |
| A2 | Finite threshold gate | **PASS** | R7; `DEFAULT_THRESHOLD` value unchanged |
| A3 | Identify ACCEPT/UNKNOWN through contract | **PASS** | Probe validated before score |
| A4 | Gallery / pack gate + **independent gallery contract at load** | **PASS** | `_gallery()` calls `validate_identity_embedding` per exemplar before scoring; `compare()` still checks both sides |
| A5–A6 | Persist gate (`status='ok'` only for contract vectors) | **PASS** | Shared `_persist_faces` |
| A7–A9 | Review / search / eval via hardened `compare()` | **PASS** | No local refuse beyond A1 |
| A10 | Cluster benefit via A1 only | **observed** | `cluster.py` not edited |
| A11 | Reembed write contract | **OPEN — P1b** | Blocked on B2 |
| A12 | Live overlay as identity writer | **OPEN — P1b** | **Not** the probe/gallery compatibility check. Plan disposition: prefer `not_production_door`. Probe/gallery independent validation is **A4** (closed in P1a). Closing A12 remains an acceptance criterion for full I1 writer coverage, not optional cleanup. |
| A13 | Durable UNKNOWN (`identify_evaluations`) | **PASS** | Schema 7 + restart test |
| A14 | Typed `IdentityVector` | **skipped** | Optional; validators suffice |
| A15 | G1 People GUI: Named / Not sure peers (brief GUI / Deliverable-class) | **OPEN** | No GUI redesign this slice; D.S spot-check / G1 continuous |
| A16 | Non-face embeddings must not vote on identity | **PASS** | `compare_space` refuses face — **not** the GUI deliverable |
| A17 | ErasureIntent / `_clear_unnamed_faces` | **out (P2)** | Day-one registration only |

## `identify_evaluations` field confirmation (brief seven)

| # | Brief requirement | Column(s) | Evidence |
|---|---|---|---|
| 1 | Probe face / reference | `probe_face_id` | `test_identify_unknown_survives_store_reopen` |
| 2 | Pack identity | `embedding_pack` | same |
| 3 | Contract identity (dim) | `embedding_dim` | same (`embedding_norm` remains on `runs`; face rows carry dim+pack) |
| 4 | Run / gallery context | `run_id`, `gallery_size` | same (+ `source`) |
| 5 | Outcome + reason | `outcome`, `reason` | same; `empty_gallery` asserted |
| 6 | Policy / threshold version | `policy_version`, `threshold` | `POLICY_VERSION`; threshold frozen value policy |
| 7 | Timestamp | `created_at` | same |

## Durability (UNKNOWN restart)

| Check | Test |
|---|---|
| Persist UNKNOWN with reason | `test_identify_unknown_survives_store_reopen` |
| Close / reopen store; read all seven fields | same |
| Schema presence alone is insufficient | Restart test required; schema-only checks remain secondary |

## Gallery-side validation

| Side | When | Mechanism |
|---|---|---|
| Probe | Before score / write | `validate_identity_embedding` in `identify_face` / `identify_run` / image path |
| Gallery | At load in `_gallery()` | Same validator per exemplar; corrupt rows dropped before `_person_scores` |
| Both | At score | `compare()` re-validates probe and gallery vectors |

Test: `test_gallery_corrupt_exemplar_dropped_independently`.

## Empty gallery vs empty pack

| Case | Reason / error | Test |
|---|---|---|
| Empty **pack_id** | `CompareError` / identify refuse (R8) | `test_r8_empty_pack_must_fail_closed` |
| Empty **gallery** (no valid named exemplars) | `reason='empty_gallery'`, outcome UNKNOWN | `test_identify_unknown_when_gallery_empty` |

## Change register (§7.1)

| Change ID | Subsystem | Sites touched | Disposition before → after | Verifying test | Dynamic-site effect | Residual risk |
|---|---|---|---|---|---|---|
| A1 | `compare.py` | validate + L2 on `compare()` only | not_observed → observed | `tests/test_p1_i1_baseline_detectors.py` R4–R6,R8 | none | float32 pack noise within `L2_TOLERANCE` |
| A2 | `identify.py` / `compare.require_finite_threshold` | identify entry | not_observed → observed | R7 + `test_identify_refuses_non_finite_threshold` | none | callers that bypass identify still need their own gate |
| A3–A4 | `identify.py` | ACCEPT/UNKNOWN + pack gallery + load validate | partially_observed → observed | identify suite + gallery corrupt + empty_gallery | identify dynamic SQL unbound shape unchanged | dropped corrupt exemplars shrink gallery silently (fail closed toward UNKNOWN) |
| A5–A6 | `ingest._persist_faces` | shared persist gate | not_observed → observed | audit/negative/backfill ingest paths | none (check before INSERT) | engines emitting non-L2 now reject rather than store ok |
| A7–A9 | review/search/eval | via A1 only | observed via compare | existing review/identify suites | not_touched | local refuse beyond compare not required |
| A10 | cluster | none | observed via A1; SQL not_touched | cluster suite unchanged behaviour intent | blocked by B2 | — |
| A13 | `store.py` MIGRATION_7 + erasure/observation deletes | additive table | deferred → landed | schema / identify restart / delete_person | store migration DDL only | P1b A11 still open |
| A16 | `compare_space` | refuses face; no L2 | observed | `test_compare_rejects` | none | non-face spaces remain non-identity |

## Detectors (R1–R8)

All **fail_closed** — see `P1-REJECTION-PATH-AUDIT.md`.

## Fixture amendment (S5 post-confirm)

A5 rejects non-L2 blobs before `status='ok'`. Mock embeddings that used `np.zeros(...)` / unnormalised vectors were updated to unit L2 vectors so tests exercise the identity path rather than the reject path. Schema asserts updated 6→7 where they pinned the prior version.

| Path | Why |
|---|---|
| `tests/test_audit_regressions.py` | Unit L2 mocks |
| `tests/test_scan_tiers.py` | Unit L2 mocks + schema 7 |
| `tests/test_ingest_workers.py` | Unit L2 mocks |
| `tests/test_category_backfill.py` | schema migration assert 7 |
| `tests/test_ship_audit.py` | Unit L2 mocks where face persist |
| `tests/test_negative.py` | Unit L2 mocks |
| `tests/test_fullstack.py` | Unit L2 mocks |
| `tests/test_temporal.py` | Unit L2 mocks |
| `tests/test_progress.py` | Unit L2 mocks |
| `tests/test_visual_discovery.py` | Unit L2 mocks (region fixtures retained) |

These paths are appended to `P1-PERMIT-LIST.md` Section B (fixture amendment).

## Deferrals still open

| ID | Status |
|---|---|
| B1 | Open — not fired |
| B2 | Open — **must close before A11 / any live.py SQL-lifecycle edit (A12)** |
| D6 A11 reembed | P1b after B2 — acceptance for full I1 writer coverage |
| D7 A12 live.py | P1b — acceptance criterion for writer coverage (prefer `not_production_door` disposition with evidence); **not** probe/gallery (that is A4) |
| A15 GUI / G1 | Open — not covered by A16 |

## Verification commands (local)

```
.\.venv\Scripts\python.exe -m pytest -q tests/test_p1_i1_baseline_detectors.py tests/test_schema.py tests/test_identify.py tests/test_cluster.py tests/test_review.py tests/test_audit_regressions.py tests/test_process.py tests/test_category_backfill.py tests/test_scan_tiers.py tests/test_ingest_workers.py tests/test_negative.py tests/test_fullstack.py tests/test_temporal.py tests/test_progress.py tests/test_visual_discovery.py tests/test_ship_audit.py
```

Focused identify suite includes restart + empty_gallery + gallery-load validation.

## Privacy

No new instrumentation under `tools/p1/`. Evaluation rows omit paths/OCR/bytes/names. Trace-inspection test **not required** this slice.
