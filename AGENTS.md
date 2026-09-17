# Semblon agent rules

Working name SEMBLON (SEM-blon). FACEKIT is an engineering term only.

Read in order: `docs/PRODUCT.md` → `docs/CONTRACTS.md` → `docs/CURSOR_INSTRUCTION.txt` → current FACE id. Do not invent a parallel plan, OBS/SIM/VISION tickets, or `SEMBLON_IMPLEMENTATION_PLAN.md`.

## Product

Personal local-first Windows CLI. One user. No cloud. No ACC. No GUI required. Files stay put. SQLite + originals are authoritative.

Loop: `cluster → review → person → name`. Never `cluster = person`.

Unknown is valid. False merge > false split. Wrong identity > unknown.

## Now

S1 identity-quality PASS is closed on golden run `20260913T153515Z-1e915abe`. Do not retune clustering. Do not re-ingest that dump.

FACE-002 → FACE-005 recorded (`docs/FACE-GATES.md`). S6 on main. **S8 Interactive Review slice** (`semblon review-ui`) is the current product surface for human decisions.

**Authorized next (parallel):** (1) Phase 1 real-world validation of `review-ui`. (2) **PERF** — P0 frozen (`docs/PERF-P0-BASELINE.md`); P1 native ARM64 **blocked** (`docs/PERF-P1-ARM64.md`) — do not open workers/EP/batch until P1 unblocks. Do **not** implement S7 engine, full shell, identify/inbox UI, search, or cancellation as a substitute. Do **not** retune eps from the P0 dump.

ARM64 OpenCV **binary** is proven (`cv2.cp314-win_arm64.pyd`, PE `0xaa64`) but **not loadable** in the P1 venv today (`opencv_geometry500.dll` hang). Semblon S1 still uses x64 `cv2` (`0x8664`). Never silent S1 swap. ARM64 ORT `1.30.0` works in `.venv-arm64-perf`. x64 native FACE-000 unverified. Emulation “3–8×” remains hypothesis.

Deferred (catalog): cooperative cancel; structured process.completed; per-file UI outcomes; cluster elapsed (not fake %); workers/EP/GPU/batch/duplicate-imread/SQLite-commit after P1; 10k scale; S7 video; identify/inbox UI; full S8 search. Progress `on_event` spine is **retained**.

## Forbidden unless the current FACE id explicitly requires it

MediaPipe, CLIP, hands, pose, objects, semantic clustering, video, live, public lookup, ACC, vector DB, CustomTkinter, FastAPI, watchdog, parked §20 libraries, new schema columns, cross-pack compare.

FaceKit / InsightFace is the identity engine. `pack_id` includes weight hashes. `buffalo_l` is a family name, not the compare key. Geometry / appearance / objects / semantics must not silently influence identity.

`report` must not write to the store.

## Machine

Windows ARM64 native and Windows x64 native are first-class. x64-on-ARM64 is `emulated` only. Never call that native. Quote Windows paths. Space after `--out`.

## How to work

One ticket, one path, branch `grok/<ticket>`. Cite file:line or a command you ran. Stop before push. Do not start a Cursor Cloud Agent.
