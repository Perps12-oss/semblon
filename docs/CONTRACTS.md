# SEMBLON — Contracts V1.1-corrected
**Status:** AUTHORITATIVE schema / CLI / runtime  
**Date:** 2026-09-09  
**Note:** 2026-09-13 — staging pointer and CLI surface clarified. No column changes.

This file is the only schema authority.  
Planned work is `docs/SEM-ARCH.md`. There is no `SEMBLON_IMPLEMENTATION_PLAN.md` and no OBS / SIM / FACE-n successor clock.  
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

Implemented now: `lab profile` (FACE-000); `process` (happy-path ingest -> cluster -> export review.html; owns `run_id`; default store under `%LOCALAPPDATA%\\Semblon\\store.sqlite`); `home` (double-click entry: tk Choose folder / Open Review over `process_folder` + `review-ui`; not full shell; cooperative cancel between files — cancelled is not success); `review-ui` (S8 Interactive Review slice: tkinter Name/Merge/Split/Ignore/Note over existing `review.py` APIs; `--run` optional = latest run **that has faces** so an empty FACE-005 skip-all run does not blank the board; both `review-ui` and `review.html` show `this run: N faces; store has M on run …` and missing thumbs say `file missing`; STRONG clusters stay unnamed until Name; static `review.html` remains read-only export; S8 Reviewability: video face thumbs from `path`+`frame_id`+`bbox` seek/crop, no on-disk crop dump; video unassigned faces grouped by derived Track — a track is not a person; Name defaults to **create new person** — attach only via explicit `--attach-to` / `attach_to_person_id`; Ignore hides the item from the board; Note is `decisions.kind=note`); `ingest` (FACE-005: skip sha256 already in `media` unless `--reprocess`; same-run skip unchanged; S7a: video files in the folder are sampled at 1 Hz into `observations.frame_id`/`t_ms` with `media.source_type=video`; no new columns; optional experimental `--workers N` default 1 — thread-local FaceAnalysis for stills, single SQLite writer; does not change thresholds/pack/provider); `cluster --run`; `export --run --out` (read-only HTML; includes a JSON evidence block, no embeddings; `counts.unassigned` is `status=ok` faces with no `cluster_id`; export lists `decisions`; S8 Reviewability: video face thumbs from `path`+`frame_id`+`bbox` seek/crop, same as `review-ui`, no on-disk crop dump); `export --run --views` (person folders as views; originals stay put; rejected/low_quality held out; hardlink or copy); `review --run --store {merge,split,ignore,note}` (0.4; writes `decisions`; merge/split keep existing kinds; ignore/note use kind `reject` + `policy_json`; re-cluster does not clobber them); `name` / `merge` / `split` remain as aliases; `name --face` enrols an unassigned inbox face (refuses clustered faces — name the cluster); `name --track` / `name --faces` enrol derived-track members as one person (track id is never person id; no cluster created); `lab observatory` snapshot / freeze / compare / enter; `lab eval` (FACE-002: create / pair / freeze / mine / score). `lab eval score` prints FAR/FRR only for a frozen `confirmatory_hard` set (`--eval-set confirmatory` or that set's id). Underpowered sets report counts and refuse rates. Remine (`lab eval mine`) writes `mined_discovery` only. `identify --run --store [{--face|--image}]` (FACE-004 / FACE-005; 1:N vs active persons on **any** run, never vs clusters; omit `--face`/`--image` to identify unnamed ok faces on `--run`; ACCEPT only if exactly one person is at/above the identity threshold; writes `decisions.kind=identify` with top1/top2/margin; does not auto-assign `faces.person_id`; `--image` probes are not enrolled). `inbox --run --store` (FACE-005; KNOWN / UNKNOWN / REVIEW_REQUIRED / REJECTED; read-only of meaning). `tracks --run --store` (S7b; derived IoU+time tracks per video Media; read-only; no new columns; untracked faces stay valid; not a person and not a cluster; embeddings do not vote).

`stats --run --store` (read-only JSON counts; FAR/FRR only if confirmatory is measurable). `report --run --store --out` (read-only markdown; writes `--out` only, never the store). `lab backup --store --out` (WAL-aware copy; does not write the source). `lab restore --from --store [--force]` (refuses to overwrite unless `--force`).

`memory history --person --store` / `memory together --store` / `memory events --store` (S6; read-only; optional `--run`; time from EXIF then filename then `mtime_ns`; video observations add in-file `t_ms` to that time; place is folder plus GPS if EXIF has it; named video faces appear as history items plus per-media `presence` intervals; together is same still or same clip; no geocoding; no new columns). Time/place/co-appearance must not change `compare()` or clustering.

`watch FOLDER` (poll + incremental ingest; cancellable). `live --source` (webcam index or RTSP; `source_type=live`). `canvas` (observation overlay; cluster ≠ person). Ingest-family commands that address a stored run require `--run`. Exit 0/2/3 as specified. `identify` unknown is exit 0.

`--observers` comma list: `face,color,object,text,clip,pose`. Face is identity. Extras never vote on `compare()` / DBSCAN / identify. Missing OCR/CLIP/pose libraries persist an unavailable/error item, not a crash.

`observations` remains a source/frame slot (`media_id`, `frame_id`, `run_id`) for the identity path.

Schema **v2** (migration engine) adds `observation_items`, `embeddings`, `tracks`, `observation_groups`, `relationships`, `events`. Face identity embeddings stay on `faces`. `embeddings.modality='face'` is forbidden. `compare_space()` refuses face identity. Extra observers never write `faces.person_id`.

Progress `on_event` kinds: `queued` / `started` / `progress` / `partial` / `completed` / `failed` / `cancelled` / `stalled`. Skip is an `outcome` on `progress` (`skipped_seen`, `skipped_same_run`), not a silent success. Cancel stamps `runs.finished_at` and `runs.notes=cancelled`. SIGINT is cooperative at file boundaries. Partial per-file commits remain. Cancelled work must not emit `completed`. A stall watchdog may emit `stalled`; it does not kill the job. `process --resume` / Home **Resume** (next to Cancel) continues the latest unfinished run for that folder: same `run_id` for cancelled ingest (same-run skip), then cluster, then export; completed stages are skipped (`outcome=skipped_stage`). No new columns. Progress events carry wall-clock `clock`, `elapsed_s`, and `eta_s` only when files already done give a real rate. Stills percent is `files_processed/files_total` (0–100); never invent a denominator.

`search --person` / `--people` / `--face --run` / `--similar ITEM` (lookup of named persons or identify vs persons; `--similar` is same-modality+pack only and refuses face identity; not a vector DB; similarity is not identity). `lab integrity --store` (read-only; exit 3 if unfinished/orphans). `lab models` (weight presence; does not download). `lab providers` (optional extra availability).

## Observation primitives (ARCH-001)

Docs/conceptual only. No new columns. Map of SEM-ARCH nouns onto today's store:

| Primitive | Today | In store? |
|---|---|---|
| Media | `media` (`sha256` unique, `path` first-seen, `source_type` ∈ folder\|video\|live) | yes |
| Observation | `observations` is a source/frame slot; a face observation lives in `faces` | yes (face-shaped) |
| Embedding | `faces.embedding` + run `pack_id` (family + versions + weight hashes) | yes (face only) |
| Evidence | `decisions` rows, cluster `min_intra`, export JSON evidence block | partial |
| Hypothesis / group | `clusters` (stills DBSCAN only; video held out) | yes (faces) |
| Track | derived IoU+time per video Media (`semblon tracks`); also snapshotted to `tracks` | yes (v2 snapshot; track ≠ person) |
| Entity | `persons` after `name` only | yes |
| Relationship | S6 together/history; also `relationships` with `confirmed=0` | yes (v2 snapshot) |
| Event | S6 crude time/folder bursts; also `events` with `confirmed=0` | yes (v2 snapshot) |
| Decision | `decisions` (identify/merge/split/name/reject/note) | yes |

Frozen rule: detector → observation; grouping → hypothesis; human → decision. `cluster ≠ person`. `group ≠ entity`. Unknown is valid.

Embedding envelope (conceptual): modality, provider/`pack_id`, dimensions, normalisation, version, vector. Incompatible spaces never compare. Face identity remains FaceKit/`pack_id` only.

`ObservationProvider` (sketch, not a class today): FaceKit is the first provider (face observation + embedding + bbox + quality + pack_id). No second provider is authorized.

`ObservationGroup`: today's `clusters` — related under a model/config, not “the same thing”. Do not retune `eps=0.40`.

## Metrics

FAR/FRR on confirmatory sets only. Mined tail is discovery. Remine does not refresh confirmatory.

Local dump confirmatory (`docs/FACE-002-CONFIRMATORY.md`): 22 pairs; FAR 0/11, FRR 1/11 at frozen threshold 0.60. That is harness-measurable on this dump, not a 10k or public-FRTE claim. Identify is 1:N vs named persons, never clusters. Cluster ≠ person. STRONG ≠ person until `name`. Pair labels ≠ cluster/person ground truth.

Gate index: `docs/FACE-GATES.md`. Incremental ingest + inbox are implemented (1.1). S7a sampled video ingest is implemented. Experimental `ingest --workers` exists for perf measurement (`docs/PERF-WORKERS.md`; stills only). Deferred: defaulting workers>1; CPU/GPU EP selection; provider/device/worker as product defaults.
