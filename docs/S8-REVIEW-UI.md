# S8 Interactive Review slice

**Status:** shipping vertical on main-line work; **S8 Reviewability** (video face thumbs) is the open friction fix.  
**This is** the beginning of S8 (smallest interactive vertical).  
**Design target** for the broader shell/Canvas: `docs/SEMBLON_MATURITY_BLUEPRINT.md` §S8 + `docs/ROADMAP-RECONCILE.md`.  
**Not yet:** full shell, Intelligence Canvas, tracklet review groups, identify/inbox UI, search. **Not:** S7b engine.

## What this slice is

A stdlib **tkinter** window that calls existing [`semblon/review.py`](../semblon/review.py) APIs:

- Name (cluster or unassigned face → person)
- Merge / Split / Ignore / Note
- Reload from SQLite after each mutation

Entry: `semblon review-ui [--store …] [--run …]` (`--run` omitted → latest run).

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

1. Name → person + gallery faces → `identify --face` ACCEPT same person.  
2. Merge → reload → decision persists; donor cluster gone.  
3. Split → reload → new cluster + decision; split faces unnamed until named.

## Product milestone (Phase 1)

Process → review-ui → name/correct → close/reopen → decisions still there — without PowerShell ID copying.

## S8 Reviewability (open — video inspectability)

Forensic run `20260917T161452Z-a012c0fe` (2 videos, 1 Hz): **231** sampled frames → **434** accepted face observations → product **0** clusters because S7a holds video out of DBSCAN. Offline frozen params show substantial temporal compression into a few groups; that is **not** person proof (`cluster ≠ person`).

**Bug:** thumbs used `cv2.imread(media.path)`, which returns `None` for `.mp4`, so the UI drew empty rectangles.

**Fix (narrow):** board members carry provenance (`source_type`, `path`, `frame_id`, `t_ms`, `bbox`, `face_id`, `observation_id`). Render-time crop:

```text
stills: path → imread → bbox crop
video:  path + frame_id → VideoCapture seek → bbox crop → thumbnail
```

No mass on-disk PNG dump. No clustering / threshold / sampling changes. List may still be one row per face until S7b tracklets exist — inspectability first.

## Next (ordered)

1. Phase 1 real use — **approved 2026-09-17**.  
2. Phase 2 friction: double-click **home** (Choose folder / Open Review); **S8 Reviewability** video thumbs (this doc).  
3. Phase 3 axes in parallel: **S7a** evidence continues (`docs/S7A.md`); PySide6 dump-gate (`docs/S8-TOOLKIT.md` — review actions wired in `tools/s8_toolkit_spike`; full Canvas still deferred).  
4. **S7b** tracklets / review groups — only after video observations are visually inspectable. Do not pretend stills clusters are the video review unit.
