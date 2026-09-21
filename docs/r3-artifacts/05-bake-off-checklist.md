# Artifact 4 — Toolkit bake-off (criteria)

**Status:** Criteria CANONICAL; gate **CLOSED / DONE** by owner 2026-09-21 (`SEM-ARCH-V1.4` §I.5). Native shell authorized.  
**Authority:** `docs/R3-BRIEF.md` §6 · this file.  
**Prerequisite:** Artifacts 1–3 under this folder are complete.  
**Not:** Electron / Tauri / permanent Tk AppShell / CustomTkinter; inventing schema; polishing Tk Home into final shell.

The WinUI/Qt question remains a compliance lens for implementation. Criteria below are retained for optional regression; owner closed the gate without requiring filled JSON rows to proceed.

| Favored on (hypothesis) | Toolkit |
|---|---|
| Criteria 3, 5, 6 | WinUI |
| Criteria 1, 2, 4 | Qt |

## Measurement harness (optional regression)

| Piece | Path |
|---|---|
| README | `tools/r3-bakeoff/README.md` |
| Orchestrator | `tools/r3-bakeoff/run_bakeoff.py` |
| PowerShell | `tools/r3-bakeoff/Invoke-Bakeoff.ps1` |
| Schema | `tools/r3-bakeoff/schema/results.schema.json` |
| Probes C1–C6 | `tools/r3-bakeoff/probes/` |
| Results | `tools/r3-bakeoff/results/bakeoff-*.json` |
| CLI | `python -m semblon lab r3-bakeoff --toolkit <WinUI3\|Qt\|dry-run>` |

Harness still never invents `pass` on its own; owner closed the **ship gate**.

## Candidates / outcome

| Toolkit | Machine | Date | Operator | Notes |
|---|---|---|---|---|
| _(gate closed)_ | — | 2026-09-21 | owner | **CLOSED / DONE** — native shell authorized |

Rejected (do not ship as production shell): Electron, Tauri, permanent Tk AppShell, CustomTkinter.

---

## Six criteria (pass threshold + test)

| # | Criterion | Pass threshold | Test |
|---|---|---|---|
| **1** | Accent suppression | OS accent does not appear in focus, selection, toggle, progress, or hover in any state of the 17-component matrix | Render the full matrix in both themes; sample every pixel; **zero** accent-value matches |
| **2** | Mica + opaque compositing | Content surface over Mica shows zero bleed at 100% opacity, at 4K, 150% DPI, all three Windows backdrop modes | Pixel-diff against a solid-color reference; **ΔE < 1.0** |
| **3** | Frame time, 4K/60 video scrub | 95th percentile frame **≤ 16.0 ms**, sustained 30s | Trace with GPUView; no frame **> 20 ms** |
| **4** | WCAG AA on custom controls | All text **≥ 4.5:1**; all non-text UI **≥ 3.0:1**; face-box halo **≥ 3.0:1** against sampled crop mean in **95%** of test images | Automated + 200-image manual sample |
| **5** | Virtualized grid at 10k items | 60 fps scroll, 95th percentile frame **≤ 16.0 ms**, memory **≤ 400 MB** | Synthetic dataset, sustained 60s scroll |
| **6** | Accessibility tree on custom surfaces | Face boxes, compare cells, and notches expose role, name, and state to UIA; screen reader traverses the Inspector in logical order | Narrator + NVDA, full task walkthrough |

## Disqualifiers (pass/fail, not scored)

| # | Disqualifier | Rule |
|---|---|---|
| **D1** | A11y failure | Criterion **6** fails → toolkit is **out**, regardless of C2–C5 |
| **D2** | Accent leak | Criterion **1** fails → toolkit is **out**, regardless of C2–C5 |

A bake-off without disqualifiers is theatre. Run **D1/D2 first**.

C2–C5 may be scored/weighted only after both disqualifiers PASS.

## Run record (leave blank until measured)

| Toolkit | C1 | C2 | C3 | C4 | C5 | C6 | D1 | D2 | Overall | Evidence path |
|---|---|---|---|---|---|---|---|---|---|---|
| | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | | |
| | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | [ ] | | |

Overall for a toolkit: **PASS only if** D1 PASS · D2 PASS · and C1–C6 all PASS. Partial scores do not name a winner.

## After gate close (§I.5 CLOSED / DONE)

1. Optional: record regression JSON under `tools/r3-bakeoff/results/`.  
2. §8.7 decision packet is **CLOSED / DONE** — native shell authorized.  
3. Ruled out product-wire claim is **CLOSED / DONE** — bake-off does not invent columns.

**Timing:** owner closed this gate 2026-09-21. Next = native production shell against Artifacts 1–4.

## What this locks under R3-BRIEF

1. **State matrix is the contract** (`01-state-matrix.md`) — shipped component state missing = bug.  
2. **State triple is the asset model** (`02-state-triple.md`) — asset without three channels = collapsed layers.  
3. **Collision ledger is the test plan** (`03-collision-ledger.md` + frames) — hesitation = fail.

## Related

- Hierarchy frames (TEST): `06-hierarchy-frames.html`
- Shell decision packet: `07-shell-decision.md`
- Interaction cross-product (identity × processing): `02-interaction-cross-product.md`
