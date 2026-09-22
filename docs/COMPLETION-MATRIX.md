# Semblon completion matrix (authoritative current state)

**Date:** 2026-09-22  
**Authority:** `docs/SEM-ARCH-V1.4.md` · this matrix reconciles docs vs `main` implementation.  
**Do not** treat older freeze audits as current blockers without checking this file + SEM-ARCH §I.5.

| ITEM | CURRENT STATE | EVIDENCE | REMAINING ACTION | FINAL STATUS |
|---|---|---|---|---|
| Identity FACE-001→005 | Closed | `docs/FACE-GATES.md`, S1 golden | None (do not retune) | **COMPLETE** |
| APP-1 JobEngine door | Merged | `semblon/jobs.py`, Home/IPC clients | None | **COMPLETE** |
| APP-1 C.2 pause/unpause | Implemented + unit-tested | `JobEngine.pause/unpause/_gate`; `Application.pause_job/unpause_job`; Home + shell controls; `tests/test_jobs.py`, `tests/test_application.py`, `tests/test_ipc_probe.py` | Optional owner Windows live re-proof (procedure below) | **COMPLETE (auto)** |
| APP-1 C.3 Windows live | Owner CLOSED 2026-09-21 (§I.5) | Prior owner declaration in SEM-ARCH §I.5 / HUMAN-VERIFY | Owner may return today's live evidence packet for production-readiness report | **OWNER-AUTHORIZED / CLOSED** — live re-verify optional for evidence pack |
| Application API façade | Named commands on `Application` | `semblon/application.py`, `docs/APPLICATION_API.md` | Grow clients as shell deepens | **COMPLETE** (boundary) |
| R2 IPC probe | Loopback probe on main | `semblon/ipc_probe.py`, `semblon lab ipc-probe`, `tests/test_ipc_probe.py` | Not product IPC (named pipes / WinUI host later if needed) | **COMPLETE** (probe) |
| R3 Artifacts 1–4 | Canonical | `docs/r3-artifacts/` | Use as acceptance while implementing shell | **COMPLETE** (spec) |
| Bake-off / §8.7 / Ruled-out ship | CLOSED / DONE | SEM-ARCH §I.5 | Do not reopen | **OWNER-AUTHORIZED / CLOSED** |
| Native production shell | First slice shipped | `semblon/native_shell/`, `semblon shell`, Application API only | Deepen Canvas/Inspector verbs; Windows visual proof; do not expand Tk into AppShell | **IN PROGRESS** (slice 1) |
| Tk Home | Compatibility frontend | `semblon home` | Keep until native shell replaces default entry | **KEEP** |
| `review.html` as UX | Engineering export only | export path | Must not become default workflow | **SUPERSEDED as UX** |
| PERF ARM64 OpenCV | Load hang | `docs/PERF-P1-ARM64.md` | Owner/machine native load when unblocked | **BLOCKED** (perf track; not APP-1) |
| Multi-worker default | Experimental | workers default 1 | Measure before product default | **EXPERIMENTAL** |
| MSI + weights | Unavailable | licenses | Legal + packaging | **UNAVAILABLE** |

## Status vocabulary (this completion drive)

- **COMPLETE** — implemented and auto-verified where claimed.
- **OWNER-AUTHORIZED / CLOSED** — owner closed the gate; do not reopen as stop-work.
- **VERIFIED AUTOMATICALLY** — portable pytest / source contracts.
- **VERIFIED ON WINDOWS** — requires owner machine evidence (not claimed from Linux Cloud).
- **IN PROGRESS** — planned item partially shipped.
- **SUPERSEDED / HISTORICAL** — keep evidence; not current queue.
- **BLOCKED** — real technical blocker (cite path).

## Windows live procedure (APP-1 C.3 evidence pack)

See the procedure in the agent summary / `docs/HUMAN-VERIFY-THEN-WIRE.md` §5 (historical steps). Minimal packet for today's production report is listed in the PR / agent message. After owner returns evidence, update this matrix row C.3 **VERIFIED ON WINDOWS** and SEM-ARCH if needed — without inventing results.
