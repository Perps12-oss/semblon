# BRAIN Increment 3 — plan (approved A + clarifications)

## Four binding clarifications

1. **`suggested` semantics (reading b):** A face embedding resembles an **existing confirmed Person** with  
   `suggest_floor ≤ similarity < confirm_threshold`.  
   Reason: `below_confirm_threshold`.  
   Not (a) “we embedded a face,” not (c) cluster membership (Inc 4+).

2. **`suggest_floor`:** Additive band in `semblon/brain/suggest_policy.py`.  
   Does **not** tune `DEFAULT_THRESHOLD` / confirm.  
   Row records both bands: `threshold` = suggest_floor; `policy_version` and `reason` include both values.

3. **`identify_evaluations.outcome` CHECK:** Strict superset.  
   Pre-Inc3 (after MIGRATION_10): `ACCEPT | UNKNOWN | tagged`.  
   Post-Inc3: `ACCEPT | UNKNOWN | tagged | suggested`.

4. **Erasure:** Confirmed in `MIGRATION_10` — `trg_erasure_brain_observations_bd` already gates deletes.  
   Inc 3 adds a face-path erasure test only; no new erasure DDL in schema 11.

## Ships

- Adopt `existing_nanodet_tags` for C1 via §6 first-adoption (UNMEASURED benchmark row required).
- `FaceSuggestObserver` (YES_WRAP existing face pack) + `outcome='suggested'`.
- Schema 11 outcome CHECK widen only.

## Does not ship

- AdaFace / RAM++ / HDBSCAN / GDINO adoption  
- Nodes / edges / cluster-sourced suggestions  
- Threshold retuning of confirm  
- Owner 150-image sample this increment (available for later measured benchmarks)

## Post-acceptance notes

### `suggest_floor` is provisional
`SUGGEST_FLOOR = 0.40` in `semblon/brain/suggest_policy.py` was set without measurement.  
**`provisional_until: 100k pilot`** — that pilot must measure false-suggest rate vs known Persons and raise/lower the floor. Do not treat 0.40 as calibrated.

### Outcome casing convention
P1-era outcomes are **uppercase** (`ACCEPT`, `UNKNOWN`).  
Brain-era outcomes are **lowercase** (`tagged`, `suggested`).  
Future values match the era they ship in — never introduce `SUGGESTED` as a synonym of `suggested`.
