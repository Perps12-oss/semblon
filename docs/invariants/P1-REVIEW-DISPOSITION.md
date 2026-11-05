# P1 plan review disposition (authorizer)

**Date:** 2026-11-05  
**P1 authorizer / named P1 signer:** B.H  
**Plan reviewed:** `P1-CONFIRMATION.md` + `P1-PLAN.md` (Task 1–2 accepted as reviewable baseline)  
**Production code:** none authorised except as stated under S1  

## Header note (freeze defect)

The review message opened with the words “P0 SIGNED” while **S1** states the authorizer will not sign P0 in this disposition. **S1 body controls.** P0 sign-off remains a Gate B requirement. The conflicting header is recorded so it is not papered over.

## S1–S5

| Ask | Disposition |
|---|---|
| S1 Sign P0 / exception | **No waiver of Gate B.** Narrow pre-sign-off exception: author and commit the **red detector** for P0 issue #6 (and the eight-path audit) only. No fix merged, no schema, no deploy until Gate B. |
| S2 Name roles | P1 signer named **B.H**. Spot-checker and adjudicator **still blocked** until named humans are supplied. Signer ≠ spot-checker. |
| S3 Durable UNKNOWN | **Grant** single additive migration exception for `identify_evaluations` (terms below). Migration itself **Gate B gated**. |
| S4 A11 → P1b after B2 | **Confirmed.** Deferral register row required (see register). |
| S5 §7.4 permit-list | Contents in `P1-PERMIT-LIST.md` (exact paths, justifications, hash). Awaiting authorizer confirm/strike. |

### Gate B (all three required)

1. P0 sign-off  
2. Incident-defender sign-off (P0 gap #11)  
3. Named P1 signer — **B.H recorded**; still need spot-checker ≠ signer and adjudicator ≠ both  

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
| 1 | Commit `artifacts/p0/MANIFEST.json` (path, sha256, timestamp) | Done in this docs/evidence commit |
| 2 | Privacy/retention stated before identify_evaluations | Done in this document |
| 3 | Eight rejection paths as red/fail_closed tests | Done — `P1-REJECTION-PATH-AUDIT.md` + `tests/test_p1_i1_baseline_detectors.py` |

## Authorised now

- Docs + permit list + manifest + baseline detectors (strict xfail for defects).  
- **Not authorised:** compare() fix, schema migration, merge of behaviour change, Task 3 deferral closure until S3/S5 closure acknowledged and Gate B where required.
