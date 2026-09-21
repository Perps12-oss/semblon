# R3 §8.7 — Shell decision packet (evidence → winner)

**Status:** OPEN — no winner named.  
**Authority:** `docs/SEM-ARCH-V1.4.md` §D.2 / §I.5 / §J · visual contract `docs/R3-BRIEF.md`.  
**Human naming of winner:** **DEFERRED TO LAST** (SEM-ARCH §I.5). Development of shell chrome continues without a named toolkit.  
**When naming (last):** Artifacts 1–3 canonical + frames walked · Artifact 4 bake-off **measured** for each candidate · hierarchy frames walked (TEST) · six-of-six PASS.  
**Not:** polishing Tk Home · inventing schema · preferring a toolkit without six-of-six PASS · inventing a PASS from dry-run.

## Decision question

> Which frontend architecture should own the production application shell, given the APP-1 JobEngine boundary and measured workloads?

Candidates under consideration: **WinUI 3**, **Qt/PySide**, or another justified native approach.  
Still rejected: Electron, Tauri, permanent Tk AppShell, CustomTkinter.

## Evidence inputs (fill after human bake-off)

| Input | Path / note | Present? |
|---|---|---|
| Artifact 1 — state matrix (17) | `docs/r3-artifacts/01-state-matrix.md` | yes (canonical) |
| Artifact 2 — state triple | `docs/r3-artifacts/02-state-triple.md` | yes (canonical) |
| Artifact 3 — collision ledger | `docs/r3-artifacts/03-collision-ledger.md` | yes (canonical) |
| Artifact 4 — bake-off criteria | `docs/r3-artifacts/05-bake-off-checklist.md` | criteria yes; **measures DEFERRED TO LAST** |
| Related — identity × processing | `docs/r3-artifacts/02-interaction-cross-product.md` | yes (kept) |
| Collision frames (15) | `docs/r3-artifacts/03-collision-frames.html` | yes |
| State-triple grid (30) | `docs/r3-artifacts/04-state-triple-grid.html` | yes |
| Hierarchy frames (TEST) | `docs/r3-artifacts/06-hierarchy-frames.html` | yes |
| Bake-off JSON | `tools/r3-bakeoff/results/bakeoff-*.json` | human-run |
| R2 IPC probe | `semblon lab ipc-probe` (boundary only) | yes on `main` |
| APP-1 C.3 Windows live gate | owner machine proof | **DEFERRED TO LAST** (SEM-ARCH §I.5) — not a stop-work |

## Candidate scorecard (one row per toolkit measured)

| Toolkit | Machine | Operator | Date | C1 | C2 | C3 | C4 | C5 | C6 | Overall |
|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | |
| | | | | | | | | | | |

Overall = **PASS only if C1–C6 are all PASS**. Partial scores do not name a winner.

## Architecture fit (non-visual)

Record after bake-off PASS for a candidate:

| Concern | Evidence / notes |
|---|---|
| Talks to JobEngine via APP-1 Application API (UI does not own ingest) | |
| Can host Library / People / Work + Canvas without second Home app | |
| Ruled out / Ignore stay distinct (CONTRACTS shape already named) | |
| Identity firewall: overlays never auto-assign `person_id` | |
| R2 probe ops remain reachable (or successor IPC) without Tk owning the loop | |

## Decision record (blank until evidence)

| Field | Value |
|---|---|
| Winner | _none yet_ |
| Date | |
| Operator | |
| Linked bake-off JSON | |
| Linked checklist ticks | |
| Explicit refusals still held | Electron · Tauri · permanent Tk AppShell · CustomTkinter · WinUI-for-speed-alone |
| Next engineering slice | Native production shell against this winner + R3 brief |

## Explicitly deferred here

- Implementing the shell  
- Claiming a winner from dry-run / pending_human bake-off JSON  
- Reopening identity thresholds or inventing DDL from this packet  
