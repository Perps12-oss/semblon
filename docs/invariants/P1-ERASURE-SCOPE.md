# P1 erasure scope (draft — pre–Gate B)

**Status:** Draft for review before `identify_evaluations` exists.  
**Finalisation:** Tied to the S3 additive migration commit; until then this is the intended registration.

## Purpose

Register personal-data surfaces introduced by P1 identity evaluation durability so P2 ErasureIntent work inherits an explicit scope (no orphan probe references).

## Tables / rows in scope

| Surface | When present | Erasure must |
|---|---|---|
| `identify_evaluations` (planned) | After S3 migration | Delete or anonymise rows whose probe `face_id` / gallery person refs are in the erasure set |
| Existing `decisions` (kind=`identify`) | Already in library | Unchanged by P1; remains in P2 erasure scope as today |
| `faces` / `persons` | Existing | Unchanged; P1 must not create a second identity store |

## Retention (from P1-REVIEW-DISPOSITION)

- Retain until explicit user erasure of the referenced person/face/library scope, or `wipe_library`.
- No cloud export.
- Evaluation rows must not store raw photo bytes, OCR text, or filesystem paths.

## Out of scope here

- Implementing ErasureIntent DB enforcement (P2).
- Changing `_clear_unnamed_faces` (P2).

## Open before migration lands

- Exact column list for `identify_evaluations` (probe face id, pack/contract, run/gallery context, outcome, reason, policy/threshold version).
- Down-migration that drops the table without touching other tables.
- Test that `decisions.kind` CHECK set is unchanged.
