# Semblon hardening policy (current)

This file records explicit hardening expectations for productization tracks.

## Identity safety

- FaceKit/InsightFace remains the only identity engine.
- Non-face observers must never set `faces.person_id`.
- `embeddings.modality='face'` is forbidden.

## Runtime evidence

Every production/perf run should record:

- workers used
- selected provider
- fallback path
- timings
- execution architecture (`native` vs `emulated`)

## Filesystem policy

- Ingest is local-first and reads user-owned files in place.
- Store writes are restricted to the Semblon SQLite path and explicit export paths.
- Missing originals are reported by integrity checks; they are not silently repaired.

## Resource safety policy

- Benchmarks must report semantic parity, not only throughput.
- Large-scale or hardware-sensitive claims require explicit evidence runs.
- Video/track episodes are hypotheses and must not auto-assign identity.

## Installer lifecycle baseline

- install: `tools/install-windows.ps1`
- uninstall: `tools/uninstall-windows.ps1`
- first-run UI command: `python -m semblon home`

Hardening state snapshot command:

`python -m semblon lab hardening`
