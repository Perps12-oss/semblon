# Semblon production status

**Date:** 2026-09-21  
**Version:** 1.4.0 (`main` @ schema v2 write-through + optional observers; ARCH-011 / APP-1 job door)  
**Branch intent:** full-stack architecture on the frozen identity contract.

Authority: `docs/PRODUCT.md` (v1 + 2026-09-19 production amendment), `docs/CONTRACTS.md`, `docs/SEM-ARCH-V1.4.md`.  
Freeze audit: `docs/PRODUCTION-AUDIT.md` (historical freeze at `8403292`). Addendum below that file records later main.

Canonical roadmap sequencing and reconciled status categories live in `docs/SEM-ARCH-V1.4.md`.

## Hierarchy

1. **Identity contract** — immutable. Unknown valid; cluster ≠ person; no silent auto-ID; native/emulated honesty. FaceKit is the only identity engine.
2. **Production capabilities** — accepted PySide6 Home shell (Photos/Videos/Live/People/Unknown/Activity/Settings), review mutations, cancel, backup, integrity, person search, Canvas overlay, schema v2 write-through, stall watchdog on Home, FaceKitProvider on ingest, sampled video tracks. `review-ui` remains a KEEP/evidence vertical; `review.html` is QA/forensic only.
3. **Experimental / unavailable** — product-default `workers>1`, GPU when no EP, MSI+weights, 10k run, OCR/CLIP/pose unless those libraries **and** runnable APIs are installed (import ≠ capability).

## COMPLETE (verified in portable pytest)

- Identity loop, FACE-002→005 evidence, S1 golden frozen
- Incremental ingest, inbox (RO), identify vs persons
- Home + review-ui; empty states; file missing; People/Unknown/Activity/Settings pages; person search field
- **Accepted desktop shell:** `semblon home` / `semblon desktop` → PySide6 (`semblon.desktop`). Live page overlays faces/tracks. `--legacy` keeps tkinter Home. No second GUI framework.
- ARCH-011 / APP-1: `JobEngine` is the ingest door; second submit is `JobBusy`; Home job-control (folder/Resume off, Cancel on) does not lock Review / People / Search; Review is a Toplevel on Home’s root; Review reads use `busy_timeout=5000`
- Cancel (GUI + SIGINT at file boundaries); cancelled ≠ completed; partial then cancelled
- Backup/restore; integrity report; unfinished runs stamped interrupted (not completed)
- `FaceKitProvider.load()` is the ingest load path (`ingest.load_app` wraps it)
- Stall watchdog on Home status; stalled ≠ killed
- Schema v2: `observation_items`, `embeddings`, `tracks`, `observation_groups`, `relationships`, `events`
- Face dual-write as `observation_items` kind=`face` without identity vectors in `embeddings`
- DBSCAN clusters snapshot to `observation_groups` (group ≠ person)
- S6 together/events snapshot to `relationships`/`events` with `confirmed=0`
- `search --person/--people/--face/--similar` (similar is same-modality only; face refused)
- `watch`; `live` detect→track→selective embed→identify vs named persons (`--seconds 0` unbounded, `--retain-s` optional); `canvas` observation overlay
- Color-hist + OpenCV **contour regions** (not a trained object detector); OCR/CLIP/pose only when libraries **and** runnable APIs exist — see capability matrix in `docs/SEM-EXECUTION-2026-09-21.md`
- S7a/S7b; S6 memory
- Process callback emits `KIND_QUEUED` before `KIND_STARTED`
- Portable CI workflow (no weight download)

## PARTIAL

- Home People/Unknown/Activity/Settings are functional pages inside the accepted PySide shell (not a separate WinUI app)
- OCR/CLIP/pose: implemented behind optional imports; not in `requirements.txt`; **capability ≠ import** (see observer matrix in `docs/SEM-EXECUTION-2026-09-21.md`)
- Canvas overlay is tk PhotoImage / Qt paint path, not a pixel compositor
- Object observer = OpenCV contour regions, **not** a trained detector
- Live overlays are product-wired; real webcam/RTSP hardware proof still pending

## COMPLETE — ENVIRONMENT-LIMITED

- ARM64 native OpenCV ingest (binary exists; load hang)
- x64 native FACE-000 (no x64 PC here)
- Video tracking quality on real camera motion (synthetic tests only)
- Webcam/RTSP hardware validation on real devices is pending; live engine is seam-tested in portable CI

## EXPERIMENTAL

- `ingest --workers` (default 1; hash-phase parallelism; single FaceAnalysis; product default stays 1 until measured)

## DEFERRED

Identify/inbox as dedicated full pages; default GPU/workers; vector DB. PySide6 shell promotion is **resolved** (accepted as default Home; tk `--legacy` retained).

## UNAVAILABLE

- buffalo_l redistribution / frozen installer with weights
- Legal licence sign-off
- Clean-machine MSI

## Evidence

Portable: `python -m pytest -q` (no InsightFace download).  
Live dump / 10k / GPU / real webcam: not executed this run — human verification required.
