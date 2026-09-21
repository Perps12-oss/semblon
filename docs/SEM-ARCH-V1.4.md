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
| Canvas | **EXISTS — Home-integrated Tk production overlay** (renderer still provisional vs native shell) |
| Search | **EXISTS** |
| Home | **SHIPPED — sidebar shell (Library \| Workspace/Canvas \| Inspector)**; R3 native shell still open |
| Review UI | **SHIPPED, legacy Tk surface** |
| Native application shell | **NOT decided/implemented** |
| APP-1 JobEngine boundary | **MERGED** (`main`) |
| APP-1 C.2 paused / unpause | **IMPLEMENTED** (code+unit tests; Windows live gate still required) |
| IPC boundary | **PROBE** (`semblon/ipc_probe.py` loopback JSON-lines; not product IPC) |
| Native ARM64 performance | **BLOCKED** |
| Multi-worker ingest | **EXPERIMENTAL / not default** |
| GPU | **PRODUCTIZED** — prefer when ORT lists CUDA/DirectML/TensorRT; else honest CPU; Azure ≠ GPU; listed ≠ smoke-tested |
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

Windows live proof of pause/unpause was part of the C.3 gate; **C.3 is CLOSED / DONE** (owner).

## C.3 APP-1 Windows live gate (human) — **CLOSED / DONE**

**Owner declaration 2026-09-21:** this gate is **CLOSED and DONE**. APP-1 is treated as production-proven for roadmap purposes.  
JobEngine remains on `main`. Do not reopen this gate as a stop-work. See §I.5.

Historical proof checklist (retained as evidence of what the gate covered):

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

---

## D) Immediate follow-up after APP-1

## D.1 R2 IPC probe (boundary test, not product shell)

R2 remains in-scope but is reframed as an architecture boundary proof:

```text
external/native client <-> IPC <-> JobEngine <-> existing engine
```

**Probe in tree:** `semblon/ipc_probe.py` + `semblon lab ipc-probe` — JSON-lines on `127.0.0.1` only. Ops: `ping`, `status`, `submit_ingest`, `cancel`, `pause`, `unpause`, `result`, `shutdown`, plus push `progress` / `done`. Tests: `tests/test_ipc_probe.py`. This is **not** the final IPC system (no named pipes, no WinUI host, no LAN bind).

Probe scope (satisfied by the loopback probe):

- start job
- status query
- progress stream
- cancel
- resume (`unpause` in-flight; `submit_ingest` with `resume=true` after cancel)
- result retrieval
- error handling

No need to implement the final IPC system in R2.

## D.2 R3 becomes frontend architecture decision

R3 question is not "WinUI or Qt?"

R3 question:

> Which frontend architecture should own the production application shell, given the APP-1 boundary and measured workloads?

Candidates can include WinUI 3, Qt/PySide, or another justified native approach.  
Previously rejected/deferred paths stay rejected/deferred (Electron, Tauri, permanent Tk shell, CustomTkinter).

**Visual / interaction contract (approved):** `docs/R3-BRIEF.md` (v2.4).  
Two-axis identity language (evidence × decision), five display states including **Ruled out**, state matrix + processing grammar, Library vs observation layer, toolkit bake-off against six measured criteria.  
**Artifacts 1–4 (canonical):** `docs/r3-artifacts/README.md` — fuller pack landed (`01-state-matrix.md`, `02-state-triple.md`, `03-collision-ledger.md`, `05-bake-off-checklist.md`). Abbreviated §3 seed in the brief is **superseded**. Related cross-product + HTML frames + hierarchy TEST + decision packet indexed there.  
**Artifact 4 / toolkit bake-off:** **CLOSED / DONE** by owner 2026-09-21 (§I.5) — native shell authorized. Criteria remain in `05-bake-off-checklist.md` for regression; JSON rows not required to proceed.  
**§8.7 shell decision:** **CLOSED / DONE** at `docs/r3-artifacts/07-shell-decision.md` — native production shell authorized (refusals held: Electron · Tauri · permanent Tk AppShell · CustomTkinter).  
R3 does **not** start by polishing Tk Home. **Native shell chrome against Artifacts 1–4 is the authorized next engineering path.**

Durable **Ruled out** vs Ignore/`reject`: named slice `docs/CONTRACTS-RULED-OUT.md`. **Product-wire ship claim CLOSED / DONE** by owner 2026-09-21 (§I.5). Do not invent new columns from the brief alone.

---

## E) Frontend migration constraints

1. Do not build the future shell by continuously expanding Tk Home into the final architecture.  
2. Keep Tk Home as a temporary compatibility frontend while the boundary is extracted.  
3. Keep `review-ui` as the production/evidence surface during migration.  
4. Keep `review.html` as an engineering/forensic artifact, not the end-user shell.  
5. Keep PySide6 / QML under `tools/s8_toolkit_spike` as reference only; do not auto-promote to production. There is no second product Home shell on `main`.  
6. Shell look-and-feel follows `docs/R3-BRIEF.md`; do not invent a parallel visual plan.

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

