# Decision — category-specific full-library scan and backfill

**Date:** 2026-10-27  
**Status:** implemented on `feat/discover-category-entry`; full-suite evidence not recorded in this environment  
**Branch:** `feat/discover-category-entry`

## Problem

Discover now offers People, Objects, Regions and Words in photos. Those entry points currently route into existing views/search modes; they do not guarantee that every existing archive item has the corresponding observation or embedding. Search can only find stored evidence.

The existing `ShellBridge.rescanFolder()` is not a safe substitute. It calls `_start_ingest(..., reprocess=True)`, which re-enters the broad `process_folder` ingest/cluster path. `ingest.ingest()` currently loads the FaceKit provider unconditionally; `process_folder()` then runs clustering. In addition, `scan_tiers.requested_mask()` always includes the shared `TIER_OBSERVE` bit, so passing only `object` or `text` observers through the existing ingest API would still couple their completion to the shared observer tier. A category choice must not silently rerun FaceKit or mark unrelated observer work complete when the user asked for OCR, objects or region indexing.

## Decision

Implement one category-aware backfill job contract, exposed through the existing `Application` → `JobEngine` → `ShellBridge` boundary. It operates on media already present in the archive, not by creating a new archive or rescanning arbitrary folders. A category request processes only that category's required provider and writes only its observation/index data.

Categories:

1. **People** — run the existing FaceKit detection/embedding path for eligible stills (and only explicitly supported video samples). Refresh the review board from the resulting face/cluster evidence. Never auto-name, auto-assign `faces.person_id`, or change thresholds, pack identity, clustering parameters, or the review.py-only identity writer rule. Unknown remains valid.
2. **Objects** — run NanoDet only when the BYO object pack probe is ready. Save detector labels with their true provider/provenance. Contour geometry is not a COCO object label and must not be advertised as one. If the pack is absent, return UNAVAILABLE with the install/BYO explanation and do not scan every file pointlessly.
3. **Regions** — run the existing DINOv2 whole-frame and patch-map indexing path for photos missing the active region pack/depth. Preserve coverage reporting and resumable tier state. Do not run face, object, or OCR observers.
4. **Words in photos** — run the existing OCR observer only when its provider is available. Persist both text and word boxes using the existing observation contract. Distinguish missing provider, failed read, completed empty read and successful text. Do not run face, object or region observers.

## Job contract

- Enumerate eligible media from the existing archive/session and its canonical paths. Do not create another library or make copies of originals.
- Show the selected category, provider readiness, number of eligible items, progress, completed count, skipped count, and failures in plain language.
- Support cooperative pause, cancel and resume through the existing JobEngine controls. Cancellation is observed between media and at safe stage boundaries; do not promise interruption inside a model forward.
- Be idempotent: already completed work for the active provider/pack/version is skipped; changed files and changed provider packs are detected by existing canonical provenance where possible. Never duplicate observations on retry.
- Commit bounded work safely. A cancellation or provider failure must not mark unfinished media as complete.
- Report category coverage against the eligible archive set. A completed empty OCR read is not a missing OCR run; an unavailable model is not an empty result.
- Keep per-category progress/state separate. Running an Objects scan must not change People or Regions coverage.
- Reuse existing Application, JobEngine, store, observers, provider probes and search contracts. No parallel job manager, database, gallery, cloud service or model download.
- Do not route through broad `reprocess=True` ingest. The current ingest path loads FaceKit and performs clustering; it is not a category-isolated backfill API.

## Acceptance tests

1. Each category invokes only its own provider/observer; assert other provider call counts remain zero.
2. Objects with missing NanoDet returns UNAVAILABLE without decoding every media item or writing false object labels.
3. OCR missing/failed/empty/successful states remain distinct in both persistence and search.
4. Region backfill updates region coverage and patch/CLS rows without changing faces, object rows or OCR rows.
5. People backfill creates face/cluster evidence but never writes `persons` or `faces.person_id`; naming still requires `review.py`.
6. Resume skips completed items for the same pack and retries unfinished/failed items; repeated full scan is idempotent.
7. Cancel and pause are cooperative, preserve committed work, and never stamp incomplete items done.
8. A targeted scan of one category leaves all other category coverage and observations unchanged.
9. Unsupported media, missing originals and video policy are surfaced explicitly; no silent skip presented as completion.
10. Shell tests verify category-specific status/progress, cancel/resume, and honest unavailable/empty states.

## Out of scope

- A single 'scan everything' action.
- Changing identity thresholds, face model files, clustering parameters, identity assignment, or review policy.
- Installing or downloading BYO weights automatically.
- New schema columns unless implementation evidence proves existing provenance and tier state cannot safely represent the work; any schema proposal must be a separately reviewed migration.
- Changing DINOv2 architecture, object detector, OCR provider, ranking, or search semantics.
- Claiming completion from a successful job launch; completion requires per-category coverage evidence.

## Completion rule

The worker, coverage table (schema migration 6, `category_coverage`), `JobEngine.submit_category`, `Application.submit_category`, `ShellBridge.startCategoryScan`, and the Discover check controls are implemented. People does not write `persons` or `faces.person_id` and does not cluster. Objects do not call contour labelling. The broad `reprocess=True` ingest path is not used.

Targeted tests, run in this environment without PySide6 or onnxruntime:

`python3 -m pytest -q --noconftest tests/test_category_backfill.py tests/test_schema.py tests/test_scan_tiers.py tests/test_discover_categories.py`

Result: **34 passed**.

`python3 -m pytest -q --noconftest tests/test_ship_audit.py` then failed one pre-existing ingest test with `ModuleNotFoundError: onnxruntime`. The full suite was not run. Do not treat this slice as release evidence.
