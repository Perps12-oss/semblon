# Semblon completion matrix (authoritative current state)

**Date:** 2026-09-22  
**Authority:** `docs/SEM-ARCH-V1.4.md` · this matrix reconciles docs vs `main` implementation.  
**Do not** treat older freeze audits as current blockers without checking this file + SEM-ARCH §I.5.

| ITEM | CURRENT STATE | EVIDENCE | REMAINING ACTION | FINAL STATUS |
|---|---|---|---|---|
| Identity FACE-001→005 | Closed | `docs/FACE-GATES.md`, S1 golden | None (do not retune) | **COMPLETE** |
| APP-1 JobEngine door | Merged | `semblon/jobs.py`, Home/IPC clients | None | **COMPLETE** |
| APP-1 C.2 pause/unpause | Implemented + unit-tested | `JobEngine.pause/unpause/_gate`; `Application.pause_job/unpause_job`; Home + shell controls; `tests/test_jobs.py`, `tests/test_application.py`, `tests/test_ipc_probe.py` | None | **COMPLETE** |
| APP-1 C.3 Windows live | Live evidence 2026-09-22 + prior §I.5 | Owner Windows: `20 passed` jobs/application/ipc; `semblon home` live ingest (Pause on / Resume off while running; progress 11/32193; Canvas usable during ingest) | None — gate closed | **VERIFIED ON WINDOWS** · APP-1 **CLOSED** |
| Application API façade | Named commands on `Application` | `semblon/application.py`, `docs/APPLICATION_API.md` | Grow clients as shell deepens | **COMPLETE** (boundary) |
| R2 IPC probe | Loopback probe on main | `semblon/ipc_probe.py`, `semblon lab ipc-probe`, `tests/test_ipc_probe.py` | Not product IPC (named pipes / WinUI host later if needed) | **COMPLETE** (probe) |
| R3 Artifacts 1–4 | Canonical | `docs/r3-artifacts/` | Use as acceptance while implementing shell | **COMPLETE** (spec) |
| Bake-off / §8.7 / Ruled-out ship | CLOSED / DONE | SEM-ARCH §I.5 | Do not reopen | **OWNER-AUTHORIZED / CLOSED** |
| Native production shell | Slice 1 + Inspector + Canvas RO list | `semblon/native_shell/`; Application.canvas + overlay_boxes + state-triple labels | Pixel compositor / default entry swap | **IN PROGRESS** |
| Tk Home | Compatibility frontend | `semblon home` | Keep until native shell replaces default entry | **KEEP** |
| `review.html` as UX | Engineering export only | export path | Must not become default workflow | **SUPERSEDED as UX** |
| PERF ARM64 OpenCV | Load hang | `docs/PERF-P1-ARM64.md` | Owner/machine native load when unblocked | **BLOCKED** (perf track; not APP-1) |
| Multi-worker default | Experimental | workers default 1 | Measure before product default | **EXPERIMENTAL** |
| MSI + weights | Unavailable | licenses | Legal + packaging | **UNAVAILABLE** |

## Status vocabulary (this completion drive)

- **COMPLETE** — implemented and auto-verified where claimed.
- **OWNER-AUTHORIZED / CLOSED** — owner closed the gate; do not reopen as stop-work.
- **VERIFIED AUTOMATICALLY** — portable pytest / source contracts.
- **VERIFIED ON WINDOWS** — owner machine evidence recorded.
- **IN PROGRESS** — planned item partially shipped.
- **SUPERSEDED / HISTORICAL** — keep evidence; not current queue.
- **BLOCKED** — real technical blocker (cite path).

## APP-1 C.3 Windows live evidence (2026-09-22)

**Machine:** owner Windows (`C:\Users\S8633\Documents\GITHUB\SEMBRON`, store `%LOCALAPPDATA%\Semblon\store.sqlite`).  
**Owner directive:** mark C.3 **VERIFIED ON WINDOWS** (this packet). Prior §I.5 CLOSED / DONE (2026-09-21) retained.

| Check | Result |
|---|---|
| `pytest -q tests/test_jobs.py tests/test_application.py tests/test_ipc_probe.py` | **20 passed** in 3.15s |
| `semblon home` live ingest | **PASS** — Reading photos 11/32193; elapsed/eta updating; Pause **enabled**, Resume **disabled** while running |
| UI responsive during ingest | **PASS** — Canvas selected; face + object overlays; Library/Inspector usable |
| Job door controls correct while running | **PASS** — Pause on, Resume off (unpause only when paused) |
| Prior owner §I.5 ship closure | **CLOSED / DONE** 2026-09-21 |

Screenshot artifact (this agent run): `/opt/cursor/artifacts/screenshots/app1-c3-windows-live-home.png`.

**APP-1 status:** **CLOSED** (C.2 COMPLETE + C.3 VERIFIED ON WINDOWS + prior owner authorization). Next planned work is deepen native shell — not reopen APP-1.
