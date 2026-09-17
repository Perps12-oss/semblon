# Roadmap reconcile (2026-09-16; design update same day)

**Implementation pause for engine/GUI expansion until Phase 1 validation.**  
**Design work** may update existing S7/S8 docs (this reconcile + maturity blueprint) without opening S7 code.

## Position

```text
FACE-000 … FACE-005  COMPLETE (docs/FACE-GATES.md)
S6 / 1.2             on main
S8 Interactive Review  shipped vertical (review-ui) — beginning of S8
     │
     ├── Phase 1  real-world validation (you using review-ui)     ← CURRENT GATE
     ├── Phase 2  S8.1 friction fixes from use
     └── Phase 3  ONE axis: S8 shell slice | engine prep | S7a | scale
```

Core stills loop:

```text
PHOTO LIBRARY → OBSERVATIONS → CLUSTERS → HUMAN REVIEW → NAMED PEOPLE → GALLERY → IDENTIFY
```

S7 extends the **same** model through time (Frame → Face observation → Appearance → hypothesis).  
S8 **renders and operates** on that model (shell + Intelligence Canvas). GUI does not become the intelligence.

Authoritative design text: `docs/SEMBLON_MATURITY_BLUEPRINT.md` §§ S7 and S8 (updated).

## Concept map (UI ↔ existing code)

| Design concept | Existing Semblon contract today |
|---|---|
| Face observation | `faces` + `observations` (`frame_id` NULL for stills) |
| Frame | `observations.frame_id`, `t_ms` (DDL ready; unused by stills path) |
| Appearance (temporal) | Not a table yet — S7b tracklet / presence; do not confuse with §1.5 appearance space |
| Person + references | `persons`, `cluster_person`, named `faces.person_id` after **Name** |
| Cluster | Hypothesis group — **never** a person until Name |
| Identity hypothesis | `identify` → ACCEPT \| UNKNOWN today; POSSIBLE = planned UI (needs contract) |
| Review actions | `review.py` (name/merge/split/ignore/note) — **review-ui already calls these** |
| Progress | `progress.py` / `on_event` — process/discover/ingest/cluster/export |
| Evidence export | `review.html` read-only |

## Retained (do not drop)

| Item | State |
|---|---|
| Progress `on_event` spine | Kept — future process window consumes it |
| ARM64 OpenCV binary `0xaa64` proven; S1 still x64 `cv2` | Kept, qualified |
| eps=0.40 / FACE gates / 22 confirmatory pairs | Frozen |
| Static `review.html` | Kept as export artifact |
| CLI power-user path | Kept |

## Deferred catalog (not forgotten)

| Item | When |
|---|---|
| Cooperative cancellation | Before long-run process GUI |
| Structured `process.completed` (run_id, store, out, summaries) | With process window |
| Per-file outcome UI lines | After validation if useful |
| Cluster elapsed heartbeat (not fake %) | Process window |
| Workers / EP / GPU evidence | Performance phase |
| Native ARM64 Semblon consumption / x64-native FACE-000 | Separate env tickets |
| 10k scale | Scale path |
| **S7a–d engine** | After stills loop real; design already reconciled in blueprint |
| Identify / Inbox UI + POSSIBLE contract | After Phase 1–2 naming |
| Full shell (Home/Photos/Videos/People/Canvas/Search) | S8 slices after Phase 1–2 |
| FastAPI / Electron / web / CustomTkinter | REJECT |

## Phases

### Phase 1 — Validate review-ui (gate)

Double-click → Pictures → process → review-ui → Name/Merge/Split/Ignore/Note → reopen → `identify --face`.

### Phase 2 — S8.1 friction from use

Only fixes discovered in Phase 1.

### Phase 3 — choose one implementation axis

**A. S8 shell (stills)** — application shell + Photos + People + Canvas(photo) + Inspector over existing APIs; consume `on_event` for processing.  
**B. Engine prep** — cancel + structured completion (still no workers/EP).  
**C. S7a** — video file ingest → frames → faces → Appearances → identify vs persons (CLI/evidence first; Canvas video later).  
**D. Scale** — 10k.

Do **not** merge A+B+C+D into one release.

## Must not

- Replace backend architecture to make the GUI easier.  
- Open S7 code merely because Canvas designs show video.  
- Auto-assign known people on vague similarity.  
- Treat clusters as people / identify vs clusters.  
- Fake cluster %.  
- Build search/chat/dashboard first.  
- Invent `SEMBLON_IMPLEMENTATION_PLAN.md` or parallel OBS tickets.
