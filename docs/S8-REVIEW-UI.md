# S8 Interactive Review slice

**Status:** shipping vertical on main-line work; **S8 Reviewability** (video face thumbs) is on `main` (PR #28). Static `review.html` (`export`) uses the same `path`+`frame_id`+`bbox` seek/crop.  
**This is** the beginning of S8 (smallest interactive vertical).  
**Design target** for the broader canvas: `docs/SEM-ARCH.md`. This file is the shipping review slice, not the plan.  
**Not yet:** full shell, Intelligence Canvas, identify/inbox UI, search. S7b derived tracks are rendered here; the engine stays in `semblon tracks`.

## What this slice is

A stdlib **tkinter** window that calls existing [`semblon/review.py`](../semblon/review.py) APIs:

- Name (cluster, unassigned face, or derived track members → person)
- Merge / Split / Ignore / Note
- Reload from SQLite after each mutation

Entry: `semblon review-ui [--store …] [--run …]` (`--run` omitted → latest run **that has faces**).

## Seed of the future shell

```text
today:  ReviewApp (list + thumbs + actions)
later:  Application shell → Workspace → Intelligence Canvas → Inspector
```

`review-ui` proves: **GUI → existing domain ops → store → identify**.  
Do not grow a second identity path inside the UI.

## Rules preserved

- Clusters are evidence; people are human-confirmed identities.
- STRONG clusters stay **unnamed** until the user chooses Name.
- Static `review.html` remains a read-only export/evidence artifact.
- Power-user CLI unchanged.
- No new clustering, thresholds, FastAPI, CustomTkinter, watcher, or installer.
- **observation ≠ tracklet ≠ person.** Unassigned video faces are face observations, not people. Do not shrink `unassigned=N` by enabling stills DBSCAN on video.

## Acceptance (state, not just buttons)

1. Name → person + gallery faces → `identify --face` ACCEPT same person (including Name on a derived track; track id ≠ person id).  
2. Merge → reload → decision persists; donor cluster gone.  
3. Split → reload → new cluster + decision; split faces unnamed until named.

## Product milestone (Phase 1)

Process → review-ui → name/correct → close/reopen → decisions still there — without PowerShell ID copying.

## S8 Reviewability (on `main` — video inspectability)

Forensic run `20260917T161452Z-a012c0fe` (2 videos, 1 Hz): **231** sampled frames → **434** accepted face observations → product **0** clusters because S7a holds video out of DBSCAN. Offline frozen params show substantial temporal compression into a few groups; that is **not** person proof (`cluster ≠ person`).

**Bug:** thumbs used `cv2.imread(media.path)`, which returns `None` for `.mp4`, so the UI drew empty rectangles.

**Fix (narrow):** board members and `export` face rows carry provenance (`source_type`, `path`, `frame_id`, `t_ms`, `bbox`, `face_id`, `observation_id`). Render-time crop:

```text
stills: path → imread → bbox crop
video:  path + frame_id → VideoCapture seek → bbox crop → thumbnail
```

Applies to `review-ui` and static `review.html`. No mass on-disk PNG dump. No clustering / threshold / sampling changes.

**List:** video unassigned faces are grouped by derived S7 Track (IoU+time). Name on a track enrols member observations as one person (human decision). Track id is never person id. Ignore/Note on a track still require a clicked face. Untracked video faces and stills stay one row each.

`--run` omitted (and `process` after a skip-all ingest) uses the latest run **that still has faces**. An empty incremental run must not blank `review-ui` / `review.html` while prior results remain on the store.

Both surfaces show a one-line empty state (`this run: N faces; store has M on run …`) so an empty skip-all, all-held-out (`ok=0`), and missing `media.path` are distinguishable. Failed thumbs render **file missing** instead of a blank rectangle.

## Next

This file is the shipping review vertical, not the plan. **Planned work:** `docs/SEM-ARCH.md`. Do not grow a full shell or a second identity path from this file.
