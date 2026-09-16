# Roadmap reconcile (2026-09-16)

**Pause coding expansion.** Validate S8 Interactive Review in real use first.

## Position

```text
FACE-000 … FACE-005  COMPLETE (docs/FACE-GATES.md)
S6 / 1.2             on main
S8 Interactive Review  NOW (review-ui; smallest S8 vertical)
     │
     ▼
Phase 1  real-world product validation (you using it)
Phase 2  S8.1 friction fixes discovered in use
Phase 3  pick ONE deferred axis (below) — not a giant release
```

Core loop now connected:

```text
PHOTO LIBRARY → OBSERVATIONS → CLUSTERS → HUMAN REVIEW → NAMED PEOPLE → GALLERY → IDENTIFY
```

S8 slice connects **Clusters → Human Review → Named People**. That is the milestone. Do not turn Semblon into a dashboard before this loop is exercised.

## Retained (do not drop)

| Item | State | Notes |
|---|---|---|
| Progress event spine `process_folder(..., on_event=...)` | **Kept** | GUI infrastructure; truthful discover/ingest %. Not a finished process window. |
| ARM64 OpenCV binary `0xaa64` | **Kept, qualified** | Binary proven; Semblon S1 still uses x64 OpenCV under x64 Python (emulated on ARM64 host). Not “S1 runs native ARM64.” |
| eps=0.40 / FACE gates / confirmatory 22 pairs | **Frozen** | Do not retune. Do not invent 10k. |
| Static `review.html` | **Kept** | Read-only evidence/export. Interactive surface is `review-ui`. |
| CLI power-user path | **Kept** | `review` / `name` / `merge` / `split` / `identify` unchanged. |

## Deferred (explicit — not forgotten)

| Item | Why deferred | When to reopen |
|---|---|---|
| Cooperative **cancellation** (Stop between files) | Needed before long-run GUI process UX | Before serious process window |
| **Structured process completion** (run_id, store, out, summaries via events — not stdout scrape) | GUI Open Review after `process.completed` | With process window / S8.1 |
| Richer **per-file outcome** lines in UI | Spine can grow; avoid telemetry sprawl now | After validation if useful |
| Cluster **heartbeat** (elapsed, not fake %) | DBSCAN has no honest denominator | Process window |
| Workers / EP / CPU·GPU / provider evidence | Performance phase, not S8 | After product loop proven |
| Native ARM64 Semblon swap / x64-native FACE-000 | Evidence gaps, not GUI work | Separate machine/env tickets |
| **10k** scale run | Design target only; 90 stills evidenced | Scale path when ready |
| **S7 video** | Unchanged; UI did not replace it | After photo loop is real |
| Identify / Inbox **UI** | Gallery must be exercised by real naming first | After Phase 1–2 |
| Full S8 search / memory dashboard | Refused until named gallery + repeated decide loop | Later S8 |

## Three phases (no new ticket until Phase 1)

### Phase 1 — S8 real-world validation

Double-click → pick Pictures → Process → Review UI → Name / Merge / Split / Ignore / Note → Close → Reopen → persistence → `identify --face`.

Unit tests do not replace this.

### Phase 2 — S8.1 friction from use

Fix only what you hit (nav, thumbs, merge/split UX, “already reviewed”, process progress). Product-driven, not imaginary dashboard.

### Phase 3 — one deferred axis

Choose deliberately among:

- Product/UX: gallery → identify/inbox UI  
- Engine: cancel + structured completion + (later) workers/EP  
- Platform: S7 video  
- Scale: 10k  

Do **not** merge these into one release.

## Must not

- Put “everything” into the GUI because a window exists.  
- Open S7 because review-ui shipped.  
- Build identify/inbox screens to fill the roadmap.  
- Fake cluster percent.  
- Quietly delete 10k or ARM64/x64 honesty from docs.
