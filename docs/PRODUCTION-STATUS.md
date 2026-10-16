# Semblon production status

**Historical capability list.** As of 2026-10-16 the product contract is `docs/PRODUCT.md` and the evidence-backed capability status is `docs/BUILD-STATUS.md`. Keep this file as the 2026-09-22 record plus the 2026-10-05 shell correction. Do not treat its COMPLETE bullets as the current product matrix.

**Production architecture:** COMPLETE — 2026-10-05. See `docs/ARCHITECTURE.md` and the CLOSED / OPEN split in `docs/COMPLETION-MATRIX.md`.

**Date of the capability lists below:** 2026-09-22, plus the shell correction on 2026-10-05.  
**Version:** 1.4.0  
**Branch intent:** full-stack architecture on the frozen identity contract. The shell migration is closed. Further work is product construction, not a new architecture.

Authority: `docs/PRODUCT.md` (v1 + amendments), `docs/CONTRACTS.md`, `docs/ARCHITECTURE.md`, `docs/SEM-ARCH-V1.4.md`.

Where a bullet below says “Home”, it means the legacy Tk client or a capability that client still calls. It is not a second production architecture.

## Hierarchy

1. **Identity contract** — immutable. Unknown valid; cluster ≠ person; no silent auto-ID; native/emulated honesty. FaceKit is the only identity engine.
2. **Production capabilities** — PySide6 archive (`semblon shell`) → `Application`; incremental ingest; backup/restore; integrity; person search; observation-table write-through (“schema v2” / `SCHEMA_VERSION=4`); FaceKitProvider on ingest; sampled video tracks. Tk Home and Tk review-ui are legacy clients of the same façade.
3. **Experimental / unavailable** — product-default `workers>1` (opt-in CLI exists; raise default only on owner measure PASS), GPU when no EP, MSI+weights, 10k run. OCR/CLIP/pose are **PRODUCTIZED (optional)** when honesty probes pass (`docs/OPTIONAL-MODALITY-STATUS.md`); still non-identity.

## COMPLETE (verified in portable pytest)

- Identity loop, FACE-002→005 evidence, S1 golden frozen
- Incremental ingest, inbox (RO), identify vs persons
- Home + review-ui; empty states; file missing; Home shell (historical R3 sidebar chrome still in code; **product IA LOCKED Model D** — Memory-first Stage dissolve — see `docs/SHELL-IA.md`; no MAIN sidebar scaffold); person search field
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

## COMPLETE — production GUI shell (2026-10-05)

- **Production shell:** PySide6 archive (`semblon shell`) → `Application`. Installer installs `.[gui]`. Double-click `semblon.cmd` opens that shell.
- **Application** owns `JobEngine` and the archive session. It does not import a UI toolkit.
- Tk Home (`semblon home`) and Tk review-ui are **legacy clients only**. Do not start new product work there.
- `review.html` / `review_chrome` are **retired**. There is no production Review page.
- `tools/s8_toolkit_spike` and the Live overlay are outside the production shell.
- Inspector verbs, state-triple cards, Rule out, and Activity (`application.activity`) remain domain/client capabilities (**#63–#66**). They do not make Tk the product door.

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

- `ingest --workers` / `process --workers` — **engineering COMPLETE**: bounded hash-phase ThreadPool (cap 32); single FaceAnalysis; single SQLite writer; cooperative cancel/pause; portable regression tests; harness emits machine-readable `default_gate` (`docs/PERF-WORKERS-HARNESS.md`). **Product default remains `workers=1`.** Raising the default requires owner Windows harness `default_gate.verdict=PASS` and a separate explicit PR — not authorized from Linux CI or superseded multi-session evidence.

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
