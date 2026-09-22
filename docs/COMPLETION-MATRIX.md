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
| Native production shell | Slice 1 + Inspector verbs | `semblon/native_shell/`; Application API; inspector_verbs → apply_* | Canvas compositor / state-triple cards / default entry swap | **IN PROGRESS** |
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

C.3 remains **OWNER-AUTHORIZED / CLOSED** (2026-09-21). Do not treat it as a merge blocker.  
For today's production-readiness evidence pack, on the owner Windows machine:

```text
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
pip install -e ".[gui]"
pytest -q tests/test_jobs.py tests/test_application.py tests/test_ipc_probe.py
semblon home --store "%LOCALAPPDATA%\Semblon\store.sqlite"
```

Then with a small real photo folder (≥3 stills):

1. Choose folder → confirm UI stays responsive and progress/status updates.
2. Pause mid-ingest → status shows paused; CPU/work stops between files (honest granularity).
3. Resume (unpause) → **same job** continues (do not Choose folder again).
4. Pause again → Cancel while paused → cancelled (not completed); Resume after cancel starts a **new** submit with resume.
5. Open Review during ingest → board readable; Name one cluster after cancel/complete.
6. Confirm no second ingest door (second Choose folder refused / Job busy).

Also optional native shell smoke:

```text
semblon shell --store "%LOCALAPPDATA%\Semblon\store.sqlite"
```

**Evidence to return:** short notes for steps 1–6 (pass/fail), `pytest` exit line, store path, and whether `semblon shell` opened. Screenshots optional.

After evidence is returned, update this matrix C.3 row to **VERIFIED ON WINDOWS** and the PRODUCTION-STATUS evidence section — without inventing results from Cloud/Linux.
