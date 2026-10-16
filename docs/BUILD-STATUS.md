# Semblon build status — completion programme tracker

**Authority:** this file is the single completion tracker for the 12-issue programme.  
**Architecture ledger:** `docs/COMPLETION-MATRIX.md` (closed migration / capability ledger).  
**Product contract:** `docs/PRODUCT.md` (vision fixed; this file does not amend it).  
**Roadmap sequence:** `docs/ROADMAP.md` (milestones only; not a second status SoT).

| Field | Value |
|---|---|
| Evidence date | 2026-10-16 (discovery slices A–B) |
| Branch | `grok/yunet-sface-discovery-plan` |
| Parent HEAD | (see git log on branch) |
| Working tree at evidence | Slice B hypothesis UX + Focus→People handoff; pytest below |

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
| B — Engineering baseline | Supported CI, lock, identity path, honest safety/privacy | **IN PROGRESS** — clean 3.14 local evidence + CI aggregate job landed; **GHA matrix green not yet evidenced from this agent**; FaceKit owner pack run still outstanding |
| C — Release | Offline clean install + intended assets + **signed** installer | **BLOCKED** — WiX workflow exists (`msi-release`, unsigned unless secrets); no Authenticode cert provisioned here; buffalo_l redistribution **UNAVAILABLE** (BYO stance recorded) |

## Dual verdict

| Verdict | Value |
|---|---|
| **1. Product and engineering completion** | **NOT COMPLETE** — Gate A done; Gate B still open (needs GHA green + owner pack evidence); Gate C blocked |
| **2. Release readiness** | **NOT READY** — Gate C blocked |
| **3. This roadmap pass (milestones 1–3)** | **COMPLETE** — acceptance evidenced (prior Gate A pass) |

Deferred without blocking unrelated work: **02** encryption, **08** product capture UI, milestone **4** albums.

## Twelve-item programme

| ID | Priority | Status | Evidence / remaining |
|---|---|---|---|
| 01 Win crash / Python matrix | P0 | IN PROGRESS | SciPy markers + policy. Clean 3.14 venv: nonshell **31 passed**, shell Focus + Gate A journey **2 passed** after dropping `QtMultimedia` (Essentials). **CI matrix green not evidenced this run** — aggregate job `test` republishes required context. |
| 02 Encrypted store | P2 | DEFERRED | Decision recorded. |
| 03 Signed offline MSI | P1 | IMPLEMENTED (eng) / BLOCKED (cert) | `tools/msi/build-msi.ps1` + `.github/workflows/msi-release.yml` (WiX v4/v5 via `dotnet tool wix`). Signs only when `CODE_SIGNING_PFX_*` secrets set; unsigned upload is engineering-only. |
| 04 Identity engine / pack | P0 | **IMPLEMENTED** (YuNet+SFace runtime) / **BLOCKED** (L redistribute, Q Semblon eval, P native ARM64) | Production path `opencv/yunet_sface`; `insightface` removed from deps; buffalo_l not loaded. BYO pack + pin. Smoke: ingest→cluster→name→reembed on Lena (x64). Gates: L OPEN, Q OPEN (provisional eps=0.45), I partial (pipeline wired), P partial. `docs/IDENTITY-PACK.md`. PRODUCT.md FaceKit wording unchanged until product-approval decision. |
| 05 Hashed dependency lock | P1 | IMPLEMENTED | `requirements.lock.txt` present. Not VERIFIED until CI lock step + clean install evidence from GHA. |
| 06 FaceKit owner workflow | P1 | IMPLEMENTED / BLOCKED (run) | `tools/facekit_owner_evidence.py` + `.github/workflows/facekit-owner.yml` + `docs/FACEKIT-OWNER.md`. No owner pack on this machine — evidence JSON not PASS. |
| 07 Retired Tk / review.html / spike | P1 | IMPLEMENTED | Unchanged. |
| 08 Screen-capture privacy | P1 | DEFERRED | Decision unchanged. |
| 09 Visual-memory search | P0 | **VERIFIED** (honesty + Unicode + firewall) + slice A face path | Colour-histogram labels end-to-end; Unicode folder region Similar; whole-image note. Face→similar photos is a **separate** door (`search_similar_faces` / Focus face click) with face-embedding basis — not histogram rebrand. |
| 10 Archive continuity | P0 | **VERIFIED** | Missing Focus notice; ingest rename reconnect; copy/basename safety; Gate A journey on Unicode folder. |
| 11 Contextual discovery | P1 | **VERIFIED** | `openFocusInContext` day scope includes same-day neighbours and excludes other days; missing-date honest. |
| 12 Unified experience + docs | P0/P1 | **VERIFIED** (milestones 1–3) | Gate A journey + ROADMAP sync. Milestones 4–5 / Gates B–C remain. |

