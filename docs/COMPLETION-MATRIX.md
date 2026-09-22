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
| PERF ARM64 OpenCV | Load hang; PE/timed probes shipped | `docs/PERF-P1-ARM64.md`; `semblon/opencv_probe.py`; `tools/_perf_p1_load_cv2.py` | Owner Windows ARM64: `tools\perf_p1_arm64_repro.ps1`; fix/replace `opencv_geometry500.dll`; then P0 timing | **BLOCKED** (native load) · probe **COMPLETE** |
| Multi-worker / scale | Hash workers hardened; default **1**; harness `default_gate` | `docs/PERF-WORKERS-HARNESS.md`; ingest worker tests | Raise default only after owner Windows `default_gate.verdict=PASS` + separate PR | **COMPLETE** (default=1) |
| MSI code (no weights) | WiX project + stage/build/bootstrap + docs/tests | `packaging/msi/`, `tools/msi/`, `docs/PACKAGING.md` | Owner: `wix` + `tools\msi\build-msi.ps1`; smoke checklist | **PARTIAL** — engineering complete; Windows `wix build`/sign not run here |
| buffalo_l redistribution | Legal | `docs/licenses.md` | Pack licence — do not fake | **UNAVAILABLE** |

## Production shell — corrected (PR #54 + #65)

Earlier matrix text claimed “native production shell IN PROGRESS / Tk Home is only compatibility.” That was **wrong** against shipped decisions:

1. **#54** — one shipping GUI: **tk Home + `review-ui`**; PySide product shell deleted.  
2. **#63–#66** — Inspector verbs, state-triple cards, Canvas Home integration, init-race fix.  
3. **#65** — closed leftover **UNWIRED** claim drift; Rule out **WIRED**; Activity via `application.activity`.

Mapped production shell = **Tk Home**. Optional Qt `semblon shell` (#67) is not a second product Home and is not an open stop-work item.

## Status vocabulary

- **COMPLETE** / **VERIFIED ON WINDOWS** / **OWNER-AUTHORIZED / CLOSED** / **KEEP** / **PARTIAL** / **BLOCKED** / **UNAVAILABLE** / **SUPERSEDED**

## APP-1 C.3 evidence (retained)

Owner Windows 2026-09-22: pytest jobs/application/ipc **20 passed**; live `semblon home` ingest with Pause/Resume control states + Canvas. APP-1 **CLOSED**.
