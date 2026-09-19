# Semblon production status

**Date:** 2026-09-19  
**Version:** 1.3.0  
**Branch intent:** strongest honest production engineering for the defined release boundary.

Authority: `docs/PRODUCT.md` (v1 + 2026-09-19 production amendment), `docs/CONTRACTS.md`, `docs/SEM-ARCH.md`.  
Freeze audit: `docs/PRODUCTION-AUDIT.md`.

## Declaration

FACE-002 → FACE-005 are a **closed** validation index (`docs/FACE-GATES.md`).  
The KEEP identity loop (`cluster → review → person → name`) is **closed**.  
Architecture continues at **ARCH-004** when earned (`docs/SEM-ARCH.md`). ARCH-003 envelope is recorded as docs (`pack_id` remains the identity key).  
Remaining production-readiness observations are **tracked technical debt**, not phase gates.

## Hierarchy

1. **Identity contract** — immutable. Unknown valid; cluster ≠ person; no silent auto-ID; native/emulated honesty.
2. **Production capabilities (shipping):** `process` / `home` / `review-ui`; incremental ingest; backup/restore; integrity report; cooperative cancel (GUI + SIGINT at file boundaries); named-person `search` (RO lookup) / identify; S7a sampled video + S7b derived tracks; S6 memory; portable CI without weight download. FaceKit CPU is **recorded** in `runtime_json` (ingest still calls `load_app()`).
3. **Experimental / unavailable** — workers>1, GPU, MSI+weights, Canvas, objects, 10k run.

## COMPLETE (verified in portable pytest)

- Identity loop, FACE-002→005 evidence, S1 golden frozen
- Incremental ingest, inbox (RO), identify vs persons
- Home + review-ui; empty states; file missing
- Cancel (GUI + SIGINT at file boundaries); cancelled ≠ completed; partial then cancelled
- Backup/restore; unfinished runs stamped interrupted (not completed)
- Integrity report: orphans, unfinished, `PRAGMA integrity_check`; missing originals are counted and do not fail `ok`
- Single-decode stills path; CPU/`provider` fields in `runtime_json`
- `search --person/--people` read-only lookup; `--face` is identify (writes decisions)
- ARCH-003 embedding envelope as docs; `compare()` refuses incompatible pack/dim
- S7a/S7b; S6 memory
- Portable CI workflow (no weight download); Windows-path tests do not assume POSIX `Path` identity
- GitHub Actions on this honesty slice: **ubuntu-latest + windows-latest pytest SUCCESS** (`35455505696`, 2026-09-19)

## PARTIAL (not in-product complete)

- `FaceKitProvider`: class exists; ingest still calls `load_app()`
- Stall watchdog: unit-tested; **not wired** into Home/`process` (does not kill even if used)
- Home People/Unknown/Activity/Settings are dialogs, not full pages
- Progress kind `queued`: defined, never emitted

## COMPLETE — ENVIRONMENT-LIMITED

- ARM64 native OpenCV ingest (binary exists; load hang)
- x64 native FACE-000 (no x64 PC here)
- Video tracking quality on real camera motion (synthetic tests only)

## EXPERIMENTAL

- `ingest --workers` (default 1; P1 still blocks product default)

## DEFERRED (architecture / later product)

ARCH-003…010 code, Canvas, objects/OCR/CLIP, folder watcher, webcam/RTSP, identify/inbox full UI, default GPU/workers, vector DB.

## UNAVAILABLE

- buffalo_l redistribution / frozen installer with weights
- Legal licence sign-off
- Clean-machine MSI

## Non-gating technical debt

Tracked. **Not** FACE gates. **Not** KEEP identity-loop gates. **Not** a reason to reopen clustering.

| Item | Why it is not a gate |
|---|---|
| Wire `Watchdog` into Home, or drop any in-product COMPLETE sentence | Cancel already honest; stall UI is polish |
| `FaceKitProvider.load()` in ingest | Identity engine is still FaceKit via `load_app()`; CPU is recorded |
| Dead `unassigned_media` handlers in `review_ui.py` | Board emits `track` / `unassigned`, not that kind |
| Schema migrate / uninstall installer | `SCHEMA_VERSION` is `"1"`; no upgrade path required for this freeze |
| Live P0 re-time after single `imread` | Code path is single-decode; 221-still P0 remains historical |
| GitHub Actions on `main` after merge | Slice Actions already green on PR #37 (`35455505696`); merge confirmation is process |
| GUI widget tests / visual Home | Board/API tests cover decisions; pixels are HUMAN |
| 10k / owner-dump / real video / native ARM64 OpenCV / x64 FACE-000 | Environment / dataset; do not retune eps to compensate |
| MSI + bundled `buffalo_l` | Licence, not engineering |
| `KIND_QUEUED` unused; `source_type=live` unused; `cluster --eps` power-user flag | Footguns/reserved, not identity defects |

## Evidence

Portable: `python -m pytest -q` (no InsightFace download).  
GitHub Actions (PR #37): windows-latest 3.12 and ubuntu-latest 3.12 **SUCCESS** — https://github.com/Perps12-oss/semblon/actions/runs/35455505696  
Live dump / 10k / GPU: not executed this run — human verification required, not a phase gate.
