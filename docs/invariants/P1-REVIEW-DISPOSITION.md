# P1 plan review disposition (authorizer)

**Date:** 2026-11-05  
**P1 authorizer / named P1 signer:** B.H  
**Spot-checker:** D.S  
**Adjudicator:** C.G.T  
**S5:** **CONFIRMED** (2026-11-05) — Section B / S3 authorised; fixture/erasure amendment in permit list T03  
**Plan reviewed:** `P1-CONFIRMATION.md` + `P1-PLAN.md` (Task 1–2 accepted as reviewable baseline)  
**Production code:** **PROCEED** authorised 2026-11-05 (Gate B + S5 + C.G.T) — see `P1-EVIDENCE.md` / `P1-COMPLETION.md`  

## Header note (freeze defect)

The review message opened with the words “P0 SIGNED” while **S1** states the authorizer will not sign P0 in this disposition. **S1 body controls.** P0 sign-off remains a Gate B requirement. The conflicting header is recorded so it is not papered over.

## S1–S5

| Ask | Disposition |
|---|---|
| S1 Sign P0 / exception | **No waiver of Gate B.** Narrow pre-sign-off exception: author and commit the **red detector** for P0 issue #6 (and the eight-path audit) only. No fix merged, no schema, no deploy until Gate B. |
| S2 Name roles | P1 signer **B.H**; spot-checker **D.S**; adjudicator **C.G.T**. |
| S3 Durable UNKNOWN | **Grant** single additive migration exception for `identify_evaluations` (terms below). Migration itself **Gate B gated**. |
| S4 A11 → P1b after B2 | **Confirmed.** Deferral register row required (see register). |
| S5 §7.4 permit-list | **CONFIRMED.** T03 adds fixture amendment + `erasure.py` for A13 day-one. |

### Gate B (recorded 2026-11-05)

1. P0 sign-off — **B.H SIGNED** (see `P0-COMPLETION-ADDENDUM.md`)  
2. Incident-defender (#11) — **B.H SIGNED**  
3. Named P1 signer — **B.H**; spot-checker **D.S**; adjudicator **C.G.T** (protocol sample still for D.S)

### S3 migration terms

- Additive only: new `identify_evaluations` table; **no ALTER** on existing tables; reversible down-migration.  
- Migration lands only after Gate B.  
- Table registered in erasure scope manifest on day one (`docs/invariants/P1-ERASURE-SCOPE.md` when created) — P2 liability inherited deliberately.  
- `decisions.kind` untouched — assert with a test.  
- If org refuses migration later: P1a must drop the durable-UNKNOWN acceptance criterion in writing, signed by the same signer (scope deviation). No silent partial.

## Privacy / retention (before table creation)

`identify_evaluations` will hold probe-face references and evaluation outcomes. Personal-data rule **before** first insert:

| Rule | Value |
|---|---|
| Purpose | Durable UNKNOWN vs never-evaluated; inspectable identity evaluation history |
| Retention window | **Retain until explicit user erasure of the referenced person/face/library scope**, or wipe_library; no cloud export |
| Minimum fields intent | probe face id, embedding contract / pack id, evaluation run + gallery context ids, outcome, reason, policy/threshold version — **no raw photo bytes, no OCR text, no filesystem paths in the evaluation row** |
| Erasure | Registered in P1 erasure-scope manifest on day one; P2 ErasureIntent must cover this table |
| Logs | Parameter shape only if traced; never log scores tied to display names in diagnostic dumps without redaction policy |

## Deferral register update (S4)

| ID | Item | Owner | Phase | Trigger | Expected evidence | Status |
|---|---|---|---|---|---|---|
| B2 | reembed/live/cluster SQL trace | P1 implementer | P1 | Before those modules’ SQL/lifecycle change | Trace + reconcile under `artifacts/p1/` | Open |
| D6 | A11 reembed contract hardening | P1 implementer | **P1b** | **B2 closed** | Detector + persist tests on `reembed.py` | **Registered** — blocked on B2 |

## Corrections before Gate B (status)

| # | Correction | Status |
|---|---|---|
| 1 | Commit `artifacts/p0/MANIFEST.json` (path, sha256, timestamp) | Done; content hash `5190afbd…` chained in addendum + permit list |
| 2 | Privacy/retention stated before identify_evaluations | Done in this document; draft `P1-ERASURE-SCOPE.md` in Section A |
| 3 | Eight rejection paths as red/fail_closed tests | Done — `P1-REJECTION-PATH-AUDIT.md` + `tests/test_p1_i1_baseline_detectors.py` |
| S5-1 | Permit-list hash method byte-consistent | Done — hash excludes `**Content SHA-256` line (`7b79744e…`) |
| S5-2 | Do not mutate frozen `P0-COMPLETION.md` | Done — restored to `50722ef`; addendum only |
| S5-3 | Manifest hash frozen in evidence chain | Done — addendum + permit list |

## Authorised now

- **PROCEED (2026-11-05):** P1a Section B + S3 — `compare()` fail-closed, persist gate, schema 7 `identify_evaluations`, fixture amendments, erasure day-one.  
- **Still deferred:** A11/A12 until B2 (P1b). Spot-check sample under D.S not yet claimed.
