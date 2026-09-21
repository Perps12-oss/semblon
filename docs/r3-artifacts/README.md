# R3 artifacts (§8.1–§8.4)

**Status:** COMPLETE for matrix + interaction cross-product + collision frames + state-triple grid  
**Authority:** `docs/R3-BRIEF.md` (visual/interaction). Roadmap: `docs/SEM-ARCH-V1.4.md`.  
**Date:** 2026-09-21  
**Not:** toolkit bake-off measurements (§8.5), clickable hierarchy (§8.6), schema columns, shell implementation.

Open the HTML frames in a browser. Spec docs are markdown. Reviewer hesitation on a collision pair = rule or rendering fails.

| # | Artifact | Path |
|---|---|---|
| 8.1 | Complete state matrix (17 components) | [01-state-matrix.md](01-state-matrix.md) |
| 8.2 | Identity × processing interaction spec | [02-interaction-cross-product.md](02-interaction-cross-product.md) |
| 8.3 | Collision ledger — 15 comparison frames | [03-collision-frames.html](03-collision-frames.html) |
| 8.4 | State-triple grid — 30 cards | [04-state-triple-grid.html](04-state-triple-grid.html) |
| 8.5 | Bake-off checklist (human-run; no results) | [05-bake-off-checklist.md](05-bake-off-checklist.md) |

Shared visual tokens (CSS): inlined in each HTML file from the brief’s grammar (notch + stroke texture; processing = shape, not hue).

## How to review

1. Read **01** — any shipped chrome state missing from the matrix is a bug.
2. Read **02** — illegal cells must not be painted as identity conclusions.
3. Open **03** — each pair side-by-side; if you hesitate, the pair fails. Footer must show pair count 15.
4. Open **04** — ingest × analysis are independent channels; identity notch cycles. Footer must show card count 30. Confusable pair = wrong channel assignment.
5. Use **05** only for real toolkit measurements on owner hardware — leave blanks until then.

## Explicitly deferred

- §8.5 Toolkit bake-off **measurements** against brief §6 (checklist exists; no PASS claimed)
- §8.6 Clickable hierarchy frames  
- CONTRACTS slice for durable **Ruled out** (called out; not invented here)
