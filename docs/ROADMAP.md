# Semblon delivery roadmap

**Product contract:** [`docs/PRODUCT.md`](PRODUCT.md) (frozen).  
**Evidence and statuses:** [`docs/BUILD-STATUS.md`](BUILD-STATUS.md) is the single status tracker.  
**Architecture:** [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) stays closed.

This file lists the product-completion sequence. It does not redefine the vision.

## Milestones

| # | Outcome | Status (2026-10-16) | Evidence in BUILD-STATUS |
|---|---|---|---|
| 1 | Enter the archive — empty state, grid, Focus, missing original, moved path | **VERIFIED** | Issue 10 + Gate A journey (Unicode folder, missing Focus, ingest rename reconnect). |
| 2 | Find by appearance — whole-image and region Similar, honest labels, Unicode paths | **VERIFIED** (honesty / Unicode / firewall) | Issue 09. Colour histogram labeled; not a semantic quality claim. |
| 3 | Recover the context — Similar hit → day + surrounding photos | **VERIFIED** | Issue 11. Same-day neighbours in Field; other days excluded; missing-date honest. |
| 4 | Keep and organise discoveries | **DEFERRED** | No album schema (product decision). |
| 5 | Trust and release | **IN PROGRESS** / Gate C **BLOCKED** | YuNet+SFace runtime landed (buffalo_l retired from deps). Still need: L PASS or permanent BYO ship stance, Q Semblon eval, native ARM64, GHA green, Authenticode cert, lockfile refresh without insightface. |
| 6 | Face → archive discovery (plan) | **PLANNED** | Not a People dashboard. Order: face→similar photos → reviewable groups → person→context → unified results → later OCR/objects. Plan: `docs/decisions/2026-10-16-yunet-sface-discovery-plan.md`. |

## Pass verdict

Milestones **1–3 are COMPLETE** for the acceptance criteria that can be evidenced in this environment (offscreen production shell + unit tests).  
The overall product is **NOT COMPLETE** until Gates B and C close. See BUILD-STATUS dual verdict.

## Rule

A completed slice updates BUILD-STATUS with behaviour, test, command, and result. It does not edit PRODUCT.md unless the intended experience itself changed via `docs/decisions/`.
