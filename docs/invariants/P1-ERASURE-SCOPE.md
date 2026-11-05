# P1 erasure scope — `identify_evaluations`

**Status:** Finalised with schema 7 / MIGRATION_7 (S3).  
**P2 inherits:** ErasureIntent DB enforcement must cover this table; this file is the day-one registration.

## Purpose

Register personal-data surfaces introduced by durable identify evaluation so P2 ErasureIntent does not orphan probe references.

## Tables / rows in scope

| Surface | When present | Erasure must |
|---|---|---|
| `identify_evaluations` | Schema ≥ 7 | Delete rows whose `probe_face_id` or `person_id` is in the erasure set; wipe_library already lists the table in `LIBRARY_TABLES` |
| Existing `decisions` (kind=`identify`) | Already in library | Unchanged by P1; remains in P2 erasure scope as today |
| `faces` / `persons` | Existing | Unchanged; P1 must not create a second identity store |

## Columns (schema 7)

| Column | Personal-data note |
|---|---|
| `evaluation_id` | Opaque id |
| `probe_face_id` | Face reference (`ON DELETE CASCADE`) |
| `embedding_pack` / `embedding_dim` | Contract metadata only |
| `run_id` | Run context |
| `outcome` / `reason` | ACCEPT / UNKNOWN + reason code |
| `threshold` / `policy_version` | Policy metadata |
| `gallery_size` / `score_top1` / `score_top2` / `margin` | Score shape — no display names |
| `person_id` | Person reference (`ON DELETE SET NULL`); explicit delete on person erasure |
| `source` / `created_at` | Provenance |

**Forbidden in this table:** raw photo bytes, OCR text, filesystem paths, display names.

## Retention (from P1-REVIEW-DISPOSITION)

- Retain until explicit user erasure of the referenced person/face/library scope, or `wipe_library`.
- No cloud export.

## Day-one writers / deleters

| Path | Behaviour |
|---|---|
| `semblon/identify.py` `_write_evaluation` | Inserts ACCEPT/UNKNOWN rows |
| `semblon/erasure.py` `delete_person` | Deletes by `person_id` and probe `face_id` before face/person removal |
| `semblon/store.py` `delete_observation_tree` | Deletes by probe `face_id` before face removal |
| `wipe_library` | Clears via `LIBRARY_TABLES` |

## Out of scope here

- Implementing ErasureIntent DB enforcement (P2).
- Changing `_clear_unnamed_faces` SQL shape (P2); face FK uses `ON DELETE CASCADE` so unnamed clears do not IntegrityError.
