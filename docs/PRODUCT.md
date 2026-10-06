# Semblon — Product brief (frozen 2026-09-12)

Semblon v1 is a **personal, local-first** Windows CLI. One user. No cloud. No ACC. No GUI required.

**Successful day:** drop a folder of stills → conservative face groups → review and name people you care about → those people become a gallery for later identification.

The long-term north star is `docs/SEM-ARCH-V1.4.md`. It does **not** redefine this v1. Folder-first, face-first, local-first remains the current product. Future observers, spaces, sources, and integrations stay out until this file is explicitly amended.

## v1 in

- Folders of still photographs (~10k first target; do not design *only* for 10k)
- Command ingest (no folder watcher)
- Detect → filter → embed → compare → cluster
- HTML contact sheets (artifact, not a web app)
- CLI `merge` / `split` / `name`
- Persons only after review
- Files stay where they are; SQLite + originals authoritative
- Optional export folders as views
- Unknown is valid
- Windows ARM64 native and Windows x64 native first-class
- x64-on-ARM64 = `emulated` only
- buffalo_l for internal evaluation only

## v1 out

Public lookup · live CCTV · USB webcam · video files · ACC · mobile · multi-user · sharing · CustomTkinter · FastAPI · folder watcher (v1 “watchdog”) · automatic identity

v1 **out** “watchdog” means **folder watcher**, not `semblon/watchdog.py` (stall detector). Home constructs `Watchdog` and may show `stalled` on status without killing the job.

## v1 ship test

A folder of stills can be ingested reproducibly; faces detected/embedded/grouped conservatively; groups reviewed and corrected; people named; reviewed gallery persisted locally for later identification.

## Later (not v1)

| Version | What |
|---|---|
| v2 | USB webcam: detect → track → selective embed → identify vs persons → known/unknown (log; optional prompt to name; never force ID) |
| later | RTSP, video files, explicit click-to-lookup, ACC as **client** of standalone Semblon, licensed pack if anyone else gets a copy |

## Recorded validation (2026-09-16)

Status only. Does **not** amend v1 in/out.

FACE-002 → FACE-003 → FACE-004 → FACE-005 is recorded in `docs/FACE-GATES.md`. Live evidence: 90-still S1 dump; 22 confirmatory pairs; FAR 0/11, FRR 1/11 at frozen 0.60. “~10k first target” above is a design target, not a completed run. ARM64 OpenCV binary is proven (`0xaa64`) and not consumed by Semblon. x64 native FACE-000 is unverified (no x64 PC). Incremental ingest + inbox already exist (1.1).

## Loop (do not invert)

`cluster → review → person → name`  
Never `cluster = person`.

## Production application (amended 2026-09-19)

This amendment does **not** erase frozen v1. It records what the shipping application actually is after production engineering.

**Level 1 — identity contract (immutable):** unknown is valid; cluster ≠ person; STRONG ≠ person; no silent auto-identity; native vs emulated is labelled honestly.

**Level 2 — production capabilities (shipping):** `process` / `home` / `review-ui` (KEEP GUI; v1 still “no GUI required”); incremental ingest; backup/restore; integrity report (orphans + `PRAGMA integrity_check`; missing originals counted, do not fail `ok`); cooperative cancel (GUI + SIGINT at file boundaries); FaceKit CPU **recorded** in `runtime_json` (ingest still `load_app()`); evidence-based `search` of named persons (RO) / identify; S7a sampled video + S7b derived tracks; S6 memory; portable CI without weight download.

**Home shell IA (LOCKED 2026-10-02, legacy Tk client):** Model D — Memory-first Stage dissolve (`docs/SHELL-IA.md`). Capability Stage → Memory Canvas → contextual discovery. No permanent MAIN sidebar. Faces remain a capability, not product centre. Does not amend Level 1 identity. External feature/UX precedent map: `docs/REFERENCE-STACK.md` (companion only; does not amend this contract).

Stall watchdog (`semblon/watchdog.py`) is **wired on Home** status (`stalled` ≠ killed). It does not kill jobs. Folder watcher remains v1 **out**.

**Level 3 — experimental / unavailable:** GPU when no EP is present; buffalo_l redistribution; MSI with bundled weights; 10k live library (harness exists); optional OCR/CLIP/MediaPipe extras when not installed.

## Production UI (amended 2026-10-05)

This amendment does **not** erase frozen v1 or the 2026-09-19 amendment. It records the closed shell.

The production UI is the PySide6 archive (`semblon shell`) → `Application`. Identity contract is unchanged. `semblon home` and `review-ui` are temporary legacy clients, not a second product. `review.html` is retired. No production Review page replaces it. Baseline: `docs/ARCHITECTURE.md`. What is still open (polish, eventual Tk retirement, Windows product pass) is `docs/COMPLETION-MATRIX.md`. Find is not a V1 capability.

## Full-stack acceleration (2026-09-19)

The freeze boundary is kept as the identity contract. The architecture is expanded **in parallel**: observation-table write-through (docs call this “schema v2”; store counter `SCHEMA_VERSION=4`), folder `watch`, `live` sources, Canvas, modality-scoped search, GPU detection, configurable workers, migration engine. Extra observers (color/object always; OCR/CLIP/pose if installed) **must not** vote on identity.

Video files remain **out of frozen v1** and **in KEEP** as sampled holdout evidence. That is not a second identity engine.
