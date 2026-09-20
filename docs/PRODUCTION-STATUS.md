# Semblon production status

**Date:** 2026-09-19  
**Version:** 1.4.0 (`main` @ schema v2 write-through + optional observers)  
**Branch intent:** full-stack architecture on the frozen identity contract.

Authority: `docs/PRODUCT.md` (v1 + 2026-09-19 production amendment), `docs/CONTRACTS.md`, `docs/SEM-ARCH.md`.  
Freeze audit: `docs/PRODUCTION-AUDIT.md` (historical freeze at `8403292`). Addendum below that file records later main.

## Hierarchy

1. **Identity contract** — immutable. Unknown valid; cluster ≠ person; no silent auto-ID; native/emulated honesty. FaceKit is the only identity engine.
2. **Production capabilities** — Home/review-ui, cancel, backup, integrity, person search, Canvas overlay, schema v2 write-through, stall watchdog on Home, FaceKitProvider on ingest, sampled video tracks.
3. **Experimental / unavailable** — product-default `workers>1`, GPU when no EP, MSI+weights, 10k run, OCR/CLIP/pose unless those libraries are installed.

## COMPLETE (verified in portable pytest)

- Identity loop, FACE-002→005 evidence, S1 golden frozen
- Incremental ingest, inbox (RO), identify vs persons
- Home + review-ui; empty states; file missing; People/Unknown/Activity/Settings list windows; person search field
- Cancel (GUI + SIGINT at file boundaries); cancelled ≠ completed; partial then cancelled
- Backup/restore; integrity report; unfinished runs stamped interrupted (not completed)
- `FaceKitProvider.load()` is the ingest load path (`ingest.load_app` wraps it)
- Stall watchdog on Home status; stalled ≠ killed
- Schema v2: `observation_items`, `embeddings`, `tracks`, `observation_groups`, `relationships`, `events`
- Face dual-write as `observation_items` kind=`face` without identity vectors in `embeddings`
- DBSCAN clusters snapshot to `observation_groups` (group ≠ person)
- S6 together/events snapshot to `relationships`/`events` with `confirmed=0`
- `search --person/--people/--face/--similar` (similar is same-modality only; face refused)
- `search --lens IMAGE` coherent local workflow sections (people/similar/objects/text/concepts/memory/video presence); identity path remains separate
- `lab contract snapshot/compare` semantic drift guard (A+B no-regression gate)
- `watch`; `live` detect→track→selective embed→identify vs named persons (`--seconds 0` unbounded, `--retain-s` optional); `canvas` observation overlay
- Color-hist + OpenCV contour observers; OCR/CLIP/pose run when libraries exist, otherwise an unavailable/error item
- S7a/S7b; S6 memory
- `episodes` derived from tracks as hypotheses (`observation != track != person`)
- Process callback emits `KIND_QUEUED` before `KIND_STARTED`
- Portable CI workflow (no weight download)

## PARTIAL

- Home People/Unknown/Activity/Settings are list windows, not a full sidebar shell
- OCR/CLIP/pose: implemented behind optional imports; not in `requirements.txt`; CLIP/pose may fail without local weights (recorded as error items, not crashes)
- Canvas overlay is tk PhotoImage, not a pixel compositor
- Query-by-image / OCR retrieval are non-identity retrieval features; ranking/filtering are still evolving
## COMPLETE — ENVIRONMENT-LIMITED

- ARM64 native OpenCV ingest (binary exists; load hang)
- x64 native FACE-000 (no x64 PC here)
- Video tracking quality on real camera motion (synthetic tests only)
- Webcam/RTSP hardware validation on real devices is pending; live engine is seam-tested in portable CI

## EXPERIMENTAL

- `ingest --workers` (default 1; hash-phase parallelism; single FaceAnalysis; product default stays 1 until measured)

## DEFERRED

Identify/inbox as dedicated full pages; default GPU/workers; vector DB; PySide6 shell as the default Home.

## UNAVAILABLE

- buffalo_l redistribution / frozen installer with weights
- Legal licence sign-off
- Clean-machine MSI

## Evidence

Portable: `python -m pytest -q` (no InsightFace download).  
Live dump / 10k / GPU / real webcam: not executed this run — human verification required.
