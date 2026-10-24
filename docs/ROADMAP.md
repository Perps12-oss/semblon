# Semblon delivery roadmap

**Product contract:** [`docs/PRODUCT.md`](PRODUCT.md) (frozen).  
**Evidence and statuses:** [`docs/BUILD-STATUS.md`](BUILD-STATUS.md) is the single status tracker.  
**Architecture:** [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) stays closed.

This file lists the product-completion sequence. It does not redefine the vision.

## Milestones

| # | Outcome | Status | Evidence in BUILD-STATUS |
|---|---|---|---|
| 1 | Enter the archive — empty state, grid, Focus, missing original, moved path | **VERIFIED** | Issue 10 + Gate A journey (Unicode folder, missing Focus, ingest rename reconnect). |
| 2 | Look into a picture — point, understand, find across the archive, show where the match sits | **VERIFIED** on the photographic set | `docs/evidence/photo-region-eval.json`. Four photographs. Viewpoint and lighting both rank above the same-colour distractor. Match box meets the paste. |
| 3 | Recover the context — Similar hit → day + surrounding photos | **VERIFIED** | Issue 11. Same-day neighbours in Field; other days excluded; missing-date honest. |
| 4 | Keep a discovery | **VERIFIED** | Kept finds sit beside the library in `{store}.discoveries.json`. No new table. |
| 5 | Trust and release | Gate B **GREEN on this commit**. Gate C **not PASS** | Commit `558cbb212bfacd27dc63ce27637ca0a97124e784`. Both `ci / test` jobs succeeded. Not a merge to `main`. Signed MSI smoke has not been run. BYO weights stay the ship stance. |
| 6 | Face → archive discovery | Slices A–E **landed**. Q/L/I/P **not PASS** | A–E are in the build. Those four gates are not marked passed. `docs/SHIP-GATES.md`. |
| 7 | Multi-leg local retrieval | Synthetic rank bar **CLOSED / PASS 5/5**. Precision **not PASS** | `docs/evidence/lens-retrieval-eval.json` lines 2, 6, 65, 319, 326. Kind door SKIPPED. `ann_justified` false. ANN is out of ship. |

## Pass verdict

Milestones **1–4 are COMPLETE** on the evidence already in BUILD-STATUS.  
Milestone **7** synthetic rank bar is **PASS 5/5** (`docs/evidence/lens-retrieval-eval.json`). Precision is null. It does not reopen milestone 2. ANN is out of ship.  
Gate B is **green on commit `558cbb2`** and is not a merge to `main`.  
The product is **NOT COMPLETE** and **NOT READY** for release. Gate C signed MSI smoke has not been run.

## Rule

A completed slice updates BUILD-STATUS with behaviour, test, command, and result. It does not edit PRODUCT.md unless the intended experience itself changed via `docs/decisions/`.
