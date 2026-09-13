# Semblon — Product brief (frozen 2026-09-12)

Semblon v1 is a **personal, local-first** Windows CLI. One user. No cloud. No ACC. No GUI required.

**Successful day:** drop a folder of stills → conservative face groups → review and name people you care about → those people become a gallery for later identification.

The architectural North Star in `docs/ARCHITECTURE.md` does **not** redefine this v1. Folder-first, face-first, local-first remains the current product. Future observers, spaces, sources, and integrations stay out until PRODUCT is explicitly amended.

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

Public lookup · live CCTV · USB webcam · video files · ACC · mobile · multi-user · sharing · CustomTkinter · FastAPI · watchdog · automatic identity

## v1 ship test

A folder of stills can be ingested reproducibly; faces detected/embedded/grouped conservatively; groups reviewed and corrected; people named; reviewed gallery persisted locally for later identification.

## Later (not v1)

| Version | What |
|---|---|
| v2 | USB webcam: detect → track → selective embed → identify vs persons → known/unknown (log; optional prompt to name; never force ID) |
| later | RTSP, video files, explicit click-to-lookup, ACC as **client** of standalone Semblon, licensed pack if anyone else gets a copy |

## Loop (do not invert)

`cluster → review → person → name`  
Never `cluster = person`.
