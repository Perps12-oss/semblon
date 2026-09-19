# Semblon production status

**Date:** 2026-09-19  
**Branch intent:** finish the defined product boundary (PRODUCT v1 + KEEP surfaces), not the SEM-ARCH north-star GUI/search/objects destination.

Authority: `docs/PRODUCT.md` (frozen v1), `docs/CONTRACTS.md` (schema/CLI/runtime), `docs/SEM-ARCH.md` (north star + planned work).

## Product status

COMPLETE inside the current boundary: stills CLI, incremental ingest, conservative clustering, review/name/merge/split, identify vs persons, inbox, Home + review-ui, sampled video holdout, derived tracks, S6 memory, truthful progress, cooperative cancel, store backup/restore.

This is **not** a claim that SEM-ARCH Phases E–K exist.

## Classification

### COMPLETE

- Identity loop `cluster → review → person → name`. Cluster id is never person id.
- FACE-002→005 evidence index (`docs/FACE-GATES.md`). S1 golden frozen.
- Incremental ingest by `sha256`; inbox buckets; identify does not auto-assign.
- `process` / `home` / `review-ui` / static `review.html`.
- S7a sampled video observations; S7b derived tracks (not a table, not identity).
- S6 memory (time/place/co-appearance do not vote on identity).
- Progress `on_event` including `cancelled`; Home Cancel.
- `lab backup` / `lab restore`.
- ARCH-001 observation primitive map (`docs/CONTRACTS.md`) — docs only.

### KNOWN LIMITATION

- buffalo_l weights: internal evaluation only; not a commercial redistribution permission (`docs/licenses.md`).
- ARM64 native OpenCV ingest **blocked** (`docs/PERF-P1-ARM64.md`). S1 still uses x64 `cv2` (`0x8664`) on this ARM64 machine = `emulated`.
- x64 native FACE-000 unverified (no x64 PC).
- Experimental `ingest --workers` default 1; do not product-default workers>1 while P1 is blocked.
- Video is sampled at 1 Hz; not every frame; held out of product DBSCAN.
- Tracks are derived, not persisted. Untracked is valid.
- Home/review-ui are tkinter verticals, not the Intelligence Canvas.
- First ingest may download buffalo_l into `%USERPROFILE%\.insightface` (network for weights only). Core runtime is local-first after that.

### DEFERRED (intentionally post this boundary)

| Item | Why | Blocks production of v1+KEEP? |
|---|---|---|
| ARCH-002…004 code | docs/sketches only until a second provider is earned | no |
| ARCH-005 track table | derived tracks already KEEP | no |
| ARCH-006 relationships table | S6 derived together/history exists | no |
| ARCH-007 event entities | S6 bursts exist | no |
| ARCH-008 visual search | later | no |
| ARCH-009 general visual memory index | S6 is the current slice | no |
| ARCH-010 Intelligence Canvas | review-ui is the shipping vertical | no |
| Identify / inbox UI + POSSIBLE | CLI exists | no |
| Folder watcher | command ingest is the contract | no |
| Webcam / RTSP / live | PRODUCT v2+ | no |
| Default workers>1 / EP / GPU / batch | gated on PERF P1 | no |

### BLOCKED

- Native ARM64 OpenCV load (`opencv_geometry500.dll` hang). Do not silent-swap S1.

### POST-PRODUCTION / REJECTED as current work

Objects, OCR, CLIP, MediaPipe, vector DB, graph DB, LLM, cloud APIs, ACC, public lookup, video product DBSCAN, retuning `eps=0.40`.

## Evidence

- Unit/integration: `pytest -q` from repo root (no live InsightFace, no owner dump).
- Face gates: `docs/FACE-GATES.md`. Confirmatory 22 pairs FAR 0/11 FRR 1/11 at 0.60.
- S1 golden: `docs/S1-GOLDEN.md` run `20260913T153515Z-1e915abe`.
- PERF P0: `docs/PERF-P0-BASELINE.md`. P1 blocked.
- Workers bench: `docs/PERF-WORKERS.md` (experimental).

## Negative-test coverage

`tests/test_negative.py`, plus existing identity/review/cluster tests:

- unsupported / zero-byte / corrupt stills do not invent faces
- duplicate content is not duplicated
- interrupted ingest (NULL `finished_at`) then re-ingest does not duplicate
- cluster is not a person; naming Alice does not rename Bob
- cancel emits `cancelled`, not `completed` / `failed`
- missing store / empty store are errors, not fake boards
- backup restore roundtrip; restore refuses overwrite
- stills are not track members

## Performance

Do not open workers/EP/batch until P1 unblocks. Duplicate `imread` on stills remains a known P2 note (`docs/PERF-P0-BASELINE.md`), not an identity change.

## Security / privacy

- Local SQLite under `%LOCALAPPDATA%\Semblon` (or `--store`).
- Originals stay put. Export views are copies/hardlinks.
- No product telemetry. No ACC. No cloud identity.
- `report` does not write the store.
- Backup is an explicit copy the user chooses.

## Packaging / release

Supported install: `tools/install-windows.ps1` then double-click `semblon.cmd`.

Not a silent end-user MSI. Frozen exe + bundled weights is **blocked on licence** until a redistributable pack is chosen. Do not PyInstaller-bundle buffalo_l.

## Hardware honesty

| Claim | Status |
|---|---|
| Windows ARM64 native identity | blocked on OpenCV load; S1 is emulated x64 cv2 |
| Windows x64 native | unverified here |
| CPU FaceKit | recorded in run `runtime_json` |

## Release verification

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
.venv\Scripts\python.exe -m pytest -q
semblon.cmd --help
```
