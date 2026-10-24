# Semblon completion matrix (architecture closed / open)

**Readiness verdict (2026-10-22):** **NOT READY FOR RELEASE.** Evidence and the repair ledger are `docs/audits/PRODUCTION-READINESS-AUDIT.md` and `docs/audits/PRODUCTION-READINESS-LEDGER.md`. This file is still the architecture ledger. It is not a release certificate.

**Product contract:** `docs/PRODUCT.md`. **Programme completion tracker (12 issues, Gates A/B/C):** `docs/BUILD-STATUS.md`. This file remains the architecture ledger only. Do not treat `docs/ROADMAP.md` as a status SoT. Rows that say Find is out of V1, or that name Tk Home as the product door, are historical against the 2026-10-16 shell.

**Date:** 2026-10-05 (architecture baseline). Earlier rows retain their original dates.  
**Authority:** `docs/ARCHITECTURE.md` (production shell) · `docs/SEM-ARCH-V1.4.md` (engineering planned work) · this matrix (architecture closed vs open).  
**UI exposure classes:** `docs/UI-EXPOSURE-MAP.md` is a historical inventory plus a 2026-10-05 banner. Do not treat its September shell rule as current.  
**Do not** treat older freeze audits as current blockers without checking this file.

Look here first. Architecture migration is closed. Product construction is open.

## CLOSED — architecture migration (2026-10-05)

| ITEM | STATE | EVIDENCE |
|---|---|---|
| Architecture migration | **COMPLETE** | `docs/ARCHITECTURE.md` |
| Production shell | **PySide6** (`semblon shell`) | `semblon/native_shell/` → `Application` |
| Application boundary | **COMPLETE** — UI-independent; owns archive, jobs, Lens | `semblon/application.py` |
| One JobEngine | **COMPLETE** | Constructed only in `Application`. `semblon process` is headless and is not a second engine |
| Media lookup | **COMPLETE** | `Application.media` / `media_path`; UI decodes locally |
| Lens door | **COMPLETE** | `Application.query_media` → `lens.query_image` |
| Region Similar | **COMPLETE** | `remember_and_find_region` → `region_search.remember_and_find` |
| Review HTML | **RETIRED** | `review_chrome/` deleted. No production writer. No replacement Review page |
| Installer / launcher | **COMPLETE** | `tools/install-windows.ps1` installs `.[gui]`. Double-click opens the PySide6 archive |
| Schema, identity thresholds, Lens behavior | **UNCHANGED** by this migration | Do not retune |

Verification recorded with the baseline: **914 passed / 8 skipped / 0 failed**.

## OPEN — product construction (not another migration)

These are product and engineering gaps. They are not permission to reopen the shell, the façade, or `review.html`.

| ITEM | STATE | NOTES |
|---|---|---|
| Field + Focus experience | **LANDED on branch** | Native shell at `43eafe5`. Matrix date remains 2026-10-05; this row was stale. |
| Find | **Historical row — see `docs/BUILD-STATUS.md`** | The shell now has people search, text search, whole-image Similar, and region Similar. This row recorded the migration rule against a second query stack. Lens remains `Application.query_media`. Region Similar remains `Application.remember_and_find_region`. |
| People / Decision / Appearance / Time as lenses | **LANDED on branch** | Same session. Time is the mtime lens. People writes only through `review.py`. |
| Remaining production UX and polish | **CLOSED as designed** | Gate A offscreen journey is the acceptance (`docs/BUILD-STATUS.md`). A visible desktop grab is optional and is not a PASS claim. |
| Eventual Tk retirement | **COMPLETE** | `home`, `review-ui`, and `canvas` CLI clients removed; production UI is `semblon shell` only |
| Whole-machine stress testing | **CLOSED as designed** | Owner procedure in `docs/SHIP-GATES.md`. Not PASS. Workers stay 1. |
| PERF ARM64 OpenCV load | **BLOCKED** | See the ledger below. Not a shell decision |
| MSI `wix build` / sign | **CLOSED as designed** (engineering). Sign **not PASS** | Source and workflow exist. Signed smoke has not been run. `docs/SHIP-GATES.md`. |
| Identity ONNX redistribution (YuNet/SFace; buffalo_l historical) | **OUT OF SHIP** for bundling | BYO until L PASS. L is not PASS. `docs/decisions/2026-10-16-identity-engine-redistribution.md`. |

## Ship disposition (2026-10-24)

