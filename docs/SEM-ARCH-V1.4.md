# SEM-ARCH V1.4 — Engineering planned work

**Status:** engineering planned-work source. It is not the product contract. Production shell baseline: `docs/ARCHITECTURE.md` (**COMPLETE** 2026-10-05).  
**Date:** 2026-09-21. Shell baseline recorded 2026-10-05. Product-truth split recorded 2026-10-16.

Product completion outcomes live in `docs/ROADMAP.md`. Current capability evidence lives in `docs/BUILD-STATUS.md`. This file does not redefine `docs/PRODUCT.md`.

- `docs/PRODUCT.md` is the product contract.
- `docs/CONTRACTS.md` remains schema / CLI / runtime authority.
- `docs/FACE-GATES.md` remains the closed FACE-002→005 validation index.

No second product contract and no second architecture north star.

---

## A) Reconciled baseline (new truth)

> FACE-001→FACE-005 are closed.  
> The identity engine is shipped/gated and is no longer the primary architecture risk.  
> Semblon is transitioning from an identity-engine project to a local-first image intelligence application.

This reconciliation **does not** reopen FACE gates, retune identity thresholds, or restart old handover queues.

### Production architecture baseline (2026-10-05) — COMPLETE

The architecture migration is closed. The canonical statement is `docs/ARCHITECTURE.md`. It is repeated here so this file cannot be read as still choosing Tk Home.

```text
                    PySide6
                       │
                       ▼
                 Application
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
      Archive         Jobs       Lens / Search
        │              │              │
        └──────────────┼──────────────┘
                       ▼
                Domain / Storage
                       │
                 Providers / ML
```

Constraints:

- PySide6 is the production UI. New production UI work belongs there.
- `Application` is the only application boundary. UI clients do not open storage themselves.
- Media lookup crosses `Application`. Decoding may stay in the UI.
- NumPy arrays are not `Application` or `JobEngine` command parameters.
- One `JobEngine`, owned by `Application`. `semblon process` is synchronous headless ingest, not a second engine.
- One Lens door: `Application.query_media` → `lens.query_image`.
- One Region Similar operation: `remember_and_find_region` → `region_search.remember_and_find`.
- `review.html` and `review_chrome` are retired. No production Review page replaces them. Board operations stay in `review_board` / `review.py`.
- Tk Home and Tk review-ui are temporary legacy clients, not a second architecture.
- `tools/s8_toolkit_spike` and Live overlay are research or secondary. They do not define production architecture.
- Do not resurrect `lens_home`, `native_shell/window.py`, `review.html`, or a parallel store path.

Schema, identity thresholds, and Lens behavior were not changed by this migration.

The next work is product construction on that foundation: Field + Focus, archive first, then Find, People, Decision, Appearance, and Time as lenses on the same session. Not another shell migration.

### Status picture as reconciled 2026-09-21 (historical)

