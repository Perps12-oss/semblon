# Semblon completion matrix (authoritative current state)

**Date:** 2026-09-22  
**Authority:** `docs/SEM-ARCH-V1.4.md` · this matrix reconciles docs vs `main` implementation.  
**Do not** treat older freeze audits as current blockers without checking this file + SEM-ARCH §I.5.

| ITEM | CURRENT STATE | EVIDENCE | REMAINING ACTION | FINAL STATUS |
|---|---|---|---|---|
| Identity FACE-001→005 | Closed | `docs/FACE-GATES.md`, S1 golden | None (do not retune) | **COMPLETE** |
| APP-1 JobEngine door | Merged | `semblon/jobs.py`, Home/IPC clients | None | **COMPLETE** |
| APP-1 C.2 pause/unpause | Implemented + unit-tested | `JobEngine.pause/unpause/_gate`; `Application.pause_job/unpause_job`; Home controls; tests | None | **COMPLETE** |
| APP-1 C.3 Windows live | Live evidence 2026-09-22 + prior §I.5 | Owner Windows pytest 20 passed; `semblon home` live ingest | None | **VERIFIED ON WINDOWS** · APP-1 **CLOSED** |
| Application API façade | Named commands on `Application` | `semblon/application.py`; Activity via `application.activity` (**#65**) | None | **COMPLETE** |
| **Production GUI shell** | **One shipping GUI: tk Home + review-ui** | **#54** one-GUI; **#63** Inspector verbs; **#64** state-triple cards; **#65** Rule out WIRED + Activity façade; **#66** Canvas init race | None — not “native shell still open” | **COMPLETE** |
| R2 IPC probe | Loopback probe on main | `semblon/ipc_probe.py` | Not product IPC | **COMPLETE** (probe) |
| R3 Artifacts 1–4 / bake-off / §8.7 / Ruled-out | CLOSED / DONE | SEM-ARCH §I.5; #65 ship claim WIRED | Do not reopen | **OWNER-AUTHORIZED / CLOSED** |
| Optional Qt `semblon shell` | Optional `[gui]` client of Application API | `semblon/native_shell/` (#67) | KEEP optional; **not** a second product Home; **not** a mapped blocker | **KEEP (optional)** |
| `review.html` as UX | Engineering export only | export path | Must not become default workflow | **SUPERSEDED as UX** |
<<<<<<< HEAD
| PERF ARM64 OpenCV | Load hang (historical) | `docs/PERF-P1-ARM64.md` | Agent track: unblock / probe / owner Windows measure | **IN FLIGHT** |
| Multi-worker / scale | Hash workers experimental; default 1 | harness + ingest `--workers` | Agent track: harden + measure honesty; default stays 1 until evidence | **IN FLIGHT** |
| MSI (code, no weights) | Install scripts exist; MSI engineering incomplete | `docs/PACKAGING.md` | Agent track: WiX/MSI without buffalo_l | **IN FLIGHT** |
| buffalo_l redistribution | Legal | `docs/licenses.md` | Pack licence — not an engineering fake | **UNAVAILABLE** |
=======
| PERF ARM64 OpenCV | Load hang | `docs/PERF-P1-ARM64.md` | Owner/machine native load when unblocked | **BLOCKED** (perf track; not APP-1) |
<<<<<<< HEAD
| Multi-worker default | Experimental | workers default 1 | Measure before product default | **EXPERIMENTAL** |
| MSI code (no weights) | WiX project + stage/build/bootstrap + docs/tests | `packaging/msi/`, `tools/msi/`, `docs/PACKAGING.md` | Owner: `wix` + `tools\msi\build-msi.ps1` on Windows; smoke `packaging/msi/smoke-checklist.md` | **PARTIAL** — engineering complete; Windows `wix build`/sign not run in this agent |
| buffalo_l in MSI / redistribution | Legal block | `docs/licenses.md` | Pack licence — do not fake | **UNAVAILABLE** |
>>>>>>> ba19528 (feat(packaging): WiX code MSI without buffalo_l weights)
=======
| Multi-worker / scale | Hash workers hardened; default **1**; harness `default_gate` | `docs/PERF-WORKERS-HARNESS.md`; `tests/test_ingest_workers.py`; cancel/pause + integrity tests | Raise product default only after owner Windows `default_gate.verdict=PASS` + separate PR | **COMPLETE** (default=1) |
| MSI + weights | Unavailable | licenses | Legal + packaging | **UNAVAILABLE** |
>>>>>>> cf6ba88 (feat(ingest): complete hash workers path with default_gate honesty)
>>>>>>> 9413d34 (feat(ingest): complete hash workers path with default_gate honesty)

## Production shell — corrected (PR #54 + #65)

Earlier matrix text claimed “native production shell IN PROGRESS / Tk Home is only compatibility.” That was **wrong** against shipped decisions:

1. **#54** — one shipping GUI: **tk Home + `review-ui`**; PySide product shell deleted.  
2. **#63–#66** — Inspector verbs, state-triple cards, Canvas Home integration, init-race fix.  
3. **#65** — closed leftover **UNWIRED** claim drift; Rule out **WIRED**; Activity via `application.activity`.

Mapped production shell = **Tk Home**. Optional Qt `semblon shell` (#67) is not a second product Home and is not an open stop-work item.

## Status vocabulary

- **COMPLETE** / **VERIFIED ON WINDOWS** / **OWNER-AUTHORIZED / CLOSED** / **KEEP** / **IN FLIGHT** / **UNAVAILABLE** / **SUPERSEDED**

## APP-1 C.3 evidence (retained)

Owner Windows 2026-09-22: pytest jobs/application/ipc **20 passed**; live `semblon home` ingest with Pause/Resume control states + Canvas. APP-1 **CLOSED**.
