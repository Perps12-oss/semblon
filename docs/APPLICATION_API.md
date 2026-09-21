# Application API (APP-1 / R1)

**Status:** extracted from existing Python. Not a framework. Not WinUI.  
**Date:** 2026-09-21  
**Code:** `semblon/jobs.py`, `semblon/application.py`, Home control policy in `semblon/home_ui.py`  
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
| Job | One bounded unit of work (today: ingest/process) | `JobHandle` while running; `JobResult` when done |
| Progress | Honest counts and stage/kind; no invented percent | `ProgressEvent` via `on_event` |
| Cancellation | Cooperative; cancelled ≠ completed; partial retained | `JobEngine.cancel` → ingest `cancel` |
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
| `job_current()` | `JobEngine.current` / `busy` | Handle while running; None when idle |

Mutations (one writer: Python domain ops):

| Command | Existing call | Notes |
|---|---|---|
| `submit_ingest(folder, resume?)` | `JobEngine.submit_ingest` → `process_folder` | Engine owns the store. One ingest at a time. Second submit is `JobBusy` |
| `cancel_job()` | `JobEngine.cancel` | Cooperative at file boundaries |
| `apply_name` | `review_ui.apply_name` | Cluster / track members / unassigned face |
| `apply_merge` | `apply_merge` | Clusters only |
| `apply_split` | `apply_split` | Faces leave the cluster |
| `apply_ignore` | `apply_ignore` | Hide from board |
| `apply_note` | `apply_note` | `decisions.kind=note` |

Named later, not implemented as Job types in this slice: `watch`, `live`. The API must not assume stills-only.

## Job result status

```
completed | cancelled | failed
```

`JobEngine.busy` is true while a handle is claimed. `JobResult.status` is the terminal outcome delivered to `on_done`.

Progress stays on `ProgressEvent` (None means unknown — do not invent). Percent belongs to the presentation of an event that already has a denominator (`stills_percent`).

Callbacks on `JobEngine.submit_ingest` are a Python convenience, not the IPC. R2 will serialize handle/result fields, not widgets.

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
| People / Unknown / Activity / Search / Canvas | allowed | RO reads |
| Choose folder / Resume | blocked | would be a second ingest (`JobBusy`) |
| Cancel | allowed | cooperative cancel |

Review opens as a `Toplevel` on Home's root so Home keeps pumping job events. Standalone `run_review_ui()` still owns its own loop when there is no parent.

## Identity firewall

This API does not enrol, merge, or compare faces. FaceKit remains the only identity engine. Optional observers must not write `faces.person_id` or `embeddings.modality='face'`.
