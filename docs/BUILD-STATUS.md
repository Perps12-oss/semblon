# Semblon build status — completion programme tracker

**Authority:** this file is the single completion tracker for the 12-issue programme.  
**Architecture ledger:** `docs/COMPLETION-MATRIX.md` (closed migration / capability ledger).  
**Product contract:** `docs/PRODUCT.md` (vision fixed; this file does not amend it).  
**Do not** treat `docs/ROADMAP.md` as a second status SoT.

| Field | Value |
|---|---|
| Evidence date | 2026-10-16 (programme execution) |
| Branch | `grok/product-truth` |
| HEAD | `079d88ba` — *Close the ship-audit holes that change identity or drop the library.* |
| Working tree at baseline | Dirty docs/`AGENTS.md`; untracked pytest-tmp / `.venv-312` preserved |
| CI lead (not re-run here yet) | GHA `38902434196` failed: `scipy==1.18.1` unsatisfiable on Python 3.11; Ubuntu 3.12 shell-frontend failures |

## Status vocabulary

| Status | Meaning |
|---|---|
| NOT STARTED | No verified implementation |
| IN PROGRESS | Work exists; acceptance unmet |
| BLOCKED | Named external decision, dependency, or environment prevents completion |
| IMPLEMENTED | Code/config exists; verification incomplete |
| VERIFIED | All defined acceptance criteria pass with recorded evidence |
| DEFERRED | Explicit documented product decision excludes the item from this release |

Code presence, a written plan, or an unre-run unit test does **not** establish VERIFIED.

## Gates

| Gate | Meaning | Status |
|---|---|---|
| A — Core product | E2E visual-memory journey, archive continuity, context where metadata permits | IN PROGRESS |
| B — Engineering baseline | Supported CI, lock, identity path explicit, retired surfaces, honest safety/privacy claims | IN PROGRESS |
| C — Release | Offline clean install + intended assets + **signed** installer | BLOCKED (cert + redistribution) |

## Twelve-item programme

| ID | Priority | Status | Dependencies | Locations | Acceptance (summary) | Evidence / remaining |
|---|---|---|---|---|---|---|
| 01 Windows crash / Python matrix | P0 | IN PROGRESS | Support policy before pins | `.github/workflows/ci.yml`, `pyproject.toml`, `requirements.txt`, `semblon/engine.py`, `tools/assert_one_opencv.py` | Advertised supported Pythons pass Windows tests; AV fixed or evidence-based exclusion | CI install broken on 3.11 (`scipy==1.18.1`). Dual-OpenCV guard present. Win 3.14 AV not freshly dumped |
| 02 Encrypted store | P2 | DEFERRED | Design only | `docs/THREAT-MODEL.md` | Tested encryption **or** explicit deferral with threat/WAL/migration design | Store is plaintext. Deferred for this release after design expansion. No live DB experiments |
| 03 Signed offline MSI | P1 | IMPLEMENTED (eng) / BLOCKED (sign) | Lock (05); cert for Gate C | `packaging/msi/`, `tools/msi/`, `docs/PACKAGING.md` | Offline install works; signing verified **or** signing BLOCKED | Engineering present. Unsigned repro ≠ signed release. Cert unavailable → signing BLOCKED |
| 04 Identity engine / pack | P0 | IMPLEMENTED (local) / BLOCKED (redistribute) | Licence | `semblon/engine.py`, `docs/licenses.md` | Documented engine; offline ingest; hash pin; no silent download; redistribute only if legal | `pack-accept` + no-download. buffalo_l redistribution UNAVAILABLE. Local pack ≠ redistributable |
| 05 Hashed dependency lock | P1 | NOT STARTED | Python support policy | `requirements*.txt`, `pyproject.toml` | Hash-verified lock installs; CI detects drift | Exact pins exist; no `--hash=` lock yet |
| 06 FaceKit owner workflow | P1 | IMPLEMENTED / BLOCKED (run) | Accepted pack on runner | `.github/workflows/facekit-owner.yml` | Workflow passes with recorded env **or** BLOCKED with prerequisites | Workflow exists; stock GHA has no pack |
| 07 Retired Tk / review.html / spike | P1 | IMPLEMENTED / hygiene IN PROGRESS | None | CLI, `review_chrome/`, `tools/s8_toolkit_spike/`, docs | No retired UI as production; dead refs cleaned; shell tests pass | CLI is `shell` only. Empty `semblon/review_chrome/`. Doc drift. s8 research kept |
| 08 Screen-capture privacy | P1 | DEFERRED (product UI) | Scope decision | `semblon/privacy.py`, lab capture | Accurate limits; exclusions if product feature; else defer | Title-prefix is not a security boundary. Product UI deferred; lab retained |
| 09 Visual-memory search | P0 | IN PROGRESS | Continuity helpful | `region_search.py`, `search.py`, Focus QML | E2E shell journey; unicode paths; honest mode label; regressions | Default match is colour histogram. Region uses `cv2.imread` (unicode gap) |
| 10 Archive continuity | P0 | IMPLEMENTED | None | `ingest._remember_path`, duplicates, integrity | Fresh move/rename/dup/missing evidence; no filename-only merge | Tests exist; **not VERIFIED until re-run on HEAD** |
| 11 Contextual discovery | P1 | IN PROGRESS | Search hits (09) | Time lens, Shell.qml | Hit → day/neighbours; honest missing metadata | Time browse exists; search→context not wired |
| 12 Unified experience + docs | P0/P1 | IN PROGRESS | 09–11 | Shell Primary/Advanced, PRODUCT/UI docs | Coherent journey; consistent terms; tracker matches repo | Shell Primary/Advanced present; docs still contradict in places |

## Python support policy

**Status:** pending evidence inventory (do not edit pins until recorded below).

Target advertised range today: `requires-python = ">=3.11,<3.15"` with CI matrix 3.11–3.14. Known conflict: `scipy==1.18.1` requires Python ≥3.12. Policy and markers will be filled in Phase 2 before pin changes.

## Dual verdict (updated at programme end)

| Verdict | Value | Notes |
|---|---|---|
| Product and engineering completion | NOT COMPLETE | Gates A/B unmet at baseline |
| Release readiness | NOT READY | Gate C blocked (signing + redistribution) |

## Verification log

Commands, environments, and results are appended here as they are executed. Distiguish **run** vs **not run**.

### Baseline (2026-10-16)

- Git: `grok/product-truth` @ `079d88ba`
- Prior CI: `gh run view 38902434196` — failure (scipy on 3.11; Ubuntu shell errors). Not a fresh local suite pass.
- Pytest: not re-run for this baseline document rewrite.

## Capability notes (non-authoritative detail)

Useful source-read detail from the earlier inventory (status vocabulary above supersedes any `INTEGRATED` wording):

- Default Similar / region match is colour histogram, not semantic / face identity.
- `openFocus` stills only (`source_type=folder`); video playback DEFERRED.
- Pack gate: `assert_face_pack_ready` / `semblon lab pack-accept`; MSI asserts no weights.
- ARM64 OpenCV load remains BLOCKED per `docs/PERF-P1-ARM64.md` (not Gate C signing, but platform note).

## What this file will not absorb

Architecture migration status stays in `docs/COMPLETION-MATRIX.md`. Closed FACE gates stay in `docs/FACE-GATES.md`. Product vision stays in `docs/PRODUCT.md`.
