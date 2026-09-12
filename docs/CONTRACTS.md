# SEMBLON — Contracts V1.1-corrected
**Status:** AUTHORITATIVE schema / CLI / runtime  
**Date:** 2026-09-09  

This file is the only schema authority.  
The implementation plan is the only staging authority.  
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

`semblon lab profile --image` is implemented (FACE-000).  
ingest/cluster/export/stats/report require `--run` when added.  
report is read-only. Exit 0/2/3 as specified.

## Metrics

FAR/FRR on confirmatory sets only. Mined tail is discovery. Remine does not refresh confirmatory.
