# Semblon production status

**Date:** 2026-09-22  
**Version:** 1.4.0 (`main` + this slice: Application façade, APP-1 C.2 COMPLETE, native shell slice 1)  
**Branch intent:** full-stack architecture on the frozen identity contract.

Authority: `docs/PRODUCT.md` (v1 + 2026-09-19 production amendment), `docs/CONTRACTS.md`, `docs/SEM-ARCH-V1.4.md`.  
**Completion matrix (current):** `docs/COMPLETION-MATRIX.md`.  
Freeze audit: `docs/PRODUCTION-AUDIT.md` (historical freeze at `8403292`). Addendum below that file records later main.

Canonical roadmap sequencing and reconciled status categories live in `docs/SEM-ARCH-V1.4.md`.

## Hierarchy

1. **Identity contract** — immutable. Unknown valid; cluster ≠ person; no silent auto-ID; native/emulated honesty. FaceKit is the only identity engine.
2. **Production capabilities** — Home/review-ui, native shell slice 1, cancel/pause, backup, integrity, person search, Canvas overlay, observation-table write-through (“schema v2” / `SCHEMA_VERSION=4`), stall watchdog on Home, FaceKitProvider on ingest, sampled video tracks.
3. **Experimental / unavailable** — product-default `workers>1` (opt-in CLI exists; raise default only on owner measure PASS), GPU when no EP, MSI+weights, 10k run. OCR/CLIP/pose are **PRODUCTIZED (optional)** when honesty probes pass (`docs/OPTIONAL-MODALITY-STATUS.md`); still non-identity.

## COMPLETE (verified in portable pytest)

- Identity loop, FACE-002→005 evidence, S1 golden frozen
- Incremental ingest, inbox (RO), identify vs persons
- Home + review-ui; empty states; file missing; **Home sidebar shell** (Library | Workspace/Canvas | Inspector per R3 §4 IA); person search field
- ARCH-011 / APP-1: `JobEngine` is the ingest door; second submit is `JobBusy`; Home job-control (folder/Pause/Resume/Cancel) does not lock Review / People / Search; Review is a Toplevel on Home’s root; Review reads use `busy_timeout=5000`
- **APP-1 C.2:** real paused state; `pause`/`unpause`; cancel while paused; unpause continues same job; honest between-files granularity; `Application.pause_job`/`unpause_job`; Home + IPC + native shell controls
- Cancel (GUI + SIGINT at file boundaries); cancelled ≠ completed; partial then cancelled
- Backup/restore; integrity report; unfinished runs stamped interrupted (not completed)
- `FaceKitProvider.load()` is the ingest load path (`ingest.load_app` wraps it)
- Stall watchdog on Home status; stalled ≠ killed
- Schema v2 tables (`observation_items`, `embeddings`, `tracks`, `observation_groups`, `relationships`, `events`) at store `SCHEMA_VERSION=4`
- Face dual-write as `observation_items` kind=`face` without identity vectors in `embeddings`
- DBSCAN clusters snapshot to `observation_groups` (group ≠ person)
- S6 together/events snapshot to `relationships`/`events` with `confirmed=0`
- `search --person/--people/--face/--similar` (similar is same-modality only; face refused)
- `watch`; `live` detect→track→selective embed→identify vs named persons (`--seconds 0` unbounded, `--retain-s` optional); **Canvas** Home-integrated observation overlay (boxes/tracks; never writes `person_id`)
- Color-hist + OpenCV contour observers; OCR/CLIP/pose product path when honesty probes ready (`MODALITY_PRODUCT`)
- GPU product path: `product_prefer_gpu` / Settings status from ORT EP listing (no fake GPU claims)
- S7a/S7b; S6 memory
- Process callback emits `KIND_QUEUED` before `KIND_STARTED`
- R2 IPC probe (`semblon lab ipc-probe`)
- Portable CI workflow (no weight download)

## PARTIAL

- Identify/inbox as dedicated full pages (Inspector lists today)
- Canvas Tk PhotoImage compositor (Home-integrated overlay; pixel compositor may improve)
- OCR/CLIP/pose: product path ON when probes ready; not in `requirements.txt`; CLIP/pose may fail without local weights (recorded as error/unavailable items, not crashes)
- GPU: honest EP detection + product `prefer_gpu` when CUDA/DirectML/TensorRT listed; listed ≠ smoke-tested

## COMPLETE — production GUI shell

- **One shipping GUI:** tk Home + `review-ui` (**#54**)
- Inspector verbs wired (**#63**); state-triple media cards (**#64**); Rule out WIRED + Activity via `application.activity` (**#65**); Canvas init race fixed (**#66**)
- Optional Qt `semblon shell` (#67) is KEEP optional — **not** a second product Home and **not** an open mapped blocker

## IN FLIGHT (delegated engineering tracks)

- PERF ARM64 OpenCV load path
- Multi-worker / scale harden (product default remains 1 until measured)
- MSI code packaging without buffalo_l

## COMPLETE — ENVIRONMENT-LIMITED

- ARM64 native OpenCV ingest (binary exists; load hang) — see IN FLIGHT
- x64 native FACE-000 (no x64 PC here)
- Video tracking quality on real camera motion (synthetic tests only)
- Webcam/RTSP hardware validation on real devices is pending; live engine is seam-tested in portable CI

## COMPLETE — MEASUREMENT-GATED DEFAULT

- `ingest --workers` / `process --workers` — **engineering COMPLETE**: bounded hash-phase ThreadPool (cap 32); single FaceAnalysis; single SQLite writer; cooperative cancel/pause; portable regression tests; harness emits machine-readable `default_gate` (`docs/PERF-WORKERS-HARNESS.md`). **Product default remains `workers=1`.** Raising the default requires owner Windows harness `default_gate.verdict=PASS` and a separate explicit PR — not authorized from Linux CI or historical multi-session evidence (`docs/PERF-WORKERS.md`).

## DEFERRED

Identify/inbox as dedicated full pages; vector DB.

## UNAVAILABLE

- buffalo_l redistribution / frozen installer with weights
- Legal licence sign-off
- Clean-machine MSI (engineering IN FLIGHT; weights still UNAVAILABLE)

## OWNER-AUTHORIZED / VERIFIED ON WINDOWS

- APP-1 C.3 Windows live — **VERIFIED ON WINDOWS** 2026-09-22 (owner: pytest 20 passed; `semblon home` live ingest Pause/Resume states + Canvas during ingest). Prior §I.5 CLOSED retained. **APP-1 CLOSED.**
- Toolkit bake-off · §8.7 shell decision · Ruled-out product wire — **CLOSED / DONE** (`SEM-ARCH-V1.4` §I.5).

Evidence detail: `docs/COMPLETION-MATRIX.md`.

## Evidence

Portable: `python -m pytest -q` (no InsightFace download).  
Windows APP-1 C.3: owner 2026-09-22 packet recorded in COMPLETION-MATRIX.  
Live 10k / GPU smoke / real webcam: environment-limited where not yet run.
