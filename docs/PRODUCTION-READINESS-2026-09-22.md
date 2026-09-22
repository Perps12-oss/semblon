# Production readiness report (2026-09-22)

**Branch:** `cursor/app1-c2-pause-unpause-dc8c`  
**Authority:** `docs/SEM-ARCH-V1.4.md` · `docs/COMPLETION-MATRIX.md` · `docs/PRODUCTION-STATUS.md`  
**Portable tests this run:** `462 passed, 5 skipped` (`python3 -m pytest -q`)

## IMPLEMENTED

- APP-1 JobEngine boundary (prior main) + C.2 pause/unpause
- `Application` named commands: `pause_job` / `unpause_job` / `cancel_job` / `submit_ingest` / `job_current`
- Home Pause/Resume (unpause vs resume-after-cancel)
- R2 IPC probe pause/unpause ops
- Native production shell slice 1: `semblon shell` (IA + job bar + Inspector verbs via `inspector_verbs`)
- Docs reconciled (SEM-ARCH V1.4.9, APPLICATION_API, CONTRACTS, PRODUCTION-STATUS, COMPLETION-MATRIX)

## VERIFIED AUTOMATICALLY

- `tests/test_jobs.py` — pause blocks until unpause; cancel while paused; JobBusy; Home control states
- `tests/test_application.py` — Application façade same-job unpause; cancel while paused; cancelling state
- `tests/test_ipc_probe.py` — pause/unpause over loopback probe
- `tests/test_native_shell.py` — no process_folder/FaceKit imports; CLI `shell`; verb wiring (PySide optional)
- Full portable suite: **462 passed, 5 skipped**
- Owner Windows: `pytest -q tests/test_jobs.py tests/test_application.py tests/test_ipc_probe.py` → **20 passed** in 3.15s

## VERIFIED ON WINDOWS

- **APP-1 C.3** — owner 2026-09-22:
  - pytest jobs/application/ipc: **20 passed**
  - `semblon home --store "%LOCALAPPDATA%\Semblon\store.sqlite"` live ingest
  - Screenshot: Pause enabled, Resume disabled while running; progress 11/32193; Canvas overlays during ingest; UI responsive
  - Artifact: `/opt/cursor/artifacts/screenshots/app1-c3-windows-live-home.png`
- **APP-1 CLOSED** (C.2 COMPLETE + C.3 VERIFIED ON WINDOWS + prior §I.5 authorization)

## OWNER-AUTHORIZED

- APP-1 C.3 (also now Windows-verified) · bake-off · §8.7 native shell · Ruled-out product wire (§I.5)

## SUPERSEDED / HISTORICAL

- `docs/PRODUCTION-AUDIT.md` freeze at `8403292` (historical)
- `docs/ROADMAP-RECONCILE.md` retired pointer
- `review.html` as end-user workflow (engineering export only)
- Expanding Tk Home into permanent AppShell (refused)

## Genuinely REMAINING

1. Deepen native shell: Canvas compositor, state-triple media cards, Assign-to-person UX, default entry decision (`shell` vs `home`)
2. PERF ARM64 OpenCV load hang (`docs/PERF-P1-ARM64.md`) — parallel track
3. MSI + buffalo_l redistribution / legal — UNAVAILABLE
4. Scale 1k/5k/10k live measurements — environment-limited

## Identity / correctness checks this slice

- No identity threshold changes
- No schema DDL
- No second JobEngine
- Shell/Home do not call `process_folder`
- FaceKit remains only identity engine
