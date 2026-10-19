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
| 5 | Trust and release | **IN PROGRESS** / Gate C **BLOCKED** | YuNet+SFace runtime landed (buffalo_l retired from deps). Still need: L PASS or permanent BYO ship stance, Q Semblon eval, native ARM64, GHA green, Authenticode cert, lockfile refresh without insightface. |
| 6 | Face → archive discovery | **IN PROGRESS** (slices A–E code; Q/L ops open) | A–E: face similar, review handoff, person→Time, unified results, OCR→Field, NanoDet BYO. Plan: `docs/decisions/2026-10-16-yunet-sface-discovery-plan.md`. Q calibration + MSI weight L PASS remain external. |
| 7 | Multi-leg local retrieval — detect + OCR → parallel recall → RRF → lightweight rerank | **NOT STARTED** | Plan: `docs/decisions/2026-10-19-lens-style-retrieval.md`. Does not reopen milestone 2. Does not swap DINOv2, add Chroma/FAISS as a product dependency, or touch identity. |

## Pass verdict

Milestones **1–3 are COMPLETE** for the acceptance criteria that can be evidenced in this environment (offscreen production shell + unit tests).  
Milestone **7** is planned quality work on the same “look into a picture” act. It does not reopen milestone 2.  
The overall product is **NOT COMPLETE** until Gates B and C close. See BUILD-STATUS dual verdict.

## Rule

A completed slice updates BUILD-STATUS with behaviour, test, command, and result. It does not edit PRODUCT.md unless the intended experience itself changed via `docs/decisions/`.
