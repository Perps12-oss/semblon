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

**Authorized next:** Phase 1 real-world validation of review-ui (process → name/merge/split → reopen → identify). See `docs/ROADMAP-RECONCILE.md`. Do **not** open S7, identify/inbox UI, search dashboard, cancellation, or workers/EP until that reconcile doc says so.

ARM64 OpenCV **binary** is proven (`cv2.cp314-win_arm64.pyd`, PE `0xaa64`). Semblon still runs the existing x64 `cv2` (`0x8664`) under pythoncore-3.14-64. Do not swap OpenCV into the S1 environment unless explicitly decided. x64 native FACE-000 is unverified (no x64 PC). Do not use emulation/VM as native x64 evidence.

Deferred (catalog): cooperative cancel; structured process.completed; per-file UI outcomes; cluster elapsed (not fake %); workers/EP/GPU evidence; 10k scale; S7 video; identify/inbox UI; full S8 search. Progress `on_event` spine is **retained**.

## Forbidden unless the current FACE id explicitly requires it

MediaPipe, CLIP, hands, pose, objects, semantic clustering, video, live, public lookup, ACC, vector DB, CustomTkinter, FastAPI, watchdog, parked §20 libraries, new schema columns, cross-pack compare.

FaceKit / InsightFace is the identity engine. `pack_id` includes weight hashes. `buffalo_l` is a family name, not the compare key. Geometry / appearance / objects / semantics must not silently influence identity.

`report` must not write to the store.

## Machine

Windows ARM64 native and Windows x64 native are first-class. x64-on-ARM64 is `emulated` only. Never call that native. Quote Windows paths. Space after `--out`.

## How to work

One ticket, one path, branch `grok/<ticket>`. Cite file:line or a command you ran. Stop before push. Do not start a Cursor Cloud Agent.