1. APP-1 boundary already on `main` — keep strengthening Application API / JobEngine clients
2. formalize app boundary contract (docs + tests)
3. **Native production shell** against Artifacts 1–4 + R3-BRIEF (Inspector verbs · state-triple media cards · IA)
4. unified Home/Review/Canvas toward the future shell **without** expanding Tk Home into permanent AppShell (§E)
5. single authoritative architecture documentation (this file)

## I.2 Immediately after APP-1 (code track)

- ~~R2 IPC probe~~ **DONE** (loopback probe in `semblon/ipc_probe.py`; not product IPC)
- ~~Artifact 4 / §8.7 / C.3 / Ruled-out ship claim~~ **CLOSED / DONE** (owner §I.5)
- Native production shell implementation (authorized)

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

## I.5 Human verification — **CLOSED / DONE** (canonical)

**Owner declaration 2026-09-21:** the following gates are **CLOSED and DONE**. They are no longer blockers, deferrals, or stop-work. Native production shell work against Artifacts 1–4 is **authorized**.

Still forbidden: inventing DDL, skipping the identity firewall, or picking Electron / Tauri / permanent Tk AppShell / CustomTkinter.

| Human gate | Where named | Status |
|---|---|---|
| APP-1 C.3 Windows live ingest gate | §C.3 | **CLOSED / DONE** |
| Toolkit bake-off §8.5 / Artifact 4 | §D.2 · `05-bake-off-checklist.md` | **CLOSED / DONE** |
| Named shell decision §8.7 | `07-shell-decision.md` | **CLOSED / DONE** — native shell authorized |
| CONTRACTS durable **Ruled out** product wire | `CONTRACTS-RULED-OUT.md` | **CLOSED / DONE** |
| Other owner human-verify rows | `HUMAN-VERIFY-THEN-WIRE.md` | **CLOSED / DONE** for ship-gate purposes |

---

## J) Reconciled sequence

```text
CURRENT MAIN
  -> FACE-001..005 CLOSED
  -> APP-1 / R1 JobEngine boundary on main
  -> APP-1 C.3 Windows live gate CLOSED / DONE (owner)
  -> R2 IPC probe (loopback) DONE — `semblon lab ipc-probe`
  -> R3 Artifacts 1–4 CANONICAL (`docs/r3-artifacts/`)
  -> Feature gates WIRED 2026-09-21 (`docs/GATES.md`)
  -> Artifact 4 bake-off + §8.7 shell decision CLOSED / DONE (owner)
  -> Ruled out product-wire claim CLOSED / DONE (owner)
  -> NEXT: Native production shell (R3-BRIEF + Artifacts 1–4 look-and-feel)
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
| V1.4.7 | 2026-09-21 | Plan-gaps productization on `main`: status table Home sidebar + CanvasWorkspace + GPU PRODUCTIZED + optional observers (`product_prefer_gpu` / `resolve_product_observers`). |
| V1.4.6 | 2026-09-21 | Owner closed APP-1 C.3, bake-off/§8.7, Ruled-out ship claim as **CLOSED / DONE** (§I.5). Native production shell authorized next. |
| V1.4.5 | 2026-09-21 | Fuller R3 Artifact 1–4 pack landed (`01-state-matrix`, `02-state-triple`, `03-collision-ledger`, `05-bake-off-checklist` criteria); abbreviated brief §3 seed superseded. Bake-off measures / §8.7 winner still §I.5 last. |
| V1.4.4 | 2026-09-21 | Human verification (APP-1 C.3, bake-off, §8.7 winner, Ruled-out ship wire, other human gates) **DEFERRED TO LAST**; development must continue (§I.5). |
| V1.4.3 | 2026-09-21 | R3 §8.7 shell decision packet OPEN; `lab r3-bakeoff` wires harness; R2 already on main. |
| V1.4.2 | 2026-09-21 | R2 IPC probe: loopback JSON-lines `semblon/ipc_probe.py` + `lab ipc-probe`. Boundary proof only; not product IPC. |
| V1.4 | 2026-09-21 | Reconciled roadmap authority: FACE closed; APP-1 first; Windows live gate; IPC as boundary test; measurement-first performance track; single planning source. |
| V1.4.1 | 2026-09-21 | Point R3 at approved `docs/R3-BRIEF.md` v2; frames before toolkit bake-off; Ruled out flagged as CONTRACTS gap. |
| V1.4.2 | 2026-09-21 | R3 §8.1–§8.4 artifacts DONE under `docs/r3-artifacts/`; sequence next = toolkit bake-off (human-run checklist; no measurements claimed). |
