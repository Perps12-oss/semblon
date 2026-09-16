# S8 Interactive Review slice

**Status:** on `grok/review-ui` (merge when ready).  
**Roadmap pause:** after merge, **Phase 1 real-world validation** before more code — see [`ROADMAP-RECONCILE.md`](ROADMAP-RECONCILE.md).

**This is** the beginning of S8 (smallest interactive vertical).  
**Not:** full S8 search/memory dashboard. **Not:** S7 video. **Not:** identify/inbox UI.

## What this slice is

A stdlib **tkinter** window that calls existing [`semblon/review.py`](../semblon/review.py) APIs:

- Name (cluster or unassigned face → person)
- Merge / Split / Ignore / Note
- Reload from SQLite after each mutation

Entry: `semblon review-ui [--store …] [--run …]` (`--run` omitted → latest run).

## Rules preserved

- Clusters are evidence; people are human-confirmed identities.
- STRONG clusters stay **unnamed** until the user chooses Name.
- Static `review.html` remains a read-only export/evidence artifact.
- Power-user CLI `review` / `name` / `merge` / `split` unchanged.
- No new clustering, thresholds, FastAPI, CustomTkinter, watcher, or installer.

## Acceptance (state, not just buttons)

1. Name → person + gallery faces → `identify --face` ACCEPT same person.  
2. Merge → reload → decision persists; donor cluster gone.  
3. Split → reload → new cluster + decision; split faces unnamed until named.

## Product milestone

Process → review-ui → name/correct → close/reopen → decisions still there — without PowerShell ID copying.

## Deferred (catalog, not dropped)

Progress `on_event` spine kept. Cancellation, structured `process.completed`, per-file UI outcomes, cluster elapsed heartbeat, workers/EP/GPU, native ARM64 Semblon consumption, x64-native FACE-000, 10k scale, S7 video, identify/inbox UI, full S8 search — see [`ROADMAP-RECONCILE.md`](ROADMAP-RECONCILE.md).
