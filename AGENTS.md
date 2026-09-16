# Semblon agent rules

Working name SEMBLON (SEM-blon). FACEKIT is an engineering term only.

Read in order: `docs/PRODUCT.md` → `docs/CONTRACTS.md` → `docs/CURSOR_INSTRUCTION.txt` → current FACE id. Do not invent a parallel plan, OBS/SIM/VISION tickets, or `SEMBLON_IMPLEMENTATION_PLAN.md`.

## Product

Personal local-first Windows CLI. One user. No cloud. No ACC. No GUI required. Files stay put. SQLite + originals are authoritative.

Loop: `cluster → review → person → name`. Never `cluster = person`.

Unknown is valid. False merge > false split. Wrong identity > unknown.

## Now

S1 identity-quality PASS is closed on golden run `20260913T153515Z-1e915abe`. Do not retune clustering. Do not re-ingest that dump. Do not start architecture expansion.

Authorized queue: FACE-005 regression/scale (`docs/FACE-005-REGRESSION.md`). Frozen params: eps=0.40. Do not retune. Do not start workers/EP/GPU. 10k scale is not evidenced.

ARM64 OpenCV **binary** is proven (`cv2.cp314-win_arm64.pyd`, PE `0xaa64`). Semblon still runs the existing x64 `cv2` (`0x8664`) under pythoncore-3.14-64. Do not swap OpenCV into the S1 environment unless explicitly decided. x64 native FACE-000 is unverified (no x64 PC). Do not use emulation/VM as native x64 evidence.

Deferred after S1/FACE gates: bounded concurrent ingest workers, provider-aware CPU/GPU EP selection, recording actual provider/device/worker in run evidence.

## Forbidden unless the current FACE id explicitly requires it

MediaPipe, CLIP, hands, pose, objects, semantic clustering, video, live, public lookup, ACC, vector DB, CustomTkinter, FastAPI, watchdog, parked §20 libraries, new schema columns, cross-pack compare.

FaceKit / InsightFace is the identity engine. `pack_id` includes weight hashes. `buffalo_l` is a family name, not the compare key. Geometry / appearance / objects / semantics must not silently influence identity.

`report` must not write to the store.

## Machine

Windows ARM64 native and Windows x64 native are first-class. x64-on-ARM64 is `emulated` only. Never call that native. Quote Windows paths. Space after `--out`.

## How to work

One ticket, one path, branch `grok/<ticket>`. Cite file:line or a command you ran. Stop before push. Do not start a Cursor Cloud Agent.
