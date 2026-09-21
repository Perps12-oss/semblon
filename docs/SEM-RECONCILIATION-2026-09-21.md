# SEM reconciliation snapshot — 2026-09-21

**Status:** frozen evidence snapshot (do not overwrite mid-execution)  
**Code authority:** always wins over this file  
**Baseline:** `main@2c19d05` lineage (Semblon 1.4.0); later commits may supersede details  
**North star:** `docs/SEM-ARCH-V1.4.md`  
**Execution follow-up:** `docs/SEM-EXECUTION-2026-09-21.md`

This file records the pretence/capability audit that moved Semblon from architecture prose to targeted implementation. It does **not** reopen FACE-002→FACE-005.

## What exists (code)

| Area | Truth |
|---|---|
| Identity / FaceKit | Shipped / gated |
| PySide6 Home | Already default `semblon home` (was documented as deferred) |
| Live engine | Exists (detect→track→selective embed→identify); product overlay was missing |
| Tracker | Greedy bbox IoU association — do not replace without measurement |
| Search CLI | `--person/--people/--face/--similar` only — **no** `--image` / `--text` |
| Workers | Hash-phase parallelism only — **not** inference workers |
| Objects | OpenCV contour regions — **not** a trained detector |
| OCR / CLIP / pose | Optional imports; import ≠ runnable capability |
| Episode type | **Does not exist** — do not invent |
| review.html | QA/evidence — not the user application |

## Immediate workstreams (ordered)

1. Resolve PySide Home / product-shell decision (docs ↔ code)
2. Put live engine on the accepted product surface
3. Multi-person live validation (independent boxes/tracks; UNKNOWN valid)
4. Real-video tracker fragmentation measurement (before rewrite)
5. Observer capability truth cleanup
6. Hash-worker 1/2/4 benchmark on current code

## Forbidden

Reopen FACE gates · retune thresholds · auto Person from Track · Episode abstraction · FAISS/HDBSCAN/Milvus · second GUI framework · claim unsupported MediaPipe/OCR/CLIP/search surfaces.

## Principle

Observation ≠ Track ≠ Person. Person exists only after explicit human naming.
