# Application API (APP-1 / R1)

**Status:** extracted from existing Python. Not a framework. Not WinUI.  
**Date:** 2026-09-22  
**Code:** `semblon/application.py` (`Application` façade), `semblon/jobs.py`, Home control policy in `semblon/home_ui.py`, native shell in `semblon/native_shell/`  
**Authority:** `docs/CONTRACTS.md`, `docs/SEM-ARCH-V1.4.md`. This page names UI-visible capabilities. It does not add columns.

A future native client consumes this surface. Home is a client of it. The Qt/PySide `semblon shell` is the authorized production shell path (R3). Tk is not the architecture.

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
| Cancellation | Cooperative; cancelled ≠ completed; partial retained | `JobEngine.cancel` / `Application.cancel_job` → ingest `cancel` |
| Pause | Cooperative; same job stays claimed; not consuming ingest work | `JobEngine.pause` / `unpause` · `Application.pause_job` / `unpause_job` |
| Application state | store path, latest run with faces | `default_store_path`, `latest_run_id` |
| Review state | board items (cluster / track / unassigned) | `load_board` / `Application.board` |
| Person operations | Name / Merge / Split / Ignore / Note / Rule out (gate default ON; ship claim CLOSED / DONE §I.5) | `apply_*` → `review.py` (Home Inspector + review-ui) |
| Search / read snapshots | people, unknown, activity, person query, canvas overlay | `search_*`, `inbox`, `activity` / Home `read_activity_snapshot`, `load_canvas` |

CONTRACTS family this maps onto: Media, Observation, Face, Embedding, Track, Episode (not a first-class UI command yet), Person, Decision, SearchResult, Job, Progress, Cancellation.

## Commands (capabilities, not widgets)

Reads:

| Command | Existing call | Notes |
|---|---|---|
| `board(store, run_id?)` | `resolve_run_id` + `load_board` · `Application.board` | Default run is latest with faces |
| `people(store)` | `search_people` · `Application.people` | Named persons only |
| `search_person(store, query)` | `search_person` | Lookup, not identity |
| `inbox(store, run_id)` | `inbox` · `Application.inbox` | UNKNOWN is valid |
| `activity(store, run_id?)` | `application.activity` → Home `read_activity_snapshot` | groups / relationships / events; track ≠ person |
| `canvas(store, run_id?)` | `load_canvas` · `Application.canvas` | Overlay payload. Cluster ≠ person |
| `job_current()` | `Application.job_current` / `busy` / `state` / `paused` | Handle while running; None when idle |

Mutations (one writer: Python domain ops):

| Command | Existing call | Notes |
|---|---|---|
| `submit_ingest(folder, resume?)` | `Application.submit_ingest` → `JobEngine` → `process_folder` | Engine owns the store. One ingest at a time. Second submit is `JobBusy` |
| `pause_job()` | `Application.pause_job` → `JobEngine.pause` | Cooperative at file/stage gates |
| `unpause_job()` | `Application.unpause_job` → `JobEngine.unpause` | Continues the **same** in-flight job |
| `cancel_job()` | `Application.cancel_job` → `JobEngine.cancel` | Cooperative at file boundaries; works while paused |
| `apply_name` | `review_ui.apply_name` | Cluster / track members / unassigned face |
| `apply_merge` | `apply_merge` | Clusters only |
| `apply_split` | `apply_split` | Faces leave the cluster |
| `apply_ignore` | `apply_ignore` | Hide from board |
| `apply_note` | `apply_note` | `decisions.kind=note` |
| `apply_rule_out` | `apply_rule_out` | Durable reject (`action=rule_out`); gate default **ON** (`semblon.gates.RULED_OUT`); opt out `SEMBLON_RULED_OUT=0`. Home Inspector **Rule out** + review-ui. **Ship claim CLOSED / DONE** (§I.5). See `docs/CONTRACTS-RULED-OUT.md` |

Named later, not implemented as Job types in this slice: `watch`, `live`. The API must not assume stills-only.

