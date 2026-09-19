# Semblon production status

**Date:** 2026-09-19  
**Version:** 1.3.0  
**Branch intent:** strongest honest production engineering for the defined release boundary.

Authority: `docs/PRODUCT.md` (v1 + 2026-09-19 production amendment), `docs/CONTRACTS.md`, `docs/SEM-ARCH.md`.  
Freeze audit: `docs/PRODUCTION-AUDIT.md`.

## Hierarchy

1. **Identity contract** — immutable. Unknown valid; cluster ≠ person; no silent auto-ID; native/emulated honesty.
2. **Production capabilities** — Home/review-ui, cancel, backup, integrity, search lookup, CI, sampled video tracks. FaceKit CPU is recorded in `runtime_json`; stall watchdog exists as a library (not on the Home/`process` path).
3. **Experimental / unavailable** — workers>1, GPU, MSI+weights, Canvas, objects, 10k run.

## COMPLETE (verified in portable pytest)

- Identity loop, FACE-002→005 evidence, S1 golden frozen
- Incremental ingest, inbox (RO), identify vs persons
- Home + review-ui; empty states; file missing; People/Unknown/Activity/Settings
- Cancel (GUI + SIGINT at file boundaries); cancelled ≠ completed; partial then cancelled
- Backup/restore; integrity report; unfinished runs stamped interrupted (not completed)
- Single-decode stills path; CPU/`provider` fields in `runtime_json`
- `search --person/--people/--face`
- S7a/S7b; S6 memory
- Portable CI workflow (no weight download)

## PARTIAL

- `FaceKitProvider`: class exists; ingest still calls `load_app()` (`docs/PRODUCTION-AUDIT.md`)
- Stall watchdog: unit-tested; not wired into Home/`process`
- Home People/Unknown/Activity/Settings are dialogs, not full pages

## COMPLETE — ENVIRONMENT-LIMITED

- ARM64 native OpenCV ingest (binary exists; load hang)
- x64 native FACE-000 (no x64 PC here)
- Video tracking quality on real camera motion (synthetic tests only)

## EXPERIMENTAL

- `ingest --workers` (default 1; P1 still blocks product default)

## DEFERRED

ARCH-003…010 code, Canvas, objects/OCR/CLIP, folder watcher, webcam/RTSP, identify/inbox full UI, default GPU/workers, vector DB.

## UNAVAILABLE

- buffalo_l redistribution / frozen installer with weights
- Legal licence sign-off
- Clean-machine MSI

## Evidence

Portable: `python -m pytest -q` (no InsightFace download).  
Live dump / 10k / GPU: not executed this run — human verification required.
