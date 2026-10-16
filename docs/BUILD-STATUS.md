# Semblon build status — completion programme tracker

**Authority:** this file is the single completion tracker for the 12-issue programme.  
**Architecture ledger:** `docs/COMPLETION-MATRIX.md` (closed migration / capability ledger).  
**Product contract:** `docs/PRODUCT.md` (vision fixed; this file does not amend it).  
**Roadmap sequence:** `docs/ROADMAP.md` (milestones only; not a second status SoT).

| Field | Value |
|---|---|
| Evidence date | 2026-10-16 (Gate A completion pass) |
| Branch | `grok/product-truth` |
| Parent HEAD | `f9e495bc` — *Advance the completion programme…* |
| Working tree at evidence | Changes for this pass committed with this document update |

## Status vocabulary

| Status | Meaning |
|---|---|
| NOT STARTED | No verified implementation |
| IN PROGRESS | Work exists; acceptance unmet |
| BLOCKED | Named external decision, dependency, or environment prevents completion |
| IMPLEMENTED | Code/config exists; verification incomplete |
| VERIFIED | All defined acceptance criteria pass with recorded evidence |
| DEFERRED | Explicit documented product decision excludes the item from this release |

## Gates

| Gate | Meaning | Status |
|---|---|---|
| A — Core product | Archive continuity, Similar honesty, context where metadata permits | **VERIFIED** (offscreen production shell + unit). Visible desktop `SEMBLON_VISIBLE_SHELL=1` not required for these acceptance criteria; optional residual. |
| B — Engineering baseline | Supported CI, lock, identity path, honest safety/privacy | **IN PROGRESS** — lock + pins present; GHA matrix green not evidenced from this agent |
| C — Release | Offline clean install + intended assets + **signed** installer | **BLOCKED** — no WiX here; no Authenticode cert; buffalo_l redistribution UNAVAILABLE |

## Dual verdict

| Verdict | Value |
|---|---|
| **1. Product and engineering completion** | **NOT COMPLETE** — Gate A done; Gate B still open (CI evidence); Gate C blocked |
| **2. Release readiness** | **NOT READY** — Gate C blocked |
| **3. This roadmap pass (milestones 1–3)** | **COMPLETE** — acceptance evidenced below |

Deferred without blocking unrelated work: **02** encryption, **08** product capture UI, milestone **4** albums.

## Twelve-item programme

| ID | Priority | Status | Evidence / remaining |
|---|---|---|---|
| 01 Win crash / Python matrix | P0 | IN PROGRESS | SciPy markers + policy. 3.14 shell still risky when stacking shells. **CI green not evidenced this run.** |
| 02 Encrypted store | P2 | DEFERRED | Decision recorded. |
| 03 Signed offline MSI | P1 | IMPLEMENTED (eng) / BLOCKED (sign+WiX) | Lock/wheelhouse exist. No WiX/cert here. |
| 04 Identity engine / pack | P0 | IMPLEMENTED (local) / BLOCKED (redistribute) | Pack refuse path. Licence UNAVAILABLE. |
| 05 Hashed dependency lock | P1 | IMPLEMENTED | `requirements.lock.txt` present. Not VERIFIED until CI lock + clean install. |
| 06 FaceKit owner workflow | P1 | IMPLEMENTED / BLOCKED (run) | No owner pack here. |
| 07 Retired Tk / review.html / spike | P1 | IMPLEMENTED | Unchanged. |
| 08 Screen-capture privacy | P1 | DEFERRED | Decision unchanged. |
| 09 Visual-memory search | P0 | **VERIFIED** (honesty + Unicode + firewall) | Colour-histogram labels end-to-end; Unicode folder region Similar; whole-image note; face modality refused by design. **Not** a semantic-search quality claim. |
| 10 Archive continuity | P0 | **VERIFIED** | Missing Focus notice; ingest rename reconnect; copy/basename safety; Gate A journey on Unicode folder. |
| 11 Contextual discovery | P1 | **VERIFIED** | `openFocusInContext` day scope includes same-day neighbours and excludes other days; missing-date honest. |
| 12 Unified experience + docs | P0/P1 | **VERIFIED** (milestones 1–3) | Gate A journey + ROADMAP sync. Milestones 4–5 / Gates B–C remain. |

## Behaviour landed this completion pass

1. Missing original Focus (`focusFileMissing`, QML note, primary-safe copy).
2. Honest colour-histogram Similar labels (search, region, presentation allowlist).
3. Context without inventing a date; day scope neighbours from archive Field.
4. Gate A journey test: Unicode ingest → Similar note → day neighbours → missing → rename reconnect.

## Verification log (commands actually run)

Environment: Windows ARM64 host; x64 Python 3.12 (`.venv-312`).

| Command | Result |
|---|---|
| `pytest -q` ship_audit + region_search + near_duplicates + integrity + Gate A Focus/Similar/context + drawn-region + `test_windows_journey_…` `--basetemp=.pytest-tmp-complete1` | **37 passed** |
| `pytest -q tests/test_native_shell.py::test_gate_a_archive_similar_and_context_journey` | **1 passed** (also included above) |
| Full CI matrix / FaceKit owner / WiX / signed MSI / `SEMBLON_VISIBLE_SHELL=1` | **not run** |
| Live user database | **not modified** |

### Tests covering Gate A

| Test | Covers |
|---|---|
| `test_gate_a_archive_similar_and_context_journey` | Unicode folder, histogram Similar, day neighbours, missing, rename reconnect |
| `test_open_focus_reports_missing_original` | Missing path Focus |
| `test_open_focus_in_context_without_day_stays_honest` | No invented date |
| `test_open_focus_in_context_scopes_day_when_mtime_exists` | Day scope |
| `test_ingest_updates_path_when_original_moved` | Ingest reconnect |
| `test_region_similar_unicode_path_finds_colour_match` | Unicode region Similar |
| `test_whole_image_similar_basis_says_colour_histogram` | Whole-image basis |
| `test_windows_journey_launch_ingest_browse_search_theme_restart_recover` | Empty→ingest→browse shell |

## Capability notes

- Default Similar is colour histogram (`appearance/rgb8@1`), not semantic / face identity.
- Pack gate unchanged. ARM64 OpenCV load remains BLOCKED historically (`docs/PERF-P1-ARM64.md`).

## Outstanding blockers (exact)

1. GHA CI matrix green after SciPy markers (Gate B).
2. Clean 3.14 Windows shell confirmation or evidence-based exclusion (Gate B).
3. Owner FaceKit pack run (issue 06).
4. buffalo_l redistribution licence (Gate C).
5. WiX + Authenticode certificate (Gate C).

## What this file will not absorb

Architecture migration status stays in `docs/COMPLETION-MATRIX.md`. Closed FACE gates stay in `docs/FACE-GATES.md`. Product vision stays in `docs/PRODUCT.md`.
