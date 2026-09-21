# R3 §8.7 — Shell decision packet (evidence → winner)

**Status:** **CLOSED / DONE** (owner declaration 2026-09-21).  
**Authority:** `docs/SEM-ARCH-V1.4.md` §D.2 / §I.5 / §J · visual contract `docs/R3-BRIEF.md`.  
**Outcome:** Native production shell is **authorized**. Look-and-feel follows Artifacts 1–4 + R3-BRIEF.  
**Not:** polishing Tk Home into permanent AppShell · inventing schema · Electron / Tauri / CustomTkinter / permanent Tk AppShell.

## Decision question

> Which frontend architecture should own the production application shell, given the APP-1 JobEngine boundary and measured workloads?

**Owner closed this gate 2026-09-21.** Implementation proceeds on a justified **native** approach (WinUI 3, Qt/PySide, or other native).  
Still rejected: Electron, Tauri, permanent Tk AppShell, CustomTkinter.

## Evidence inputs

| Input | Path / note | Present? |
|---|---|---|
| Artifact 1 — state matrix (17) | `docs/r3-artifacts/01-state-matrix.md` | yes (canonical) |
| Artifact 2 — state triple | `docs/r3-artifacts/02-state-triple.md` | yes (canonical) |
| Artifact 3 — collision ledger | `docs/r3-artifacts/03-collision-ledger.md` | yes (canonical) |
| Artifact 4 — bake-off criteria | `docs/r3-artifacts/05-bake-off-checklist.md` | yes — gate **CLOSED / DONE** (owner) |
| Related — identity × processing | `docs/r3-artifacts/02-interaction-cross-product.md` | yes (kept) |
| Collision frames (15) | `docs/r3-artifacts/03-collision-frames.html` | yes |
| State-triple grid (30) | `docs/r3-artifacts/04-state-triple-grid.html` | yes |
| Hierarchy frames (TEST) | `docs/r3-artifacts/06-hierarchy-frames.html` | yes |
| Bake-off JSON | `tools/r3-bakeoff/results/bakeoff-*.json` | optional regression; not required to proceed |
| R2 IPC probe | `semblon lab ipc-probe` (boundary only) | yes on `main` |
| APP-1 C.3 Windows live gate | owner declaration | **CLOSED / DONE** |

## Candidate scorecard

Owner closed Artifact 4 / §8.7 without requiring filled C1–C6 JSON rows to unblock shell work. Criteria remain for optional regression runs.

| Toolkit | Machine | Operator | Date | C1 | C2 | C3 | C4 | C5 | C6 | Overall |
|---|---|---|---|---|---|---|---|---|---|---|
| _(owner closed)_ | — | owner | 2026-09-21 | — | — | — | — | — | — | **CLOSED / DONE** |

## Architecture fit (non-visual)

| Concern | Evidence / notes |
|---|---|
| Talks to JobEngine via APP-1 Application API (UI does not own ingest) | Required of any shell implementation |
| Can host Library / People / Work + Canvas without second Home app | Required (R3-BRIEF §4 IA) |
| Ruled out / Ignore stay distinct | CONTRACTS-RULED-OUT ship claim **CLOSED / DONE** |
| Identity firewall: overlays never auto-assign `person_id` | FaceKit only |
| R2 probe ops remain reachable (or successor IPC) without Tk owning the loop | Boundary retained |

## Decision record

| Field | Value |
|---|---|
| Winner / authorization | **Native production shell authorized** (owner closed 2026-09-21). Implement with WinUI 3, Qt/PySide, or other justified native — refuse Electron/Tauri/permanent Tk AppShell/CustomTkinter. |
| Date | 2026-09-21 |
| Operator | owner |
| Linked bake-off JSON | not required (gate closed) |
| Linked checklist | `05-bake-off-checklist.md` criteria retained |
| Explicit refusals still held | Electron · Tauri · permanent Tk AppShell · CustomTkinter · WinUI-for-speed-alone |
| Next engineering slice | Native production shell against Artifacts 1–4 + R3 brief |

## Explicitly still refused

- Permanent Tk AppShell / expanding Tk Home into the final shell  
- Electron / Tauri / CustomTkinter  
- Inventing DDL or reopening identity thresholds from this packet  
