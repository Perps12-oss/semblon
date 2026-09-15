# Semblon agent rules

Working name SEMBLON (SEM-blon). FACEKIT is an engineering term only.

Read in order: `docs/PRODUCT.md` → `docs/CONTRACTS.md` → `docs/CURSOR_INSTRUCTION.txt` → current FACE id. Do not invent a parallel plan, OBS/SIM/VISION tickets, or `SEMBLON_IMPLEMENTATION_PLAN.md`.

## Product

Personal local-first Windows CLI. One user. No cloud. No ACC. No GUI required. Files stay put. SQLite + originals are authoritative.

Loop: `cluster → review → person → name`. Never `cluster = person`.

Unknown is valid. False merge > false split. Wrong identity > unknown.

## Now

S1 identity-quality PASS is closed on golden run `20260913T153515Z-1e915abe`. Do not retune clustering. Do not re-ingest that dump. Do not start architecture expansion.

Authorized queue: dump-gate → FACE-002 → FACE-003 ↔ FACE-004 → FACE-005.
FACE-002 eval harness exists; stage is open until a labeled confirmatory set exists. Do not print precision without `--eval-set confirmatory`.

## Forbidden unless the current FACE id explicitly requires it

MediaPipe, CLIP, hands, pose, objects, semantic clustering, video, live, public lookup, ACC, vector DB, CustomTkinter, FastAPI, watchdog, parked §20 libraries, new schema columns, cross-pack compare.

FaceKit / InsightFace is the identity engine. `pack_id` includes weight hashes. `buffalo_l` is a family name, not the compare key. Geometry / appearance / objects / semantics must not silently influence identity.

`report` must not write to the store.

## Machine

Windows ARM64 native and Windows x64 native are first-class. x64-on-ARM64 is `emulated` only. Never call that native. Quote Windows paths. Space after `--out`.

## How to work

One ticket, one path, branch `grok/<ticket>`. Cite file:line or a command you ran. Stop before push. Do not start a Cursor Cloud Agent.
