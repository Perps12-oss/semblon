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
| 5 | Trust and release | Gate B **GREEN on this commit**. Gate C **not PASS** | Commit `558cbb212bfacd27dc63ce27637ca0a97124e784`. Both `ci / test` jobs succeeded. On `main` via merge `db6d9ad` (PR #184, 20:13 Europe/London). Not a release. Signed MSI smoke has not been run. BYO weights stay the ship stance. |
| 6 | Face → archive discovery | Slices A–E **landed**. Q/L/I/P **not PASS** | A–E are in the build. Those four gates are not marked passed. `docs/SHIP-GATES.md`. |
| 7 | Multi-leg local retrieval | Synthetic rank bar **CLOSED / PASS 5/5**. Precision **not PASS** | `docs/evidence/lens-retrieval-eval.json` lines 2, 6, 65, 319, 326. Kind door SKIPPED. `ann_justified` false. ANN is out of ship. |

## Next engineering slice — category check lifecycle (landed, suite incomplete)

The category job now stays on its own door through pause, cancel and resume:

- Discover shows Pause, Stop and Continue check. Continue restarts that category. It does not call folder ingest.
- A category stop no longer arms the folder Resume path.
- Discover names a missing reader, a photo that could not be read, a check that failed, and a missing original separately.
- People search can say how many photos were checked and that unnamed faces are still waiting. It still does not create a person.
- Region search still says when only the whole-picture pass exists. That does not write `tier_done_mask`.

Targeted tests for this slice, including the earlier coverage tests: `python3 -m pytest -q --noconftest tests/test_category_backfill.py tests/test_schema.py tests/test_scan_tiers.py tests/test_discover_categories.py tests/test_observers.py tests/test_production.py` → **66 passed**. The full suite has not been run.

## Earlier slice — say what has been checked (landed, suite incomplete)

Category backfill can finish without the shared observe tier, so search and Discover now read `category_coverage` directly:

- Opening Discover shows a line for People, Objects, Regions and Words. It does not start a scan. A missing object pack says so and says nothing was downloaded.
- Text and object search keep their previous wording when a library has never been tracked. After a partial category check, a miss says how many photos were checked and that the rest were not.
- Region search treats a regions frame/detail row as coverage. It still does not stamp `tier_done_mask`.

Targeted tests for this slice are in `tests/test_category_backfill.py` and `tests/test_discover_categories.py`. The full suite has not been run here.

## Earlier slice — category-specific scan/backfill (landed, suite incomplete)

The Discover category chooser is a presentation/routing change. Targeted full-library backfill now has its own job, separate from broad `reprocess=True` ingest:

- People: face analysis only, retaining the identity firewall and human-only naming.
- Objects: NanoDet labels only when the BYO pack is ready; contour regions must not be presented as object classes.
- Regions: DINOv2 whole-frame/patch indexing and coverage, without rerunning People, Objects, or OCR.
- Words in photos: OCR only, with missing provider, failed read, empty read and completed read distinguished.

Each job covers existing archive media, reports category-specific progress and coverage, supports cooperative pause/cancel/resume through `JobEngine`, and skips coverage that is still valid for the same file and provider version. See `docs/decisions/2026-10-27-category-backfill.md`. Targeted tests passed (34). The full suite has not been run in the environment that landed this slice.

## Pass verdict

Milestones **1–4 are COMPLETE** on the evidence already in BUILD-STATUS.  
Milestone **7** synthetic rank bar is **PASS 5/5** (`docs/evidence/lens-retrieval-eval.json`). Precision is null. It does not reopen milestone 2. ANN is out of ship.  
Gate B is **green on commit `558cbb2`**, which is on `main` via PR #184. That merge is not a release.  
The product is **NOT COMPLETE** and **NOT READY** for release. Gate C signed MSI smoke has not been run.

## Rule

A completed slice updates BUILD-STATUS with behaviour, test, command, and result. It does not edit PRODUCT.md unless the intended experience itself changed via `docs/decisions/`.