The table below is the September reconciliation. Where it names Tk Home as the production GUI, that line is historical.

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
| Home | **SHIPPED — production GUI shell** (Library \| Workspace/Canvas \| Inspector); one shipping GUI per **#54**; wired **#63–#66**; UNWIRED claims closed **#65** |
| Review UI | **SHIPPED** (KEEP vertical with Home) |
| Native application shell | **N/A as mapped open item** — production shell is Tk Home (#54/#65). Optional Qt `semblon shell` (#67) is KEEP optional, not a second product Home |
| APP-1 JobEngine boundary | **MERGED** (`main`) · **CLOSED** (C.2+C.3) |
| APP-1 C.2 paused / unpause | **COMPLETE** |
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

## C) APP-1 boundary (closed)

APP-1 is closed. The notes below are the extraction record. They are not an open merge gate and they do not keep Tk as the production UI. Current seam: `docs/ARCHITECTURE.md`.

## C.1 APP-1 / R1 (closed)

APP-1 was not a "make Tk Home nicer" project.  
APP-1 extracted a stable application/job boundary.

Historical target seam (the "Tk now; other later" line is not current):

```text
UI / Frontend (Tk now; PySide/WinUI/other later)
            |
      Application API
            |
         JobEngine
            |
     Existing ingest engine
```

Critical rule (still true):

> UI observes and commands jobs.  
> UI does not own long-running computation.

### APP-1 branch policy

- Start clean from current `main`.
- Do not merge historical APP-1 drafts wholesale.
- Prior drafts (for example #48 / #50) are reference material only; selectively recover validated pieces.

## C.2 `paused` contract — **COMPLETE**

Job states:

```text
idle -> running -> paused -> running -> completed
running -> cancelling -> cancelled
paused -> cancelling -> cancelled
running/paused -> failed
```

(`queued` is a `ProgressEvent` kind for UI status, not `JobEngine.state`.)

V1 paused semantics:

> `paused` means resumable and not currently consuming ingest processing resources.

**Implementation:** `JobEngine.pause` / `unpause` / `state` / `paused` and `Application.pause_job` / `unpause_job` / `cancel_job`. The ingest gate blocks in `JobEngine._gate` (passed as `cancel=` into `process_folder`). Home Pause/Resume and `semblon shell` use the same door.  

**Granularity (honest):** cooperative **between files** and at the same stage polls where cancel already runs. Mid-decode / mid-embed pause is **not** claimed.

Windows live proof of pause/unpause was part of the C.3 gate; **C.3 is CLOSED / DONE** (owner). Completion matrix: `docs/COMPLETION-MATRIX.md`.

## C.3 APP-1 Windows live gate (human) — **VERIFIED ON WINDOWS** · **CLOSED**

**Owner declaration 2026-09-21:** gate **CLOSED and DONE** for roadmap (§I.5).  
**Owner live evidence 2026-09-22:** **VERIFIED ON WINDOWS** — see `docs/COMPLETION-MATRIX.md` (pytest 20 passed; `semblon home` live ingest with Pause/Resume control states + Canvas during ingest).  
APP-1 is **CLOSED**. Do not reopen as a stop-work.

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
R3 does **not** start by polishing Tk Home. **Native shell chrome against Artifacts 1–4 was the authorized engineering path. Superseded 2026-10-05:** that path is complete (`docs/ARCHITECTURE.md`). Next work is product construction, not more shell chrome.

Durable **Ruled out** vs Ignore/`reject`: named slice `docs/CONTRACTS-RULED-OUT.md`. **Product-wire ship claim CLOSED / DONE** by owner 2026-09-21 (§I.5). Do not invent new columns from the brief alone.

---

## E) Frontend migration constraints (historical — closed 2026-10-05)

These constraints governed the migration. They are not current instructions.

**Closed:** PySide6 `semblon shell` is the production UI. `review.html` is retired, not kept. `review-ui` is a legacy client, not the production surface. `tools/s8_toolkit_spike` stays research and was not promoted into a second product shell. Do not resume this list.

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

Interactive retrieval structure (landed): decompose the highlight, then parallel recall over DINOv2 `region_patch`, optional SigLIP same-kind, BM25 over stored OCR, and object class; Reciprocal Rank Fusion; feature rerank; refinement query spec. Labelled eval harness scores highlight / relevant / hard-neg tuples (`semblon/lens_eval.py`); precision stays refused without `--eval-set confirmatory`. Optional async VLM judge and ANN stay off. Plan: `docs/decisions/2026-10-19-lens-style-retrieval.md`. Vector DB, Chroma, and a required FAISS product index stay parked.

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

1. ~~APP-1 boundary / C.2 pause / C.3 Windows~~ **CLOSED**
2. ~~Production GUI shell~~ **COMPLETE** — PySide6 (`docs/ARCHITECTURE.md`, 2026-10-05). The September Tk Home completion (#54) is historical and superseded.
3. **PERF ARM64 OpenCV** — unblock / probe / measure (do not silent-swap S1)
4. **Multi-worker / scale** — harden hash workers; keep default=1 until measured
5. **MSI code packaging** (no buffalo_l); weights remain UNAVAILABLE legally
6. Keep `docs/COMPLETION-MATRIX.md` authoritative for current status

## I.2 Immediately after APP-1 (code track)

- ~~R2 IPC probe~~ **DONE**
- ~~Artifact 4 / §8.7 / C.3 / Ruled-out ship claim~~ **CLOSED / DONE** (owner §I.5) · Ruled-out chrome **WIRED** (#65)
- ~~Production GUI shell~~ **COMPLETE** (September record was Tk Home; superseded 2026-10-05 by PySide6)
- ~~Optional Qt `semblon shell` KEEP optional (#67)~~ **Superseded 2026-10-05.** `semblon shell` is the production UI. Do not restore Tk as the product door.

## I.3 Parallel experimental track

- native ARM64 perf investigation — **OpenCV load still BLOCKED** (`docs/PERF-P1-ARM64.md`); in-repo PE/timed probes shipped 2026-09-22; no fake speedup; no VERIFIED ON WINDOWS without owner evidence
- multi-worker ingest — engineering COMPLETE (hash workers + cancel/pause + harness `default_gate`); product default **workers=1** until owner Windows PASS (`docs/PERF-WORKERS-HARNESS.md`)
- provider benchmark — EP listing harness (`docs/PERF-PROVIDER-HARNESS.md`); listed ≠ smoke-tested; Azure ≠ GPU
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

**Owner declaration 2026-09-21:** the following gates are **CLOSED and DONE**. They are no longer blockers, deferrals, or stop-work. Native production shell work against Artifacts 1–4 was **authorized** and is **complete** as of 2026-10-05 (`docs/ARCHITECTURE.md`). It is not an open ticket.

Still forbidden: inventing DDL, skipping the identity firewall, or picking Electron / Tauri / permanent Tk AppShell / CustomTkinter.

| Human gate | Where named | Status |
|---|---|---|
| APP-1 C.3 Windows live ingest gate | §C.3 | **VERIFIED ON WINDOWS** (2026-09-22) · prior CLOSED / DONE (§I.5) |
| Toolkit bake-off §8.5 / Artifact 4 | §D.2 · `05-bake-off-checklist.md` | **CLOSED / DONE** |
| Named shell decision §8.7 | `07-shell-decision.md` | **CLOSED / DONE** — native shell authorized |
| CONTRACTS durable **Ruled out** product wire | `CONTRACTS-RULED-OUT.md` | **CLOSED / DONE** |
| Other owner human-verify rows | `docs/GATES.md` · SEM-ARCH §I.5 | **CLOSED / DONE** for ship-gate purposes |

---

## J) Reconciled sequence

```text
CURRENT MAIN
  -> FACE-001..005 CLOSED
  -> APP-1 / R1 JobEngine boundary on main
  -> APP-1 C.3 Windows live gate VERIFIED ON WINDOWS (2026-09-22) · APP-1 CLOSED
  -> R2 IPC probe (loopback) DONE — `semblon lab ipc-probe`
  -> R3 Artifacts 1–4 CANONICAL (`docs/r3-artifacts/`)
  -> Feature gates WIRED 2026-09-21 (`docs/GATES.md`)
  -> Artifact 4 bake-off + §8.7 shell decision CLOSED / DONE (owner)
  -> Ruled out product-wire claim CLOSED / DONE (owner)
  -> Production GUI shell COMPLETE (September: Tk Home #54 · #63–#66 · #65) — historical
  -> Optional Qt `semblon shell` KEEP (#67) — historical; not the 2026-10-05 decision
  -> ARCHITECTURE MIGRATION COMPLETE 2026-10-05 (PySide6 → Application; review.html retired; Tk legacy only)
  -> NEXT: product construction (Field + Focus). Not another shell.
  -> Still open as engineering, not architecture: PERF ARM64 · workers default · MSI (no weights) — see COMPLETION-MATRIX
  -> video/live UX expansion
  -> multimodal retrieval expansion — interactive path + eval harness landed: `docs/decisions/2026-10-19-lens-style-retrieval.md`
     (decompose highlight → DINOv2 + optional SigLIP + BM25 → RRF → rerank → refine spec;
      labelled ranks, no precision without confirmatory).
     Keep DINOv2 `region_patch`. No Chroma. No vector DB. No identity writes.
     No VLM on the blocking first grid. ANN not started.
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

1. `docs/PRODUCT.md` is the product contract. `docs/BUILD-STATUS.md` is the evidence-backed build. `docs/ROADMAP.md` is the product-completion sequence. None of them reopens the shell.
2. `docs/ARCHITECTURE.md` is the production architecture baseline (**COMPLETE** 2026-10-05). It closes the shell. It does not replace the product contract, the schema, or this file's gate record.
3. This file remains the engineering planned-work and gate authority. It is not permission to reopen the shell, restore Tk Home, or resurrect `review.html`.
4. `docs/COMPLETION-MATRIX.md` is the architecture closed-vs-open ledger, not the product capability matrix.
5. `docs/CONTRACTS.md` remains schema and runtime authority.
6. FACE gate docs remain closed validation evidence, not active work tickets.
7. Where an older section of this file names Tk Home as the production GUI, calls Qt optional, or tells you to keep `review.html`, the 2026-10-05 baseline wins.

Do not resurrect Tk Home as the product door, `review.html`, `review_chrome`, `lens_home`, `native_shell/window.py`, or a parallel application/storage path. The production architecture is PySide6 → Application.

---

## L) Changelog

| Version | Date | Summary |
|---|---|---|
| V1.4.15 | 2026-10-19 | Lens eval harness: labelled highlight / relevant / hard-neg tuples; synthetic ranks only; precision refused without confirmatory. ANN still parked. |
| V1.4.14 | 2026-10-19 | Multimodal retrieval expansion points at the Lens-style ranking plan (`docs/decisions/2026-10-19-lens-style-retrieval.md`): language door, highlight decomposition, rerank, refinement spec. Vector DB stays parked. |
| V1.4.13 | 2026-10-16 | Product contract, build status, and product roadmap are separate documents. This file stays engineering planned work. |
| V1.4.12 | 2026-10-05 | Production shell baseline closed: PySide6 → Application. `review.html` retired. Tk legacy only. Precedence points at `docs/ARCHITECTURE.md` for the shell. |
| V1.4.11 | 2026-09-22 | Retire superseded parallel docs (historical SEM-ARCH / maturity / audit / verify playbook); COMPLETION-MATRIX is status authority. |
| V1.4.9 | 2026-09-22 | APP-1 C.3 **VERIFIED ON WINDOWS** (owner live evidence); APP-1 **CLOSED**; next = deepen native shell. |
| V1.4.8 | 2026-09-22 | APP-1 C.2 COMPLETE (`Application` pause/unpause); completion matrix; native shell slice 1 (`semblon shell`); next = deepen shell. |
| V1.4.7 | 2026-09-21 | Plan-gaps productization on `main`: status table Home sidebar + CanvasWorkspace + GPU PRODUCTIZED + optional observers (`product_prefer_gpu` / `resolve_product_observers`). |
| V1.4.6 | 2026-09-21 | Owner closed APP-1 C.3, bake-off/§8.7, Ruled-out ship claim as **CLOSED / DONE** (§I.5). Native production shell authorized next. |
| V1.4.5 | 2026-09-21 | Fuller R3 Artifact 1–4 pack landed (`01-state-matrix`, `02-state-triple`, `03-collision-ledger`, `05-bake-off-checklist` criteria); abbreviated brief §3 seed superseded. Bake-off measures / §8.7 winner still §I.5 last. |
| V1.4.4 | 2026-09-21 | Human verification (APP-1 C.3, bake-off, §8.7 winner, Ruled-out ship wire, other human gates) **DEFERRED TO LAST**; development must continue (§I.5). |
| V1.4.3 | 2026-09-21 | R3 §8.7 shell decision packet OPEN; `lab r3-bakeoff` wires harness; R2 already on main. |
| V1.4.2 | 2026-09-21 | R2 IPC probe: loopback JSON-lines `semblon/ipc_probe.py` + `lab ipc-probe`. Boundary proof only; not product IPC. |
| V1.4 | 2026-09-21 | Reconciled roadmap authority: FACE closed; APP-1 first; Windows live gate; IPC as boundary test; measurement-first performance track; single planning source. |
| V1.4.1 | 2026-09-21 | Point R3 at approved `docs/R3-BRIEF.md` v2; frames before toolkit bake-off; Ruled out flagged as CONTRACTS gap. |
| V1.4.2 | 2026-09-21 | R3 §8.1–§8.4 artifacts DONE under `docs/r3-artifacts/`; sequence next = toolkit bake-off (human-run checklist; no measurements claimed). |