## Behaviour landed this blocker-resolution pass

1. CI: matrix job renamed `test-matrix`; aggregate job `name: test` with `if: always()` fails closed on matrix result.
2. Clean Python 3.14 venv evidence under `docs/evidence/clean-314-*` (nonshell + shell after Essentials QML fix).
3. Shell.qml: removed `import QtMultimedia` / MediaPlayer stubs so Essentials-only installs load.
4. FaceKit owner evidence helper + workflow_dispatch job (no download).
5. buffalo_l: explicit BYO / no redistribution decision (keep FaceKit; do not swap engines).
6. MSI release workflow: optional Authenticode via secrets; unsigned when absent.

## Verification log (commands actually run)

Environment: Windows ARM64 host; `.venv-312` for discovery slices.

| Command | Result |
|---|---|
| `pytest tests/test_similar_faces.py` + adapter honesty | **7 passed** (slice A) |
| `pytest tests/test_discovery_slice_b.py` + People desk tests | **7 passed** (`--basetemp=.pytest-tmp-slice-b`) |
| Live user database | **not modified** |

### Tests covering Gate A (unchanged)

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

## Behaviour landed — discovery slice A

1. Domain: `search_similar_faces(store, face_id)` — same-`pack_id` `compare()`, best score per other media, provisional threshold from `identity_config.DEFAULT_THRESHOLD`, no decisions / no `person_id` writes.
2. Shell: Focus face box click → `findSimilarFaces` → results strip with `Similar (face embedding): …` (engine `face-embed`). Whole-image / region Similar stay colour histogram.
3. CLI: `semblon search --similar-face FACE --store …` (lab/read-only).

## Behaviour landed — discovery slice B

1. People desk: board `band` plumbed; titles “Candidate group” / “Strong candidate group” / named; honesty note that groups ≠ persons; review counts include need-review / strong.
2. Focus: “Review this group” when selected face maps to a board subject → leaves Focus, opens People, selects that group. No auto-name.
3. Q thresholds unchanged (still provisional in `identity_config.py`).
4. Plan/ROADMAP: milestone 6 IN PROGRESS (A–B); C–E not started.

## Capability notes

- Default whole/region Similar is colour histogram (`appearance/rgb8@1`), not semantic / face identity.
- Focus face Similar is face embedding (same pack); not a name; not auto-assign.
- People desk groups are hypotheses until Name; Name remains the only person-create path.
- Pack gate unchanged. ARM64 OpenCV load remains BLOCKED historically (`docs/PERF-P1-ARM64.md`).
- Identity runtime is YuNet + SFace (`opencv/yunet_sface`); buffalo_l retired from deps (BYO historical only).

## Outstanding blockers (exact)

1. **GHA CI matrix green** (Gate B) — aggregate `test` job landed; remote green not evidenced here.
2. **FaceKit owner pack run** (issue 06) — helper/workflow ready; needs real pack → PASS evidence JSON.
3. **buffalo_l redistribution licence** (Gate C) — BYO decision recorded; commercial redistribute still UNAVAILABLE.
4. **Authenticode certificate** (Gate C) — signing path in `msi-release.yml`; secrets not provisioned.
5. WiX owner run on a machine with WiX + (optional) cert — workflow exists; not executed here.

## What this file will not absorb

Architecture migration status stays in `docs/COMPLETION-MATRIX.md`. Closed FACE gates stay in `docs/FACE-GATES.md`. Product vision stays in `docs/PRODUCT.md`.
