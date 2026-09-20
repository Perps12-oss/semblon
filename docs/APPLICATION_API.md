# Application API (R1)

**Status:** extracted from existing code. Not a framework. Not WinUI.  
**Date:** 2026-09-21  
**Code:** `semblon/jobs.py`, `semblon/application.py`

A future native client consumes this surface. Home is a client of it. Tk is not the architecture.

## Nouns

| Noun | Meaning | Source now |
|---|---|---|
| Job | One bounded unit of work (today: ingest/process) | `JobSnapshot` |
| Progress | Honest counts and stage/kind; no invented percent | `ProgressEvent` folded into the snapshot |
| Cancellation | Cooperative; cancelled ≠ completed; partial retained | `JobEngine.request_cancel` → ingest `cancel` |
| Application state | store path, latest run with faces | `default_store_path`, `latest_run_id` |
| Review state | board items (cluster / track / unassigned) | `load_board` |
| Person operations | Name / Merge / Split / Ignore / Note | `apply_*` → `review.py` |
| Search / read snapshots | people, unknown, activity, person query | existing `search_*`, Home readers, desktop service |

## Job states

`queued → starting → running → {completed, cancelled, failed}`  
`cancelling` is a running substate after cancel is requested.  
`paused` is named and **not implemented**.

## What the contract must not expose

Tk objects · Tk event-loop · Qt objects · FaceKit · Python UI callbacks as the public shape · SQLite connection objects · worker threads.

`JobSnapshot.to_dict()` is the R2 JSON shape. Callbacks on `JobEngine.submit_ingest` are a Python convenience, not the IPC.

## Home controls during a job

Enabled: Review, review.html, People, Unknown, Activity, Settings, Canvas, Search.  
Disabled: Choose folder, Resume (second ingest).  
Enabled: Cancel.

Review mutations during ingest wait on SQLite `busy_timeout`. They are not a second writer process. Naming faces of the *in-flight* run can see a board that is still growing — documented, not forbidden.

Review during ingest is a **Toplevel** on Home's root so Home keeps pumping Job events. A nested `Tk().mainloop()` is the actual reason Review used to be locked, not SQLite.

## R2

Next: named-pipe / stdio JSON of `JobSnapshot.to_dict()` plus the apply_* / load_board commands. No PyWinRT. No `.csproj` on `main`.
