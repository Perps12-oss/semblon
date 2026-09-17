# Roadmap reconcile (2026-09-17; S8 Reviewability + S7a evidence)

**Product:** Phase 1 human tests **approved** 2026-09-17. S7a dump evidence exists; **S8 Reviewability** (video face thumbs) is the open Phase 2 friction fix before S7b.  
**Performance:** P0 baseline frozen; P1 = native ARM64 measure (separate env/store). Do **not** change S1 correctness env or eps.

## Position

```text
FACE-000 … FACE-005  COMPLETE (docs/FACE-GATES.md)
S6 / 1.2             on main
S8 Interactive Review  shipped vertical (review-ui)
     │
     ├── Phase 1  real-world validation (review-ui)     ← APPROVED 2026-09-17
     ├── Phase 2  S8.1 friction + S8 Reviewability      ← OPEN (video thumbs; docs/S8-REVIEW-UI.md)
     └── Phase 3  S7a video files (sampled observations) ← DUMP EVIDENCE (docs/S7A.md)

PERF track (parallel; separate env — never swap S1):
     ├── P0  folder baseline 20260917T021045Z-48095f25   ← frozen
     ├── P1  native ARM64 timed measure                 ← BLOCKED (docs/PERF-P1-ARM64.md)
     └── P2+ EP / workers / batch / imread / SQLite     ← after P1 only
```

Core stills loop:

```text
PHOTO LIBRARY → OBSERVATIONS → CLUSTERS → HUMAN REVIEW → NAMED PEOPLE → GALLERY → IDENTIFY
```

Video path (current → intended):

```text
VIDEO → sampled frames → face observations → [S8 inspect] → S7b tracklets → review groups → optional PERSON
```

`observation ≠ tracklet ≠ person`. Do not solve video review scale by enabling stills DBSCAN on video observations.

S7 extends the **same** model through time. S8 renders it. GUI does not become the intelligence.  
Authoritative design: `docs/SEMBLON_MATURITY_BLUEPRINT.md` §§ S7–S8.  
Perf baseline: `docs/PERF-P0-BASELINE.md`.

## Concept map (UI ↔ existing code)

| Design concept | Existing Semblon contract today |
|---|---|
| Face observation | `faces` + `observations` (`frame_id`/`t_ms` set for video) |
| Frame | `observations.frame_id`, `t_ms` |
| Appearance (temporal) | Not a table yet — S7b tracklet / presence; ≠ §1.5 appearance space |
| Person + references | `persons`, `cluster_person`, named `faces.person_id` after **Name** |
| Cluster | Hypothesis — **never** a person until Name; **stills only** in product DBSCAN |
| Identity hypothesis | `identify` → ACCEPT \| UNKNOWN; POSSIBLE = planned UI |
| Review actions | `review.py` — **review-ui already calls these** |
| Video thumb | `path` + `frame_id` + `bbox` → render-time seek/crop (`review_ui`) |
| Progress | `progress.py` / `on_event` |
| Evidence export | `review.html` read-only |

## Retained (do not drop)

| Item | State |
|---|---|
| Progress `on_event` spine | Kept |
| ARM64 OpenCV binary `0xaa64` proven; S1 still x64 `cv2` | Kept — P1 installs pyd into **isolated** ARM64 env only |
| eps=0.40 / FACE gates / 22 confirmatory pairs | Frozen |
| Static `review.html` | Kept as export artifact |
| CLI power-user path | Kept |
| Perf P0 (221 files / 1299.3 s / x64 emulated) | Frozen — not an S1 retune |
| S7a video holdout from DBSCAN | Kept until S7b design |

## Deferred catalog

| Item | When |
|---|---|
| Cooperative cancellation | Before long-run process GUI |
| Structured `process.completed` | With process window |
| Per-file outcome UI lines | After validation if useful |
| Cluster elapsed heartbeat (not fake %) | Process window |
| **EP / GPU / workers / embed_batch / duplicate imread / SQLite commit policy** | **After PERF P1 only** (each alone) |
| Concurrent-process store-lock UX | Separate friction fix |
| Native ARM64 Semblon **consumption in S1 path** | Explicit decision after P1 evidence — not silent swap |
| x64-native FACE-000 | Needs genuine x64 PC |
| 10k scale | Scale path |
| **S7a video files** | **DUMP EVIDENCE** — `docs/S7A.md`; continue ingest; inspect via S8 Reviewability |
| **S7b–d** (tracklets / webcam / RTSP) | After S8 Reviewability (video faces visually inspectable) |
| Identify / Inbox UI + POSSIBLE | After Phase 1–2 naming |
| Full shell / search | After `docs/S8-TOOLKIT.md` dump-gate (PySide6 review vertical wired in spike; Canvas/search still later; Tk review-ui stays) |
| FastAPI / Electron / web / CustomTkinter | REJECT |
| Mass on-disk face PNG dump for video | REJECT — render-time crop from source |

## Phases (product)

### Phase 1 — Validate review-ui

**Approved 2026-09-17** (owner: all human tests).  
Process → review-ui → Name/Merge/Split/Ignore/Note → reopen → `identify --face`.  
On run `20260917T021045Z-48095f25`: treat `7225de9d` as REVIEW; do not retune eps.

### Phase 2 — S8.1 friction + S8 Reviewability

Home launcher as needed. **S8 Reviewability:** every video face observation independently inspectable via seek+crop (`docs/S8-REVIEW-UI.md`). Does not implement tracklets. Does not retune clustering.

### Phase 3 — S7a (selected; dump evidence exists)

Video files → sampled frame observations (`frame_id`, `t_ms`) → FaceKit embed → identify vs **persons**.  
Holdout from product DBSCAN retained. Not S7b tracking. Not webcam/RTSP. Not full S8 shell. Not scale. Not workers/EP.

## Performance track

See `docs/PERF-P0-BASELINE.md` and `docs/PERF-P1-ARM64.md`.  
P1 **blocked** on `opencv_geometry500.dll` load hang (ORT ARM64 OK). Emulation “3–8×” remains hypothesis. Do not parallelize the emulated stack until P1 unblocks or an explicit decision opens a different axis.

## Must not

- Swap OpenCV/ORT into the S1 correctness environment without an explicit decision.  
- Retune eps from a performance or one-folder review dump.  
- Open workers/EP before P1 native numbers (or a documented native-stack blocker).  
- Replace backend architecture to make the GUI easier.  
- Treat `unassigned=N` after video ingest as N people, or “fix” it with stills clustering.  
- Invent `SEMBLON_IMPLEMENTATION_PLAN.md` or parallel OBS tickets.
