# SEM-ARCH V1.4 — Reconciled architecture and roadmap authority

**Status:** AUTHORITATIVE planned-work and architecture source  
**Date:** 2026-09-21

This file replaces stale or duplicated roadmap interpretations.

- `docs/PRODUCT.md` remains the product contract (frozen v1 + production amendments).
- `docs/CONTRACTS.md` remains schema / CLI / runtime authority.
- `docs/FACE-GATES.md` remains the closed FACE-002→005 validation index.

No second north star is allowed.

---

## A) Reconciled baseline (new truth)

> FACE-001→FACE-005 are closed.  
> The identity engine is shipped/gated and is no longer the primary architecture risk.  
> Semblon is transitioning from an identity-engine project to a local-first image intelligence application.

This reconciliation **does not** reopen FACE gates, retune identity thresholds, or restart old handover queues.

### Current product status picture

| Area | Reconciled status |
|---|---|
| Identity / face pipeline | **SHIPPED / GATED** |
| Incremental ingest | **SHIPPED** |
| Inbox | **SHIPPED** |
| Named people / unknown | **SHIPPED** |
| Memory / S6 | **SHIPPED slice** |
| Video sampling / S7a | **SHIPPED slice** |
| Derived tracks / S7b | **SHIPPED slice** |
| Watch | **EXISTS** |
| Live | **EXISTS / hardware proof pending** |
| Canvas | **EXISTS, prototype implementation** |
| Search | **EXISTS** |
| Home | **SHIPPED but architecturally constrained** |
| Review UI | **SHIPPED, legacy Tk surface** |
| Native application shell | **NOT decided/implemented** |
| APP-1 JobEngine boundary | **MERGED** (`main`) |
| APP-1 C.2 paused / unpause | **IMPLEMENTED** (code+unit tests; Windows live gate still required) |
| IPC boundary | **NOT implemented** |
| Native ARM64 performance | **BLOCKED** |
| Multi-worker ingest | **EXPERIMENTAL / not default** |
| GPU | **NOT productized** |
| Rust | **DEFERRED until measurements justify it** |

---

## B) Frozen invariants

1. Personal, local-first Windows app. One user. No cloud/ACC. Originals stay put.  
2. `cluster -> review -> person -> name`; never `cluster = person`.  
3. Unknown is valid; wrong identity is worse than unknown.  
4. FaceKit / InsightFace remains the identity engine.  
5. Optional modalities (OCR/CLIP/pose/objects/color/etc.) are observation-only and must not silently vote on identity.  
6. `report` and read-only diagnostics must never write to the store.  
7. FACE-002→FACE-005 are evidence index entries, not an active queue.  
8. S1 golden identity settings remain frozen; do not retune clustering to reduce `unassigned`.

---

## C) Active work (immediate priority)

## C.1 APP-1 / R1 is the next merge gate

APP-1 is not a "make Tk Home nicer" project.  
APP-1 is the extraction of a stable application/job boundary from the current implementation.

Target seam:

```text
UI / Frontend (Tk now; PySide/WinUI/other later)
            |
      Application API
            |
         JobEngine
            |
     Existing ingest engine
```

Critical rule:

> UI observes and commands jobs.  
> UI does not own long-running computation.

### APP-1 branch policy

