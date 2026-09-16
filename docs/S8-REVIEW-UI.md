# S8 Interactive Review slice

**Status:** in progress on `grok/review-ui`  
**Not:** full S8 search/memory dashboard. **Not:** S7 video.

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

## Deferred

S7 video · identify/inbox UI · memory search dashboard · full S8.
