# Semblon delivery roadmap

**Product contract:** [`docs/PRODUCT.md`](PRODUCT.md) (frozen).  
**Evidence and statuses:** [`docs/BUILD-STATUS.md`](BUILD-STATUS.md) is the single status tracker.  
**Architecture:** [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) stays closed.

This file lists the product-completion sequence. It does not redefine the vision.

## Milestones

| # | Outcome | Status (2026-10-16) | Evidence in BUILD-STATUS |
|---|---|---|---|
| 1 | Enter the archive — empty state, grid, Focus, missing original, moved path | **VERIFIED** | Issue 10 + Gate A journey (Unicode folder, missing Focus, ingest rename reconnect). |
| 2 | Look into a picture — point, understand, find across the archive, show where the match sits | **VERIFIED** on the photographic set | `docs/evidence/photo-region-eval.json`. Four photographs. Viewpoint and lighting both rank above the same-colour distractor. Match box meets the paste. |
| 3 | Recover the context — Similar hit → day + surrounding photos | **VERIFIED** | Issue 11. Same-day neighbours in Field; other days excluded; missing-date honest. |
| 4 | Keep a discovery | **VERIFIED** | Kept finds sit beside the library in `{store}.discoveries.json`. No new table. |
| 5 | Trust and release | **IN PROGRESS** / Gate C **BLOCKED** on the certificate | BYO weights are the ship stance (`docs/decisions/2026-10-16-identity-engine-redistribution.md`). Q, native ARM64, GHA green, and Authenticode are owner procedures in `docs/SHIP-GATES.md`. |
| 6 | Face → archive discovery | **IN PROGRESS** (slices A–E code; Q/L/P not PASS) | A–E landed. Q does not transfer S1 thresholds. L stays BYO until a licence letter. `docs/SHIP-GATES.md`. |
| 7 | Multi-leg local retrieval — decompose highlight, language door, RRF + rerank, refinement spec | **IMPLEMENTED**; synthetic rank bar **PASS** 5/5 | Pool-relative rerank, weights unchanged, precision refused. ANN and a heavy VLM are out of ship. `docs/decisions/2026-10-19-lens-style-retrieval.md`. |

## Pass verdict

Milestones **1–3 are COMPLETE** for the acceptance criteria that can be evidenced in this environment (offscreen production shell + unit tests).  
Milestone **7** is implemented on the interactive path. The synthetic rank bar is PASS 5/5. Precision stays refused. It does not reopen milestone 2. ANN is out of ship.  
The overall product is **NOT COMPLETE** until Gates B and C close. See BUILD-STATUS dual verdict and `docs/SHIP-GATES.md`.

## Rule

A completed slice updates BUILD-STATUS with behaviour, test, command, and result. It does not edit PRODUCT.md unless the intended experience itself changed via `docs/decisions/`.
