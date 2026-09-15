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

Implemented now: `lab profile` (FACE-000); `ingest` (FACE-005: skip sha256 already in `media` unless `--reprocess`; same-run skip unchanged); `cluster --run`; `export --run` (read-only HTML; includes a JSON evidence block, no embeddings; `counts.unassigned` is `status=ok` faces with no `cluster_id`; export lists `decisions`); `review --run --store {merge,split,ignore,note}` (0.4; writes `decisions`; merge/split keep existing kinds; ignore/note use kind `reject` + `policy_json`; re-cluster does not clobber them); `name` / `merge` / `split` remain as aliases; `name --face` enrols an unassigned inbox face (refuses clustered faces — name the cluster); `lab observatory` snapshot / freeze / compare / enter; `lab eval` (FACE-002: create / pair / freeze / mine / score). `lab eval score` prints FAR/FRR only for a frozen `confirmatory_hard` set (`--eval-set confirmatory` or that set's id). Underpowered sets report counts and refuse rates. Remine (`lab eval mine`) writes `mined_discovery` only. `identify --run --store [{--face|--image}]` (FACE-004 / FACE-005; 1:N vs active persons on **any** run, never vs clusters; omit `--face`/`--image` to identify unnamed ok faces on `--run`; ACCEPT only if exactly one person is at/above the identity threshold; writes `decisions.kind=identify` with top1/top2/margin; does not auto-assign `faces.person_id`; `--image` probes are not enrolled). `inbox --run --store` (FACE-005; KNOWN / UNKNOWN / REVIEW_REQUIRED / REJECTED; read-only of meaning).

Not implemented: `stats`, `report`, folder watcher. Ingest-family commands that address a stored run require `--run`. `report` is read-only. Exit 0/2/3 as specified. `identify` unknown is exit 0.

`observations` is a source/frame slot (`media_id`, `frame_id`, `run_id`) for the current identity path. It is not a typed multi-kind observation schema. Do not add kind / space / payload columns to satisfy the architectural North Star.

## Metrics

FAR/FRR on confirmatory sets only. Mined tail is discovery. Remine does not refresh confirmatory.
