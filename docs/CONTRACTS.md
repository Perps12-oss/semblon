# SEMBLON — Contracts V1.1-corrected
**Status:** AUTHORITATIVE schema / CLI / runtime  
**Date:** 2026-09-09  
**Note:** 2026-09-13 — staging pointer and CLI surface clarified. No column changes.

This file is the only schema authority.  
Staging authority is FACE / build 0.x as mapped in `docs/SEMBLON_MATURITY_BLUEPRINT.md` §9. There is no `SEMBLON_IMPLEMENTATION_PLAN.md` and no OBS / SIM clock.  
The plan does not invent columns.  
Do not invent columns. Do not implement the pre-correction V1.1 draft.

## Pack identity

`pack_family` = insightface/buffalo_l (human label only).  
`pack_id` = family + pack_version + adapter_version + weight_sha256.  
`compare()` keys off pack_id.

## Runtime

Every run stores `runtime_json` plus columns arch, execution (native|emulated), ort_version.  
FACE-000 requires x64 native and ARM64 native or fail+emulated.

## DDL

See repository file as written in planning. Implement:

- PRAGMA WAL + foreign_keys
- runs (pack_id, runtime_json, config_json, timings_json, arch, execution)
- media UNIQUE(sha256); path is first-seen only
- observations UNIQUE(media_id, frame_id, run_id) + stills unique index WHERE frame_id IS NULL
- faces bbox x1 y1 x2 y2; embedding CHECK length=4*dim; FK cluster_id, person_id
- clusters snapshots face_count, min_intra
- persons status active|retired
- cluster_person
- decisions score_top1, score_top2, margin
- eval_sets frozen flag; confirmatory immutable
- eval_pairs CHECK (face_a < face_b)

Full SQL is in the planning pack; do not invent columns.

## CLI

Implemented now: `lab profile` (FACE-000); `ingest`; `cluster --run`; `export --run` (read-only HTML; includes a JSON evidence block, no embeddings; `counts.unassigned` is `status=ok` faces with no `cluster_id`); `name` / `merge` / `split` (FACE-003); `lab observatory` snapshot / freeze / compare / enter.

Not implemented: `stats`, `report`, `identify`. When added, ingest-family commands that address a stored run require `--run`. `report` is read-only. Exit 0/2/3 as specified.

`observations` is a source/frame slot (`media_id`, `frame_id`, `run_id`) for the current identity path. It is not a typed multi-kind observation schema. Do not add kind / space / payload columns to satisfy the architectural North Star.

## Metrics

FAR/FRR on confirmatory sets only. Mined tail is discovery. Remine does not refresh confirmatory.
