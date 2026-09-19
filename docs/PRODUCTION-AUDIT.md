# Semblon — Final production audit

**Date:** 2026-09-19  
**Tree:** `main` at `8403292` (production commit on top of PR #36 `27a94b2`)  
**Version:** 1.3.0  
**Portable tests this session:** 157 collected; **154 passed**, **3 skipped**, 0 xfail.

Identity contract was **not** reopened. Human verification is **not** a ship gate for the defined boundary.

Authority order: `docs/PRODUCT.md` → `docs/CONTRACTS.md` → `docs/SEM-ARCH.md`. Status snapshot: `docs/PRODUCTION-STATUS.md`. This file is the freeze-audit record.

---

## 1. Plan contradictions

| Documents originally said | Implementation | Authoritative now | Intentional? | Docs follow-up |
|---|---|---|---|---|
| PRODUCT frozen: “No GUI required” | Home + `review-ui` ship | PRODUCT amendment Level 2: GUI is KEEP, not v1-required | Yes | AGENTS still says “No GUI required” without citing the amendment |
| PRODUCT v1 **out**: video files | S7a sampled ingest + S7b derived tracks | Amendment: out of frozen v1, **in KEEP** as holdout | Yes | PRODUCT.md already states this |
| PRODUCT v1 **out**: “watchdog” (folder watcher) | `semblon/watchdog.py` stall detector | Stall watchdog is new; folder watcher still out | Yes, **name collision** | AGENTS “Forbidden: watchdog” still reads as a ban on the stall module |
| SEM-ARCH-001 “drawing-board PR does not open that slice” | CONTRACTS primitives exist | Table: COMPLETE (docs) | Yes | SEM-ARCH §16 leftover “when opened” language |
| Earlier status: stall watchdog COMPLETE in-product | Class + unit test; **not wired** into Home/`process` | Code is source of truth | Overclaim | Recorded as PARTIAL below |
| Earlier status: FaceKitProvider COMPLETE in-pipeline | `ingest` still calls `load_app()`; provider fills `runtime_json` | Code is source of truth | Thin/partial | Recorded as PARTIAL below |

---

## 2. Requirement matrix

| Requirement | Source | Implementation | Tests/evidence | Status | Human? |
|---|---|---|---|---|---|
| Stills folder ingest | PRODUCT | `semblon/ingest.py` | `tests/test_negative.py`, `tests/test_progress.py`, `tests/test_face005.py` | COMPLETE | NO |
| Detect → filter → embed → cluster | PRODUCT | engine + `eps=0.40` | `tests/test_cluster.py`, `tests/test_frozen_params.py` | COMPLETE | NO |
| Persons only after `name` | PRODUCT | `semblon/review.py` | `tests/test_review.py`, `tests/test_negative.py` | COMPLETE | NO |
| Identify vs persons, no auto-assign | FACE-005 | `semblon/identify.py` | `test_identify_does_not_auto_assign_person` | COMPLETE | NO |
| Unknown valid | PRODUCT | inbox UNKNOWN | `test_identify_unknown_*` | COMPLETE | NO |
| HTML contact sheet | PRODUCT | `semblon/export.py` | export tests | COMPLETE | NO |
| Files stay put | PRODUCT | originals not moved | export-views tests | COMPLETE | NO |
| ~10k library | PRODUCT | design target | `tools/bench_ingest.py` `verified=false` | NOT EXECUTED | YES |
| ARM64/x64 native first-class | PRODUCT | `process_arch` / `process_execution` | `test_process_arch_x64_on_arm64_is_emulated` | ENVIRONMENT-LIMITED | YES |
| buffalo_l internal eval | PRODUCT / licenses | `lab models` `redistributable: false` | `test_facekit_provider_is_cpu_only` | UNAVAILABLE to redistribute | YES legal |
| No folder watcher | PRODUCT v1 out | none | — | DEFERRED | NO |
| No webcam / ACC / public lookup | PRODUCT v1 out | none | — | DEFERRED | NO |
| Home / process / review-ui | Amendment L2 | `home_ui.py`, `review_ui.py` | board/API tests; no Tk widget tests | COMPLETE (GUI gap) | YES visual |
| People / Unknown / Activity / Settings | Amendment / master | messagebox dialogs | none for dialogs | PARTIAL | YES visual |
| Cooperative cancel | CONTRACTS | Home + SIGINT at file boundaries | `test_ingest_cancel`, `test_process_cancel` | COMPLETE | YES live Ctrl+C |
| Backup / restore | CONTRACTS | `lab backup` / `lab restore` | `test_backup_restore_*` | COMPLETE | NO |
| Integrity | CONTRACTS | `lab integrity` | `test_integrity_and_interrupted_stamp` | COMPLETE | NO |
| Search lookup | CONTRACTS | `semblon/search.py` | `test_search_person_not_cluster` | COMPLETE | NO |
| FaceKit CPU provider | SEM-ARCH-002 | class + `runtime_json` fields | unit | PARTIAL (`load()` unused in ingest) | NO |
| Stall watchdog | production push | `semblon/watchdog.py` | `test_watchdog_stall_vs_progress` | PARTIAL (not in Home/`process`) | NO |
| Progress kind `queued` | CONTRACTS | constant only | never emitted | PARTIAL | NO |
| S7a sampled video | KEEP | `temporal.py` | `tests/test_temporal.py` | COMPLETE | YES real video |
| S7b derived tracks | KEEP | `tracks.py` | `tests/test_tracks.py` synthetic | COMPLETE synthetic | YES real video |
| S6 memory | KEEP | `memory.py` | `tests/test_memory.py` | COMPLETE | NO |
| Portable CI | workflow | `.github/workflows/ci.yml` | file exists | IMPLEMENTED / NOT EXECUTED here | YES Actions |
| ARCH-001 docs | SEM-ARCH | CONTRACTS primitives | docs | COMPLETE (docs) | NO |
| ARCH-003…010 | SEM-ARCH | not built | — | DEFERRED | NO |
| Canvas / objects / CLIP | SEM-ARCH | none | — | DEFERRED | NO |
| Workers default >1 | PERF | default 1; `--workers` exists | `test_ingest_workers`; PERF-WORKERS slower | EXPERIMENTAL | NO |
| MSI + bundled weights | packaging | none | — | UNAVAILABLE | YES legal |
| Duplicate stills `imread` removed | PERF P2 | `embed_bgr(img0)` | unit ingest mocks | COMPLETE code / NOT EXECUTED live bench | NO |

---

## 3. Hidden omissions

| Finding | Where | Class |
|---|---|---|
| No `TODO` / `FIXME` / `NotImplementedError` in product `.py` | repo grep | none found |
| `except Exception: return False` on cancel callback | `semblon/ingest.py` | fail-safe cancel |
| `except Exception` on embed → file `failed` | `semblon/ingest.py` | honest fail; hides exception type |
| `emit()` swallows UI exceptions | `semblon/progress.py` | intentional |
| `except MemoryError: pass` after person search | `semblon/search.py` | silent skip of history attach |
| `search._open` uses RW `init_db` | `semblon/search.py` | inbox is RO; search is not |
| `unassigned_media` action handlers | `semblon/review_ui.py` | dead path; board emits tracks/unassigned |
| `FaceKitProvider.load()` never called | ingest uses `load_app` | unused architecture interface |
| `Watchdog` never constructed in product | only tests | unused on shipping path |
| `KIND_QUEUED` never emitted | `semblon/progress.py` | unused kind |
| `source_type='live'` in DDL | `semblon/store.py` | reserved, unused |
| `process_folder` cannot pass `--workers` | `semblon/process.py` | Home always workers=1 |
| Schema version `"1"`; no migrate | `semblon/store.py` | no upgrade path |
| Untracked `tools/_forensic_*` | working tree, **not in git** | local leftovers, not in release |
| `scikit-learn` extra unused | `pyproject.toml` | unused extra |
| InsightFace home `%USERPROFILE%\.insightface\...` | `weights_status` | documented environment assumption |

---

## 4. Failure modes

### Data

| Mode | Status |
|---|---|
| Duplicate ingestion | COMPLETE — sha256 skip |
| Partial writes | COMPLETE — per-file commit; cancel keeps partial |
| Interrupted / kill | COMPLETE — leftover `finished_at NULL` stamped interrupted; re-ingest skips hashes |
| Orphans | COMPLETE — `lab integrity` counts; no auto-repair |
| Schema migrate | NOT IMPLEMENTED |
| Missing originals | PARTIAL — thumbs/`file missing`; EXIF OSError; integrity does not walk disk |
| Inaccessible dirs / malformed media | PARTIAL — decode fail = failed; no ACL suite |
| Corruption | PARTIAL — FK + WAL + backup; no `PRAGMA integrity_check` CLI |

### Processing

| Mode | Status |
|---|---|
| Memory growth / CPU saturation | NOT EXECUTED |
| Worker deadlocks | NOT EXECUTED live; workers experimental and slower (`docs/PERF-WORKERS.md`) |
| Stalled inference | PARTIAL — `Watchdog` exists, not in product loop |
| Model / provider failure | PARTIAL — embed exception → failed file |
| Partial processing | COMPLETE — `KIND_PARTIAL` then `cancelled` |
| Retry | COMPLETE — skip-seen; failed decode retried next run |

### Identity

| Mode | Status |
|---|---|
| Accidental auto-assign | COMPLETE — identify does not stamp `faces.person_id` |
| False merges | COMPLETE policy (conservative eps); live dump HUMAN |
| Naming contamination | COMPLETE — naming isolation + merge rejects different persons |
| Merge/split | COMPLETE — `tests/test_review.py` |
| Stale identity | COMPLETE — recluster does not create persons |

### GUI

| Mode | Status |
|---|---|
| Empty states / missing media | COMPLETE (board/HTML tests) |
| Long jobs / cancel / errors | COMPLETE (Home Cancel; Failed status) |
| Restart / missing DB / invalid paths | PARTIAL — errors exist; Home not widget-tested |

### Video

| Mode | Status |
|---|---|
| Repeated observations / hash skip | COMPLETE unit |
| Fragmentation / crossing / occlusion / gaps | COMPLETE **synthetic** |
| Cuts / hundreds of observations / large unknown | NOT EXECUTED on real media |
| Track ≠ person | COMPLETE |

---

## 5. Security

A full security audit was **not** completed. Licence notes plus one CVE scan are not that.

| Check | Result |
|---|---|
| Dependency CVE scan | `pip-audit -r requirements.txt` → **No known vulnerabilities found** (exit 0). No lockfile. Optional `PySide6` extra not scanned. |
| Licence inventory | `docs/licenses.md` — notes, not legal sign-off |
| Model licence | buffalo_l not redistributable until a human decision |
| Path handling | `Path` + SQLite URI; glued `--out` rejected on `lab profile`; no traversal suite |
| Untrusted media | decode failures counted failed; no fuzzing |
| DB integrity | FK + WAL + `lab integrity` + backup |
| Secrets / API keys | none in product; no scanner run |
| `report` must not write the store | tested |

---

## 6. Performance

| Topic | Measured? | Result |
|---|---|---|
| Ingest throughput | Historical P0 | 221 stills, **1299.3 s**, ~5.9 s/file, x64/emulated — `docs/PERF-P0-BASELINE.md` |
| Workers | Historical harness | w=2 **0.86×**, w=4 **0.66×** vs w=1 — do not default >1 |
| Duplicate decode | Code change | **NOT EXECUTED** as a new live folder bench |
| `tools/bench_ingest.py` | Harness | `verified: false` unless `--folder` given — **NOT EXECUTED** |
| Memory | | Peak RSS not recorded |
| GPU / batching | | NOT IMPLEMENTED / blocked |
| 10k library | | NOT EXECUTED |

Do not treat P0 / workers tables as measurements of this freeze session.

---

## 7. Release

| Item | Implemented | Verified |
|---|---|---|
| Version 1.3.0 | YES | `import semblon` → 1.3.0 |
| Checkout install | YES `tools/install-windows.ps1` | Clean-machine NOT EXECUTED |
| Uninstall | NOT IMPLEMENTED | — |
| Schema migrate / upgrade | NOT IMPLEMENTED | — |
| User data | `%LOCALAPPDATA%\Semblon\store.sqlite` | default-path unit |
| Missing models | `lab models`; first ingest may download | download NOT EXECUTED |
| `semblon.cmd` | YES | HUMAN |
| MSI | UNAVAILABLE | — |
| CI workflow | YES | Actions run NOT EXECUTED in the audit environment |
| Interrupted-run recovery | YES | unit |

---

## 8. Tests

```text
collected 157
passed    154
skipped     3
xfail       0
```

Skipped (all `pytest.importorskip("PySide6")` in `tests/test_s8_toolkit_spike.py`):

- `test_shell_bridge_missing_store`
- `test_shell_bridge_loads_board_and_names`
- `test_shell_bridge_ignore_and_note`

Optional `.[gui]` extra; not Home/`review-ui`. Remain skipped in portable CI. Replacement: tk board/API tests.

Gaps (not skips): Home/Review widget automation; live InsightFace / owner dump / 10k / GPU / native ARM64 OpenCV; live Ctrl+C; GitHub Actions; `PRAGMA integrity_check`; permission-denied directories; Watchdog on the product path.

---

## 9. Deferred register

| Item | Source | Why deferred | Required for this freeze? |
|---|---|---|---|
| ARCH-003 envelope type | SEM-ARCH | `pack_id` is the identity key | No |
| ARCH-004 ObservationGroup | SEM-ARCH | `clusters` exist | No |
| ARCH-005 track table | SEM-ARCH | derived tracks KEEP | No |
| ARCH-006–007 links/events | SEM-ARCH | S6 derived | No |
| ARCH-008 Lens/vector search | SEM-ARCH | lookup CLI exists | No |
| ARCH-009 general index | SEM-ARCH | SQLite is the store | No |
| ARCH-010 Canvas | SEM-ARCH | `review-ui` ships | No |
| Objects / OCR / CLIP / MediaPipe | AGENTS forbidden | identity firewall | No |
| Folder watcher | PRODUCT v1 out | command ingest | No |
| Webcam / RTSP | PRODUCT v2+ | | No |
| Identify / inbox dedicated UI | KEEP leftover | CLI + Home dialog | No |
| Default workers>1 / GPU | PERF P1 | measured slower / blocked | No |
| MSI + buffalo_l | licence | | No for a code freeze |

---

## 10. Human TODO (not engineering blockers)

| Item | Why human | Action | Release impact |
|---|---|---|---|
| buffalo_l redistribution | Legal | Keep internal-eval or obtain pack licence | Required before a **public binary with weights** |
| Clean-machine `install-windows.ps1` | Fresh profile | `docs/PACKAGING.md` | Required before a **non-dev** release |
| GitHub Actions green | External CI | Actions tab on `main` | Recommended |
| Visual Home / review-ui | Eyes | People / Unknown / Cancel | Recommended |
| Live Ctrl+C | OS signals | `process` then `lab integrity` | Recommended |
| Owner dump / 10k / real video | Dataset | `tools/bench_ingest.py --folder …` | Optional until those claims |
| ARM64 OpenCV / x64 native | Hardware | P1 / other PC | Recommended, not a v1 identity block |

`HUMAN VERIFICATION REQUIRED` is not `ENGINEERING INCOMPLETE`.

---

## 11. Freeze question

If we freeze the current release boundary today, is there remaining engineering that should reasonably prevent shipping that boundary?

**NO RELEASE-CRITICAL ENGINEERING ITEMS IDENTIFIED.**

---

## COMPLETE

- Identity loop: ingest → conservative cluster → review name/merge/split → identify vs persons
- Unknown valid; cluster id is never person id; identify does not auto-assign
- FACE-002→005 index; S1 golden frozen (`eps=0.40`)
- Incremental sha256 ingest; inbox (RO open)
- `process` / `home` / `review-ui` / `review.html`; empty-run line; file-missing thumbs
- Cancel (GUI + SIGINT at file boundary); cancelled ≠ completed; partial retained
- Backup/restore; integrity (orphans + unfinished); interrupted-run stamp
- Named-person `search`; S6 memory; S7a sampled video; S7b derived tracks (synthetic)
- Single-decode stills path; CPU recorded in `runtime_json`
- Portable pytest: **154 passed**
- CI workflow file; install script; licence inventory; packaging doc
- `pip-audit -r requirements.txt`: no known CVEs

## PARTIAL

- `FaceKitProvider`: metadata only; ingest still `load_app()`
- Stall `Watchdog`: unit-tested, not wired to Home/`process`
- `KIND_QUEUED` defined, never emitted
- Home People/Unknown/Activity/Settings = dialogs, not full pages
- `search` opens the store RW (`init_db`)
- Integrity does not scan missing original files
- Video quality: synthetic only
- `process` cannot set ingest workers
- Dead `unassigned_media` handlers in `review_ui.py`

## DEFERRED

- ARCH-003…010 implementation
- Intelligence Canvas, vector/Lens search, objects/OCR/CLIP/MediaPipe
- Folder watcher, webcam/RTSP, live `source_type`
- Identify/inbox dedicated UI
- Product-default workers>1, GPU EP, batching
- Schema migration; uninstall/upgrade installer

## SKIPPED

- 3 tests: PySide6 S8 toolkit spike. Remain skipped in portable CI.

## NOT EXECUTED

- `tools/bench_ingest.py` on a real folder
- New P0 timing after duplicate-imread removal
- GitHub Actions run in the audit environment
- Clean-machine install
- Live Ctrl+C
- Owner-dump / confirmatory re-score / 10k
- GPU / native ARM64 OpenCV load
- Secrets scanner; `PRAGMA integrity_check`
- Home/Review widget automation

## ENVIRONMENT-LIMITED

- ARM64 OpenCV ingest (`opencv_geometry500.dll` hang); S1 path remains x64 `cv2` = emulated
- x64 native FACE-000 (no x64 PC)
- Real-camera tracking / long video
- Signal-handler behaviour beyond unit cancel callback

## UNAVAILABLE

- Redistribution of buffalo_l / frozen exe+weights / MSI
- Legal licence sign-off
- Claim of “fully production verified” on hardware/scale

## HUMAN VERIFICATION REQUIRED

- Legal pack licence
- Clean-machine smoke
- CI on GitHub
- Visual GUI
- Live Ctrl+C
- Optional: dump, 10k, P1 OpenCV, real video

## RELEASE-CRITICAL ENGINEERING REMAINING

None for the frozen identity + KEEP CLI/Home/`review-ui` boundary.

## DOCUMENTATION CHANGES REQUIRED

Recorded here. `docs/PRODUCTION-STATUS.md` should match this file on watchdog and FaceKitProvider (PARTIAL, not COMPLETE in-product).

## RECOMMENDED POST-RELEASE WORK

1. Wire `Watchdog` into Home status, or stop calling it in-product COMPLETE
2. Use `FaceKitProvider.load()` in ingest, or stop calling ARCH-002 pipeline-complete
3. Remove or never-hit `unassigned_media` handlers
4. `lab integrity` + `PRAGMA integrity_check` / missing-path count
5. Confirm GitHub Actions on `main`
6. After P1: native ARM64 measure — then reconsider workers
7. ARCH-003 docs when earned

---

## Addendum — after freeze (`c07220e` and later)

The freeze snapshot above is **historical** (`main@8403292`, version 1.3.0). Do not treat PARTIAL FaceKit/Watchdog or DEFERRED ARCH-003…010 in this file as current product status.

Current status: `docs/PRODUCTION-STATUS.md`.

Verified on later `main` (portable pytest; no InsightFace download):

- `FaceKitProvider.load()` is the ingest load path (`semblon/ingest.py` `load_app`)
- Home constructs `Watchdog` and can show `stalled` without killing the job; Home emits `queued`
- Schema v2 tables are written from clusters, FaceKit faces, and S6 memory (`confirmed=0`)
- `watch` / `live` / `canvas` / `search --similar` exist; extras do not vote on identity
- Optional OCR/CLIP/pose observers persist items when asked; missing libraries are unavailable/error items


## FINAL ENGINEERING VERDICT

- **Engineering completeness (defined boundary):** complete enough to freeze. Core loop, identity firewall, cancel honesty, persistence, and portable tests hold.
- **Verification completeness:** portable unit/integration yes; live InsightFace, GUI pixels, clean-machine, CI, scale, native ARM64 no.
- **Public-release limitations:** code may ship to a developer/internal user; **weights must not be redistributed**; MSI is unavailable; do not claim 10k or native ARM64.
- **Future development:** SEM-ARCH after ARCH-002 remains the plan; it is not a gate on this freeze.

Not “fully production verified.”  
Not “blocked” by remaining human checks.
