# Application API (R1)

**Status:** extracted from existing Python. Not a framework. Not WinUI.  
**Date:** 2026-09-21  
**Code:** `semblon/jobs.py`, `semblon/application.py`  
**Authority:** `docs/CONTRACTS.md`, `docs/SEM-ARCH.md`. This page names UI-visible capabilities. It does not add columns.

A future native client consumes this surface. Home is a client of it. Tk is not the architecture.

```
UI  →  Application / Job boundary  →  existing Python implementation
```

not:

```
Home button  →  Home-owned worker  →  Tk callback chain  →  ingest
```

## Nouns

| Noun | Meaning | Source now |
|---|---|---|
| Job | One bounded unit of work (today: ingest/process) | `JobSnapshot` |
| Progress | Honest counts and stage/kind; no invented percent | `ProgressEvent` folded into the snapshot |
| Cancellation | Cooperative; cancelled ≠ completed; partial retained | `JobEngine.request_cancel` → ingest `cancel` |
| Application state | store path, latest run with faces | `default_store_path`, `latest_run_id` |
| Review state | board items (cluster / track / unassigned) | `load_board` |
| Person operations | Name / Merge / Split / Ignore / Note | `apply_*` → `review.py` |
| Search / read snapshots | people, unknown, activity, person query, canvas overlay | `search_*`, `inbox`, Home `read_activity_snapshot`, `load_canvas` |
| Observation overlay | `path` + `frame_id` + `bbox` + optional track lane | `load_canvas` / `overlay_boxes` |

CONTRACTS family this maps onto: Media, Observation, Face, Embedding, Track, Episode (not a first-class UI command yet), Person, Decision, SearchResult, Job, Progress, Cancellation.

## Commands (capabilities, not widgets)

Reads:

| Command | Existing call | Notes |
|---|---|---|
| `board(store, run_id?)` | `resolve_run_id` + `load_board` | Default run is latest with faces |
| `people(store)` | `search_people` | Named persons only |
| `search_person(store, query)` | `search_person` | Lookup, not identity |
| `inbox(store, run_id)` | `inbox` | UNKNOWN is valid |
| `activity(store, run_id)` | Home `read_activity_snapshot` | groups / relationships / events; track ≠ person |
| `canvas(store, run_id?)` | `load_canvas` | Overlay payload. Cluster ≠ person |
| `job_snapshot()` | `JobEngine.snapshot` | JSON-safe |

Mutations (one writer: Python domain ops):

| Command | Existing call | Notes |
|---|---|---|
| `submit_ingest(folder, store, resume?)` | `JobEngine.submit_ingest` → `process_folder` | One ingest at a time. Second submit is `JobBusy` |
| `cancel_job()` | `JobEngine.request_cancel` | Cooperative at file boundaries |
| `apply_name` | `review_ui.apply_name` | Cluster / track members / unassigned face |
| `apply_merge` | `apply_merge` | Clusters only |
| `apply_split` | `apply_split` | Faces leave the cluster |
| `apply_ignore` | `apply_ignore` | Hide from board |
| `apply_note` | `apply_note` | `decisions.kind=note` |

Named later, not implemented as Job types in this slice: `watch`, `live`. The API must not assume stills-only.

## Job states

```
queued → starting → running → {completed, cancelled, failed}
```

`cancelling` is a running substate after cancel is requested.  
`paused` is named and **not implemented**.

Progress fields on `JobSnapshot` (None means unknown — do not invent):

```
job_id type state source store run_id resume
files_total files_processed faces skipped failed
elapsed_s rate eta_s current_stage kind error stalled
```

Percent belongs to the presentation of a `ProgressEvent` that already has a denominator (`stills_percent`). The snapshot does not invent one.

`JobSnapshot.to_dict()` is the R2 JSON shape. Callbacks on `JobEngine.submit_ingest` are a Python convenience, not the IPC.

## What the contract must not expose

Tk objects · Tk event-loop · Qt objects · FaceKit · Python UI callbacks as the public shape · SQLite connection objects · worker threads · InsightFace / ORT sessions · clusterer internals.

## Home controls during a job (Track-1)

Enabled while ingest runs: Review, review.html, People, Unknown, Activity, Settings, Canvas, Search.  
Disabled: Choose folder, Resume (that would be a second ingest).  
Enabled: Cancel.

| Operation | During ingest | Actual dependency |
|---|---|---|
| Review (read board) | allowed | RO SQLite + `busy_timeout=5000` |
| Review Name/Merge/Split/Ignore/Note | allowed, serialized | same store writer as ingest; waits on `busy_timeout` |
| People / Search / Unknown / Activity / Canvas | allowed | RO + `busy_timeout` |
| Choose folder / Resume | disabled | one ingest job |
| Cancel | enabled | cooperative flag |

Review mutations during ingest are not a second writer *process*. Naming faces of the *in-flight* run can see a board that is still growing — documented, not forbidden. Do not pretend the board is a frozen snapshot of a finished run.

Review during ingest is a **Toplevel** on Home's root so Home keeps pumping Job events. A nested `Tk().mainloop()` is the actual reason Review used to be locked, not SQLite.

## Concurrency / read-safety

- Store writes: `semblon.store.connect` already sets WAL + `busy_timeout=5000`.
- Search / inbox / canvas / activity already open `mode=ro` with the same timeout.
- `load_board` / `resolve_run_id` now set the same timeout so Review can open while ingest commits batches.
- Two Python connections in one process is not two writer *processes*. A future native UI must not open a second SQLite writer.

## R2 (not this slice)

Intended later probe:

```
Native UI  ↔  JSON IPC (named pipe / stdio)  ↔  Python application/backend
```

Commands would be JSON objects such as `{ "op": "submit_ingest", ... }` and `{ "op": "job_snapshot" }`. Events would be `JobSnapshot.to_dict()`. No PyWinRT. No `.csproj` on `main`.

## What remains Tk-specific

Home widgets, StillProgressBar, list Toplevels, ReviewApp layout, Canvas PhotoImage preview. Those stay clients.

## What remains unsuitable for future IPC as-is

- `on_event` / `on_done` Python callables on `JobEngine.submit_ingest`
- Tk `parent=` on Review / Canvas
- `board["_tracks_cache"]` (process-local cache object)
- Home `read_activity_snapshot` living next to widgets (should move before R2)
- Any FaceKit / `engine.load_app` import from a UI process
