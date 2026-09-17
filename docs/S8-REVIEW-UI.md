# S8 Interactive Review slice

**Status:** on `grok/review-ui`.  
**This is** the beginning of S8 (smallest interactive vertical).  
**Design target** for the broader shell/Canvas: `docs/SEMBLON_MATURITY_BLUEPRINT.md` §S8 + `docs/ROADMAP-RECONCILE.md`.  
**Not yet:** full shell, Intelligence Canvas, video overlays, identify/inbox UI, search. **Not:** S7 engine.

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

## Acceptance (state, not just buttons)

1. Name → person + gallery faces → `identify --face` ACCEPT same person.  
2. Merge → reload → decision persists; donor cluster gone.  
3. Split → reload → new cluster + decision; split faces unnamed until named.

## Product milestone (Phase 1)

Process → review-ui → name/correct → close/reopen → decisions still there — without PowerShell ID copying.

## Next (ordered)

1. Phase 1 real use — **approved 2026-09-17**.  
2. Phase 2 friction fixes as they appear.  
3. Phase 3 axis selected: **S7a** (`docs/S7A.md`). Full S8 shell / Canvas(Video) wait for S7a evidence.