Identified cells finish here. Gate B is green on commit `558cbb212bfacd27dc63ce27637ca0a97124e784` (both `ci / test` jobs). That commit is on `main` via merge `db6d9ad` (PR #184). The merge is not a release and it is not Gate C.

| Cell | Finish |
|---|---|
| Remaining production UX | **Closed as designed.** Gate A is the acceptance. Desktop grab is optional and is not PASS. |
| Whole-machine stress | **Closed as designed.** Owner runs `docs/SHIP-GATES.md`. Not PASS. Workers stay 1. |
| PERF ARM64 OpenCV load | **BLOCKED.** Not PASS. Repro is `tools/perf_p1_arm64_repro.ps1`. Do not silent-swap S1. |
| MSI `wix build` / sign | **Closed as designed** for the engineering source. Signed smoke is not PASS. Owner certificate remains the act. |
| Identity ONNX redistribution | **OUT OF SHIP** for bundling. BYO until L PASS (`docs/decisions/2026-10-16-identity-engine-redistribution.md`). |
| Home drag-to-select (Tk row) | Historical Tk client. Production draw is Focus on PySide6. |
| Windows capture | **OUT OF SHIP.** `docs/decisions/2026-10-16-screen-capture-deferred.md`. |
| SigLIP / SAM2 / translation / VLM / landmarks | Optional BYO. A missing pack is reported. None of them write `faces.person_id` or `embeddings.modality='face'`. SigLIP kind door skips when absent. |
| Fast index | Exact derived matrix is the product index. ANN is **out of ship** (`docs/decisions/2026-10-19-lens-style-retrieval.md` slice 9). |
| Circuit breaker | Process memory only, by the row’s own contract. Not a store column. |

## Capability ledger

The table below is the longer capability ledger (identity, APP-1, packaging). Where an older sentence names Tk Home as the production GUI, the CLOSED section above wins.

| ITEM | CURRENT STATE | EVIDENCE | REMAINING ACTION | FINAL STATUS |
|---|---|---|---|---|
| Identity FACE-001→005 | Closed | `docs/FACE-GATES.md`, S1 golden | None (do not retune) | **COMPLETE** |
| APP-1 JobEngine door | Merged | `semblon/jobs.py`; clients go through `Application` | None | **COMPLETE** |
| APP-1 C.2 pause/unpause | Implemented + unit-tested | `JobEngine.pause/unpause/_gate`; `Application.pause_job/unpause_job` | None | **COMPLETE** |
| APP-1 C.3 Windows live | Live evidence 2026-09-22 + prior §I.5 | Owner Windows pytest 20 passed; ingest pause/resume | None | **VERIFIED ON WINDOWS** · APP-1 **CLOSED** |
| Application API façade | Named commands on `Application` | `semblon/application.py`; Activity via `application.activity` (**#65**) | None | **COMPLETE** |
| **Production GUI shell** | **PySide6 archive** | `docs/ARCHITECTURE.md`; installer `.[gui]` | Product UX in the OPEN section. Not a new shell | **COMPLETE** |
| Application boundary | UI-free façade owns JobEngine and ArchiveSession | `semblon/application.py` | None | **COMPLETE** |
| `review.html` | Retired. No production writer | `review_chrome/` deleted; `process_folder` does not export HTML | None | **RETIRED** |
| R2 IPC probe | Loopback probe on Application | `semblon/ipc_probe.py` | Not product IPC | **COMPLETE** (probe) |
| R3 Artifacts 1–4 / bake-off / §8.7 / Ruled-out | CLOSED / DONE | SEM-ARCH §I.5; #65 ship claim WIRED | Do not reopen | **OWNER-AUTHORIZED / CLOSED** |
| PERF ARM64 OpenCV | Load hang; PE/timed probes shipped | `docs/PERF-P1-ARM64.md`; `semblon/opencv_probe.py`; `tools/_perf_p1_load_cv2.py` | Owner Windows ARM64: `tools\perf_p1_arm64_repro.ps1`; fix/replace `opencv_geometry500.dll`; then P0 timing | **BLOCKED** (native load) · probe **COMPLETE** |
| Multi-worker / scale | Hash workers hardened; default **1**; harness `default_gate` | `docs/PERF-WORKERS-HARNESS.md`; ingest worker tests | Raise default only after owner Windows `default_gate.verdict=PASS` + separate PR | **COMPLETE** (default=1) |
| MSI code (no weights) | WiX project + stage/build/bootstrap + docs/tests | `packaging/msi/`, `tools/msi/`, `docs/PACKAGING.md` | Owner act remains: `wix`, `tools\msi\build-msi.ps1`, then signed smoke. Not PASS. | **CLOSED as designed** — sign not run |
| Identity ONNX redistribution | Legal | `docs/licenses.md`, `docs/IDENTITY-PACK.md` | YuNet/SFace BYO; MSI fail-closed | **UNAVAILABLE** |

## Production shell — current (2026-10-05)

Production UI is PySide6 → Application. See `docs/ARCHITECTURE.md`.

Tk Home, Tk review-ui, and Tk canvas are retired. `review.html` is not on the production path.

The block below is the 2026-09 correction of an earlier “native shell in progress” claim. It is **historical**. It is not the current shell decision.

## Production shell — historical correction (PR #54 + #65, superseded 2026-10-05)

Earlier matrix text claimed “native production shell IN PROGRESS / Tk Home is only compatibility.” That was **wrong** against the decisions shipped in September 2026. Those September decisions are themselves superseded by the 2026-10-05 baseline above.

1. **#54** — one shipping GUI: **tk Home + `review-ui`**; PySide product shell deleted.  
2. **#63–#66** — Inspector verbs, state-triple cards, Canvas Home integration, init-race fix.  
3. **#65** — closed leftover **UNWIRED** claim drift; Rule out **WIRED**; Activity via `application.activity`.

At that date the mapped production shell was **Tk Home**, and optional Qt `semblon shell` (#67) was not treated as the product Home. **Superseded 2026-10-05** by the completed PySide6 production migration.

## Status vocabulary

- **COMPLETE** / **VERIFIED ON WINDOWS** / **OWNER-AUTHORIZED / CLOSED** / **KEEP** / **PARTIAL** / **BLOCKED** / **UNAVAILABLE** / **SUPERSEDED** / **RETIRED** / **OPEN**

## APP-1 C.3 evidence (retained)

Owner Windows 2026-09-22: pytest jobs/application/ipc **20 passed**; live ingest with Pause/Resume control states + Canvas on the then-current client. APP-1 **CLOSED**. This paragraph is evidence of the job boundary. It is not a claim that Tk is still the production shell.

## Retired docs (2026-09-22)

Deleted superseded parallel / historical plan files that competed with this matrix + `SEM-ARCH-V1.4`: `SEM-ARCH.md`, `SEMBLON_MATURITY_BLUEPRINT.md`, `ROADMAP-RECONCILE.md`, `PRODUCTION-AUDIT.md`, `PRODUCTION-READINESS-2026-09-22.md`, `HUMAN-VERIFY-THEN-WIRE.md`, `CURSOR_INSTRUCTION.txt`, stub discovery/backlog/references, `CRITIQUE-P0.md`, historical `PERF-WORKERS.md`, redundant `docs/r3-packets/` (Ruled-out note lives in `CONTRACTS-RULED-OUT.md`; Artifacts stay under `docs/r3-artifacts/`). Git history retains them.

## Schema list 2026-09-25 (not a Windows verification)

These rows close the open schema list in code. They do not move ARM64, worker default, MSI sign, buffalo_l, or identify/inbox pages. The Home row is the legacy Tk client, not the production shell.

| ITEM | CURRENT STATE | EVIDENCE | REMAINING ACTION | FINAL STATUS |
|---|---|---|---|---|
| Home drag-to-select | Inspector “Select a region” maps a drag into `query_image` | `semblon/selection.py`, `home_ui._open_region_select` | Tk window not clicked in this environment (no libtk) | **PARTIAL** |
| Windows capture | Privacy intersection before grab. ImageGrab fallback. WGC import does not return frames | `semblon/privacy.py`, `lens.capture_screen` | Not tried on a Windows desktop | **PARTIAL** |
| SigLIP | ONNX session, L2 blob, not a face embedding. `semblon lab install` is atomic and does not download | `lens.embed_siglip`, `model_install.py` | Fixture is a tiny ONNX graph, not SigLIP weights | **PARTIAL** |
| SAM2 | Spatial discovery when `probe_sam2` is `SAM2_READY` (`SEMBLON_SAM2_CHECKPOINT`, no download). Otherwise OpenCV regions, state explicit. Hover is an owner-map lookup | `semblon/sam2_runtime.py`, `visual_analyze.py` | Real-photo quality is not a finished product claim. DirectML is not the SAM 2 backend | **PARTIAL** |
| Translation | JSON dictionary runs. Argos only if that import exists | `lens.translate_text` | No neural model shipped | **PARTIAL** |
| VLM | `pixel-describer` marker runs a local colour model. Bad schema is ERROR | `lens.describe_vlm` | Not a downloaded VLM | **PARTIAL** |
| Landmarks, logos, products | Local JSON pack, substring or barcode. Missing pack is UNAVAILABLE | `semblon/knowledge.py` | Not a world recognizer | **PARTIAL** |
| Fast index | Derived `.semblon-index.npz` from non-face embeddings. SQLite stays authoritative | `semblon/ann_index.py`, `search_similar` | Numpy cosine, not FAISS | **PARTIAL** |
| Circuit breaker | Lens query and ingest OCR/CLIP/pose. Three crashes then `{id}.CIRCUIT_OPEN` | `semblon/circuits.py` | Process memory only. Not Home text search | **PARTIAL** |
| Model installer | Write `.partial`, fsync, `os.replace`. Checksum mismatch does not replace dest | `semblon lab install` | No download | **COMPLETE** (local file) |