**Ruled out:** product-wire ship claim **CLOSED / DONE** by owner 2026-09-21 (`docs/CONTRACTS-RULED-OUT.md` · SEM-ARCH §I.5). Chrome on Home Inspector + review-ui when gate ON.

## Job states (V1.4 C.2) — COMPLETE

```
idle → running → paused → running → completed
running → cancelling → cancelled
paused → cancelling → cancelled
running/paused → failed
```

`JobEngine.state` / `Application.state` reports `idle` | `running` | `paused` | `cancelling`.  
`JobResult.status` is terminal only: `completed` | `cancelled` | `failed`.

**Queued:** `ProgressEvent` kind `queued` (presentation / Home status). It is **not** a `JobEngine.state` value. Claiming a job moves state to `running` when the worker starts.

### Pause semantics

> `paused` means resumable and not currently consuming ingest processing resources.

**Granularity (honest):** cooperative **between files** and at the same stage checks where cancel is already polled inside `process_folder` → `ingest`. Mid-decode / mid-embed pause is **not** claimed.

`unpause` / `unpause_job` continues the same claimed job. It is not the same as Home / shell **Resume** after cancel (that is a new `submit_ingest(..., resume=True)`).

## Job result status

```
completed | cancelled | failed
```

`JobEngine.busy` / `Application.busy` is true while a handle is claimed (including while paused). `JobResult.status` is the terminal outcome delivered to `on_done`.

Progress stays on `ProgressEvent` (None means unknown — do not invent). Percent belongs to the presentation of an event that already has a denominator (`stills_percent`).

Callbacks on `submit_ingest` are a Python convenience, not the IPC. R2 serializes handle/result fields, not widgets.

## What the contract must not expose

Tk objects · Tk event-loop · Qt objects · FaceKit · Python UI callbacks as the public shape · SQLite connection objects · worker threads · InsightFace / ORT sessions · clusterer internals.

## Production shell (R3 native) vs Track-1 Tk

| Surface | Command | Role |
|---|---|---|
| **Native production shell** | `semblon shell` | Authorized R3 path (`semblon/native_shell/`). Qt/PySide via optional `[gui]`. Talks only through `Application`. |
| Tk Home | `semblon home` | Compatibility frontend (Library \| Workspace/Canvas \| Inspector). Still JobEngine door. Not permanent AppShell. |
| `review-ui` | `semblon review-ui` | KEEP evidence vertical (Toplevel on Home or standalone). |
| `review.html` | export | Engineering / forensic artifact — **not** the normal user workflow. |
| S8 toolkit spike | `tools/s8_toolkit_spike` | Reference only. Do not auto-promote. |

Native shell IA (R3-BRIEF §4):

```text
Library sidebar │ Workspace / Intelligence Canvas │ Inspector
```

Job controls: Choose folder / Pause / Resume / Cancel.  
While running (not paused): Pause on, Resume off, Cancel on.  
While paused: Pause off, Resume on (`unpause_job`), Cancel on.  
While idle with a cancelled/interrupted folder: Resume on (resume-after-cancel).  

| Operation | During ingest | Actual dependency |
|---|---|---|
| Review (read board) | allowed | RO SQLite + `busy_timeout=5000` |
| Review Name/Merge/Split/Ignore/Note | allowed, serialized | same store writer as ingest; waits on `busy_timeout` |
| People / Unknown / Activity / Search / Canvas | allowed | RO reads |
| Choose folder | blocked | would be a second ingest (`JobBusy`) |
| Pause / Unpause | allowed | cooperative between files |
| Cancel | allowed | cooperative cancel (also from paused) |
| Resume after cancel | idle only | new submit with `resume=True` |

`JobEngine` is the only ingest door for Home / native shell / Review / IPC probe. Headless CLI `semblon process` / `ingest` may call `process_folder` directly — that is not a second application door. Home, Review, and `semblon shell` must never import or call `process_folder`.

## Identity firewall

This API does not enrol, merge, or compare faces. FaceKit remains the only identity engine. Optional observers must not write `faces.person_id` or `embeddings.modality='face'`.