- Start clean from current `main`.
- Do not merge historical APP-1 drafts wholesale.
- Prior drafts (for example #48 / #50) are reference material only; selectively recover validated pieces.

## C.2 `paused` contract must be made real now

Job states:

```text
queued -> running -> paused -> running -> completed
running -> cancelling -> cancelled
running/paused -> failed
```

V1 paused semantics:

> `paused` means resumable and not currently consuming ingest processing resources.

**Implementation (code on this branch):** `JobEngine.pause` / `unpause` / `state` / `paused`. The ingest gate blocks in `JobEngine._gate` (passed as `cancel=` into `process_folder`).  

**Granularity (honest):** cooperative **between files** and at the same stage polls where cancel already runs. Mid-decode / mid-embed pause is **not** claimed.

Windows live proof of pause/unpause remains part of the C.3 gate (not satisfied by unit tests alone).

## C.3 APP-1 acceptance is a hard Windows gate

Passing tests alone is insufficient.  
APP-1 must be validated on real Windows with live ingest.

Required proof:

- UI remains responsive while ingest runs.
- ingest/progress continue.
- cancel works.
- cancelled state is recoverable.
- resume works.
- Home can read current state during ingest.
- Review can remain open during ingest.
- People/Search surfaces remain usable (no global lockout while ingest runs).
- no nested Tk mainloop.
- no Tk calls from worker threads.
- no duplicated JobEngine.
- no hidden second ingest implementation.
- no regression to identity semantics.
- process termination does not corrupt the store.
- timings are recorded.

Only merge APP-1 after this gate passes.

---

## D) Immediate follow-up after APP-1

## D.1 R2 IPC probe (boundary test, not product shell)

R2 remains in-scope but is reframed as an architecture boundary proof:

```text
external/native client <-> IPC <-> JobEngine <-> existing engine
```

Probe scope only:

- start job
- status query
- progress stream
- cancel
- resume
- result retrieval
- error handling

No need to implement the final IPC system in R2.

## D.2 R3 becomes frontend architecture decision

R3 question is not "WinUI or Qt?"

R3 question:

> Which frontend architecture should own the production application shell, given the APP-1 boundary and measured workloads?

Candidates can include WinUI 3, Qt/PySide, or another justified native approach.  
Previously rejected/deferred paths stay rejected/deferred (Electron, Tauri, permanent Tk shell, CustomTkinter).

---

## E) Frontend migration constraints

1. Do not build the future shell by continuously expanding Tk Home into the final architecture.  
2. Keep Tk Home as a temporary compatibility frontend while the boundary is extracted.  
3. Keep `review-ui` as the production/evidence surface during migration.  
4. Keep `review.html` as an engineering/forensic artifact, not the end-user shell.  
5. Keep PySide6 spike as reference only; do not auto-promote to production.

---

## F) Canvas, video, and multimodal reconciliation

## F.1 Canvas is split into product vs renderer decisions

Product requirement (stable): interactive intelligence workspace for observations, selections, relationships, search context, and temporal evidence.

Implementation question (open): renderer/compositor choice for production shell.

Therefore: Canvas capability exists; current renderer is provisional.

## F.2 Video model

Do not treat video as "thousands of independent face rows."

Canonical model:

```text
video -> temporal observations -> tracks -> track/person hypotheses -> identity evidence
```

Current truth:

- S7a sampled video: shipped
- S7b derived tracks: shipped slice
- real-motion tracking quality: pending
- webcam/RTSP quality evidence: pending hardware

## F.3 Optional modalities

OCR / CLIP / pose / objects are observation modalities and retrieval evidence, not identity replacements.

Identity firewall remains:

> optional modalities must never silently change face identity decisions.

---

## G) Performance reconciliation (measurement-first)

Performance track is independent from APP-1 delivery, but evidence-gated.

## G.1 PERF-1 measurement baseline

Measure:

- decode, detect, embedding, clustering, DB, memory, UI overhead
- files/s, faces/s, images/s
- CPU, RAM, latency

## G.2 PERF-2 concurrency experiment (headless first)

Evaluate workers=1/2/4/... and report end-to-end throughput impact before changing defaults.

## G.3 PERF-3 provider experiment

Measure CPU vs available accelerated providers and record actual EP/device used.

## G.4 PERF-4 native ARM64

Unblock OpenCV load path and collect native ARM64 measurements.  
Do not alter historical S1 settings to manufacture comparisons.

## G.5 PERF-5 optimization implementation

Rust / DB redesign / deeper rewrites are justified only by measured bottlenecks.

---

## H) Scale gate policy

The 10k target is a future scale gate, not a "mentioned once" aspiration.

| Dataset | Purpose |
|---|---|
| 90 | frozen identity baseline |
| 1k | routine functional regression |
| 5k | medium-scale behavior |
| 10k | architecture/throughput gate |
| larger | optional stress |

Track at each size:

- ingest time
- memory footprint
- DB growth
- query latency
- identity retrieval behavior
- clustering time
- UI responsiveness
- cancel/resume
- failure recovery

---

## I) Deferred / blocked / parked disposition

## I.1 Do now

1. APP-1 boundary from current `main`
2. selective salvage from prior APP-1 drafts
3. concrete `paused` semantics
4. Review usability during ingest
5. real Windows live-ingest gate
6. merge only after gate pass
7. single authoritative architecture documentation (this file)

## I.2 Immediately after APP-1

- R2 IPC probe
- formalize app boundary contract
- native frontend architecture evaluation
- R3 shell decision from architecture + evidence

## I.3 Parallel experimental track

- native ARM64 perf investigation
- multi-worker headless benchmark
- provider benchmark
- 1k/5k/10k scale testing
- webcam/RTSP real-hardware tests when available

## I.4 Parked (unchanged)

- Rust rewrite as strategy
- vector DB
- SQLite multi-writer
- permanent Tk AppShell
- Electron / Tauri
- CustomTkinter
- WinUI selected only for "speed" without architecture evidence
- InsightFace replacement
- identity threshold reopening
- buffalo_l rebundling

---

## J) Reconciled sequence

```text
CURRENT MAIN
  -> FACE-001..005 CLOSED
  -> APP-1 / R1 JobEngine boundary
       -> Windows live gate + contract tests
       -> merge gate
  -> R2 IPC probe
  -> Native frontend architecture evaluation
  -> R3 shell decision
  -> Native production shell
  -> unified Home/Review/Canvas experiences
  -> video/live UX expansion
  -> multimodal retrieval expansion
  -> scale/performance hardening
```

Parallel evidence track:

```text
PERF: ARM64 + workers + provider + scale
  -> measured bottlenecks
  -> targeted optimization only
```

---

## K) Governance and document precedence

1. This file is the only architecture/roadmap authority.
2. `docs/ARCHITECTURE.md` and `docs/ROADMAP-RECONCILE.md` are pointers only.
3. `docs/SEMBLON_MATURITY_BLUEPRINT.md` remains historical maturity evidence, not a forward queue.
4. FACE gate docs remain closed validation evidence, not active work tickets.
5. Draft architecture text is not implementation evidence by itself.

---

## L) Changelog

| Version | Date | Summary |
|---|---|---|
| V1.4 | 2026-09-21 | Reconciled roadmap authority: FACE closed; APP-1 first; Windows live gate; IPC as boundary test; measurement-first performance track; single planning source. |
