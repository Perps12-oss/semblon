# Semblon build status — completion programme tracker

**Authority:** this file is the single completion tracker for the 12-issue programme.  
**Architecture ledger:** `docs/COMPLETION-MATRIX.md` (closed migration / capability ledger).  
**Product contract:** `docs/PRODUCT.md` (vision fixed; this file does not amend it).  
**Roadmap sequence:** `docs/ROADMAP.md` (milestones only; not a second status SoT).

| Field | Value |
|---|---|
| Evidence date | 2026-10-24. Commit `558cbb212bfacd27dc63ce27637ca0a97124e784` is on `main` via merge `db6d9ad6a2198b930dfbfcfc7672cbf9c1785284` (PR #184, 20:13 Europe/London). That merge is not a release. |
| Branch | `main` at merge `db6d9ad6a2198b930dfbfcfc7672cbf9c1785284` |
| Parent HEAD | (see git log on branch) |
| Working tree at evidence | Permanent Home stage + capability catalogue; shell journey updated |

## Behaviour landed — Contact Sheet / Light Table

The shell is now one Roll with a film-edge time scrubber, a four-verb Light Table, a Ctrl+K palette, a loupe for "find a detail", and a People table. Design: `docs/UX-CONTACT-SHEET.md`. Backend additions are small bridge slots only; engine, schema and identity thresholds are unchanged.

## Behaviour landed — Safelight Desk

The production shell is still the only GUI (`semblon shell`). Home is a first-arrival desk: one promise, **Add a folder**, three steps, then Library, Visual discovery, and People. Everyday labels no longer name engines, packs, or search internals. A notice banner separates a failure, a missing extra, and work in progress, and says the original files were not changed. Identity thresholds, schema, and face comparison were not edited. Plan: `docs/ux-overhaul-plan.md`.

Linux check on this branch, 2026-10-24: `xvfb-run -a .venv/bin/python -m pytest -q` → **988 passed, 7 skipped**.

## Status vocabulary

| Status | Meaning |
|---|---|
| NOT STARTED | No verified implementation |
| IN PROGRESS | Work exists; acceptance unmet |
| BLOCKED | Named external decision, dependency, or environment prevents completion |
| IMPLEMENTED | Code/config exists; verification incomplete |
| VERIFIED | All defined acceptance criteria pass with recorded evidence |
| DEFERRED | Explicit documented product decision excludes the item from this release |
| OUT OF SHIP | Same finish: an accepted decision, or the schema freeze, excludes the item. Not an open task. |

## Gates

| Gate | Meaning | Status |
|---|---|---|
| A — Core product | Archive continuity, Similar honesty, context where metadata permits | **VERIFIED** (offscreen production shell + unit). Visible desktop `SEMBLON_VISIBLE_SHELL=1` not required for these acceptance criteria; optional residual. |
| B — Engineering baseline | Supported CI on the current workflow | **GREEN on this commit** `558cbb212bfacd27dc63ce27637ca0a97124e784`. Both `ci / test` jobs succeeded: [run 40122825488](https://github.com/Perps12-oss/semblon/actions/runs/40122825488/job/120957878614) and [run 40122814924](https://github.com/Perps12-oss/semblon/actions/runs/40122814924/job/120957843502). Devin Review succeeded on the same pull request. Linux `xvfb-run -a .venv/bin/python -m pytest -q` → exit 0, **988 passed, 7 skipped**. That commit is on `main` via merge `db6d9ad` (PR #184). The merge is not a release. The 2026-10-23 cost cut still means Actions ran Windows Python 3.12 only; Ubuntu, 3.11, 3.13, 3.14, the lock compile, and `pip-audit` were not those jobs. |
| C — Release | Offline clean install + intended assets + **signed** installer | **BLOCKED** on the certificate. Weights are bring-your-own (`docs/decisions/2026-10-16-identity-engine-redistribution.md`). Unsigned MSI is not Gate C. Owner steps: `docs/SHIP-GATES.md`. |

## Dual verdict

| Verdict | Value |
|---|---|
| **1. Product and engineering completion** | **NOT COMPLETE** — Gate A verified. Gate B is green on commit `558cbb2`, which is on `main` via PR #184. That merge is not a release. Gate C is not signed. Confirmatory precision, Q/L/I/P, ARM64 OpenCV load, and whole-machine stress are not PASS. |
| **2. Release readiness** | **NOT READY** — Gate C signed MSI smoke has not been run. Weights stay bring-your-own. |
| **3. This roadmap pass (milestones 1–3)** | **COMPLETE** — acceptance evidenced (prior Gate A pass) |

Out of ship by an existing decision or by the schema freeze: **02** encryption, **08** product screen capture, albums (not a product workflow; no new table). See `docs/SHIP-GATES.md`.

## Twelve-item programme

| ID | Priority | Status | Evidence / remaining |
|---|---|---|---|
| 01 Win crash / Python matrix | P0 | **GREEN on this commit** for the current `ci / test` job | Windows Python 3.12 `test` succeeded twice on `558cbb212bfacd27dc63ce27637ca0a97124e784` (the two job URLs under Gate B). Not the 3.11–3.14 × Ubuntu matrix. On `main` via PR #184. Not a release. |
| 02 Encrypted store | P2 | OUT OF SHIP | `docs/decisions/2026-10-16-store-encryption-deferred.md` lines 7–9. Plaintext store. Do not claim SQLCipher or DPAPI. |
| 03 Signed offline MSI | P1 | IMPLEMENTED (eng) / BLOCKED (cert) | `tools/msi/build-msi.ps1` + `.github/workflows/msi-release.yml` (WiX v4/v5 via `dotnet tool wix`). Signs only when `CODE_SIGNING_PFX_*` secrets set; unsigned upload is engineering-only. |
| 04 Identity engine / pack | P0 | **IMPLEMENTED** (YuNet+SFace runtime) / **BLOCKED** (L redistribute, Q Semblon eval, P native ARM64) | Production path `opencv/yunet_sface`; `insightface` removed from deps; buffalo_l not loaded. BYO pack + pin. Smoke: ingest→cluster→name→reembed on Lena (x64). Gates: L OPEN, Q OPEN (provisional eps=0.45), I partial (pipeline wired), P partial. `docs/IDENTITY-PACK.md`. PRODUCT.md FaceKit wording unchanged until product-approval decision. |
| 05 Hashed dependency lock | P1 | IMPLEMENTED | `requirements.lock.txt` is present. The green `ci / test` jobs on this commit do not run the lock compile. Not PASS. |
| 06 FaceKit owner workflow | P1 | IMPLEMENTED / BLOCKED (run) | `tools/facekit_owner_evidence.py` + `.github/workflows/facekit-owner.yml` + `docs/FACEKIT-OWNER.md`. No owner pack on this machine — evidence JSON not PASS. |
| 07 Retired Tk / review.html / spike | P1 | IMPLEMENTED | Unchanged. |
| 08 Screen-capture privacy | P1 | OUT OF SHIP | `docs/decisions/2026-10-16-screen-capture-deferred.md` lines 7–9. Lab capture only. |
| 09 Visual-memory search | P0 | **CLOSED** for the synthetic rank bar. Precision is not PASS. | `docs/evidence/lens-retrieval-eval.json`: `status` **PASS** (line 2), `counts.passed` **5** (line 319), `precision` **null** (line 6), kind door **SKIPPED** (lines 65, 126, 187, 247, 308), `ann_justified` **false** (line 326). SigLIP is not installed. ANN is out of ship. Photographic milestone 2 stays the separate verified set. |
| 10 Archive continuity | P0 | **VERIFIED** | Missing Focus notice; ingest rename reconnect; copy/basename safety; Gate A journey on Unicode folder. |
| 11 Contextual discovery | P1 | **VERIFIED** | `openFocusInContext` day scope includes same-day neighbours and excludes other days; missing-date honest. |
| 12 Unified experience + docs | P0/P1 | **VERIFIED** (milestones 1–4). Milestone 7 synthetic bar closed. | Gate A journey. Milestone 4 keep-a-discovery is verified. Gate B is green on this commit. Gate C is not PASS. |

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
| `pytest tests/test_discovery_slice_b.py` + People desk tests | **7 passed** (slice B) |
| `pytest tests/test_discovery_slice_c.py` | **3 passed** (slice C) |
| `pytest tests/test_discovery_slice_d.py` + region/Gate A Similar | **7 passed** (`--basetemp=.pytest-tmp-slice-d*`) |
| Live user database | **not modified** |
| `.venv-312` `tools/eval_visual_discovery.py` | **exit 0** — synthetic glyphs, DINOv2 ViT-S/14, floor 0.76, Recall@5 1.0, Precision@5 0.857 (`docs/evidence/visual-discovery-eval.json`). An earlier MobileNetV2-7 run (Precision@5 0.633) is not the file on disk. |
| `pytest tests/test_visual_discovery.py tests/test_region_search.py tests/test_discovery_slice_d.py tests/test_similar_faces.py --basetemp .pytest-tmp-vd-mobilenet` | **23 passed** |
| `pytest` visual discovery + `test_shell_add_folder_indexes_appearance_and_draw_finds_it` + video-track desk `--basetemp .pytest-tmp-vd-shell2` | **16 passed** (114s) |

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
2. Shell: Focus face box click → `findSimilarFaces` → results strip labelled **Same face**. Region Similar is DINOv2 when the pack is installed (**Similar look**). Whole-image Similar prefers the scene vector of that model. Colour histogram is the labelled fallback (**Colour only**), not the primary path.
3. CLI: `semblon search --similar-face FACE --store …` (lab/read-only).

## Behaviour landed — discovery slice B

1. People desk: board `band` plumbed; titles “Candidate group” / “Strong candidate group” / named; honesty note that groups ≠ persons; review counts include need-review / strong.
2. Focus: “Review this group” when selected face maps to a board subject → leaves Focus, opens People, selects that group. No auto-name.
3. Q thresholds unchanged (still provisional in `identity_config.py`).

## Behaviour landed — discovery slice C

1. Named People row → `personId` + `memory.history` → day chips (newest first) and **Browse in Time**.
2. Day chip / Browse → close People → `openFocusInContext` (Gate A archive-wide day neighbours). Honest empty if no dated stills.
3. Explicit **Show only this person** Field filter (opt-in); day neighbours stay archive-wide until that filter is on. No auto-name.

## Behaviour landed — discovery slice D

1. Whole / region / face Similar all publish through shared adapter + Focus strip (`similarBasis` / `similarBasisLabel`).
2. Ready-state basis note visible above the strip (not only empty/unavailable).
3. Current basis labels: **Similar look**, **Colour only**, **Same face**, **Text in the selection**, **Unknown region**. Slice D originally shipped colour-histogram wording for region and whole-image Similar. That wording is historical. The primary region path is the DINOv2 crop index.

## Behaviour landed — discovery slice E (OCR / objects BYO)

1. `search_text` joins `media_id`, returns `media_ids` + basis “Text in photos (OCR substring)”; respects active Field via `within_media_ids`; shell text mode sets Field. Label: text in photos — not a person. Tesseract OS/BYO (present on this machine).
2. NanoDet BYO pack (`docs/OBJECT-PACK.md`): pin + SHA required; OpenCV DNN postprocess matches 3-level ONNX layout; observe when ready; `search_object` / CLI `--object` / shell Search objects. Live detect evidenced (person/couch). Contours stay `opencv-contour` / `region`. MSI fail-closed on `.onnx` (L OPEN — not bundled).
3. People desk: tracks “Track (not a person)”; unresolved → inbox; person-only Field filter; Focus → People prefers named person when face already named. Offscreen tests in `test_ae_shell_programme.py`.

## Behaviour landed — region encoder (2026-10-17)

1. Production region encoder is DINOv2 ViT-S/14 ONNX (Apache-2.0). An earlier session-init hang was a lock deadlock in this module; after the fix the first embed was about 2s and the next under 1s on emulated x64. MobileNetV2-7 logits are not the production representation.
2. The measured ranking is in the section below and in `docs/evidence/visual-discovery-eval.json`.

## Capability notes

- Setup check is `semblon lab preflight`. It reads `requirements.txt` and `requirements-dev.txt` pins and the existing pack probes. A pin that already matches is skipped. `--install ID` installs that one item into the active virtual environment and marks it ready only after a second check sees the installed version. A pip call that returns without that version stays failed. The report exits non-zero when a required pin is not ready or any check failed. A missing optional model is printed and does not by itself fail the report. An unreadable requirements file or package list is a failed row, not a silent skip. It does not change system Python, does not install unpinned extras, and does not download identity weights, CLIP weights, or a signing certificate. Settings lists capabilities that are not ready, with one Install button each, and does not open that list during ordinary browsing. Install and check failures stay visible in primary mode as `Setup:` lines. Colour-only search stays labelled as colour when the region model is absent. The pytest session prints required gaps, including the reason, and does not fail the suite for them.
- Region Similar uses pinned DINOv2 ViT-S/14 CLS vectors (`modality=region`) when the pack is installed. Whole-image Similar prefers `scene`, then `clip`, then appearance. Colour histogram (`appearance/rgb8@1`) is only the labelled fallback. Not face identity.
- Focus face Similar is face embedding (same pack); not a name; not auto-assign.
- People desk groups are hypotheses until Name; Name remains the only person-create path.
- Named person → Time uses archive day scope (neighbours may include other people that day) unless person-only filter is explicit.
- Results chrome is one strip; basis labels stay distinct per door.
- Pack gate unchanged. ARM64 OpenCV load remains BLOCKED historically (`docs/PERF-P1-ARM64.md`).
- Identity runtime is YuNet + SFace (`opencv/yunet_sface`); buffalo_l retired from deps (BYO historical only).
- Object/OCR search never votes on identity. NanoDet/SFace/YuNet MSI bundling remains L OPEN.

## Outstanding blockers (exact)

1. **GHA `ci / test` on this commit** — **closed.** Both jobs succeeded on `558cbb212bfacd27dc63ce27637ca0a97124e784`: https://github.com/Perps12-oss/semblon/actions/runs/40122825488/job/120957878614 and https://github.com/Perps12-oss/semblon/actions/runs/40122814924/job/120957843502. Devin Review succeeded. On `main` via merge `db6d9ad` (PR #184). Not a release. The wider Python matrix was not these jobs.
2. **FaceKit owner pack run** (issue 06) — helper/workflow ready; needs real pack → PASS evidence JSON.
3. **Identity weight redistribution** (Gate C) — YuNet/SFace and historical buffalo_l are BYO. Commercial redistribute still UNAVAILABLE. `docs/PRODUCT.md` still names FaceKit as the only engine; that sentence was not rewritten.
4. **Authenticode certificate** (Gate C) — signing path in `msi-release.yml`; secrets not provisioned.
5. WiX owner run on a machine with WiX + (optional) cert — workflow exists; not executed here.
6. **Named-face recluster** — repaired: a multi-face `name` decision now locks every `policy.face_ids` entry, and `name_faces` refuses a conflicting `attach_to_person_id`. `merge_clusters` still copies one shared `person_id` onto survivor faces; that stamp is the tested review contract (`tests/test_review.py`), not an unapproved threshold change.
7. **Store is plaintext.** **Closed as out of ship.** `docs/decisions/2026-10-16-store-encryption-deferred.md` lines 7–9. Do not claim SQLCipher or DPAPI.
8. **Replaced file path** — repaired in `claim_new_media`: the previous digest no longer keeps the path, so an old crop cannot read the new bytes. Confirmed identities on the old digest are not deleted.
9. **Erasure centroid** — repaired: deleting a person drops or rebuilds `clusters.centroid` from the faces that remain.
10. **`docs/PERF-P1-ARM64.md` identity cell** — corrected. The 2026-09-22 FaceKit / `eps=0.40` sentence is historical. Current engine text is YuNet + SFace. The OpenCV load block is unchanged. No threshold was edited.

The 2026-10-22 audit, repairs, and the commands actually run are in `docs/audits/PRODUCTION-READINESS-AUDIT.md`. Release verdict there: **NOT READY FOR RELEASE**.

## Behaviour landed — photographic patch retrieval (2026-10-18)

1. Contract centre of gravity is point → understand → find (`docs/PRODUCT.md`, `docs/decisions/2026-10-18-local-visual-discovery.md`). Archive, people, and time stay supporting capabilities.
2. Ingest stores every content patch of the frame plus overlapping windows (`modality=region_patch`, pack id ending `/patch`). A query crop is scored by late interaction against those patches. Proposal CLS rows remain only when the patch map is absent. No new columns. No face writes.
3. The selection says face, a detector class, text, one local noun that beats "no specific name", or unlabelled region. The noun is not a person and does not choose the matches. A missing naming weight stays unlabelled. It does not invent a product or a person.
4. A result carries `match_norm`. Opening that result draws the box on the photo. Back still returns to the previous search.
5. **Keep this find** writes `{store}.discoveries.json` (query, selection, hits, match boxes). Opening a kept find restores that search.
6. Command: `.venv-312\Scripts\python.exe tools\eval_photo_regions.py` → **exit 0**. Sources are scikit-image photographs. Viewpoint is a homography of the crop on another photograph. Lighting is gamma plus a colour cast. The distractor is the crop's mean colour on another photograph.

| Query | Viewpoint rank | Lighting rank | Own distractor | Match box |
|---|---|---|---|---|
| chelsea | 1 (0.564) | 2 (0.546) | absent | yes / yes |
| clock | 1 (0.526) | 4 (0.501) | 6 | yes / yes |
| coins | 2 (0.424) | 1 (0.706) | absent | yes / yes |
| camera | 2 (0.613) | 1 (0.627) | absent | yes / yes |

Coins lighting had proposal IoU 0.0 and was still rank 1, so the hit is not one of the six proposal boxes. Clock's own colour distractor is rank 6, behind both true hits. Other library photos can still sit between those two hits (clock lighting is rank 4). That impurity is in the JSON. It is not a missed positive.

Floors, chosen on this run: token cosine 0.35, mean score 0.28, coverage 0.28.

## Behaviour landed — discovery workspace (2026-10-18)

The archive shell is unchanged as a browser. Focus is the discovery surface.

1. The selection is a clear crop on the stored rectangle: white corner brackets and a dim on the picture outside the frame. A drawn region stays unnamed and is not replaced by a nearby detection. A click on a face, read text, or detector box adopts that box. A click that misses those boxes stays a small rectangle on the point. A contour is not a snap target. An empty similar search says nothing was close enough. Edges and corners resize it. Dragging inside it moves it. Click still points. Drag still draws. Ctrl+wheel, trackpad pinch, and touch pinch zoom the photo (1×–8×). Middle-drag or Alt-drag pans. Left and Right move to the previous and next photo and reset that zoom. Search this area repeats the search on that rectangle.
2. Similar search runs off the UI thread. The strip says it is looking, Cancel search and Escape drop a late result, and a newer search replaces a slower one.
3. Each result draws its match box on that thumbnail (fit, not a crop that hides the box). The open match photo draws the same box. The query outline stays on the query photo. The line under the strip says a match is a similar region, not proof it is the same object.
4. Kept finds restore the query photo, the rectangle, and the match boxes.
5. Index copy distinguishes still indexing, this photo already searchable, coarse index only, and not indexed. A scan shows a card with a progress bar and Pause or Cancel. The card does not cover the library, so photos already added can still be opened. The grid reloads as that count moves.
6. Scores and the index state word sit in Advanced. Primary shows the photo, the selection, the understanding line, and the matches.
7. Settings **Clear library** asks first (No is the default). Yes deletes the folder index, names, and the two discovery sidecars beside the store. Original files stay on disk. Display settings stay. **Reset defaults** still only clears appearance and caches.

Indexing cost is unchanged: up to nine ONNX passes per still. The 16-image photographic run remains the retrieval measurement. A larger-library timing and memory run was not taken. A desktop grab of this shell is `docs/evidence/discovery-workspace.png` when that file is present; offscreen tests cover the sequence without it.

## Behaviour landed — local region retrieval (2026-10-17)

Historical. The photographic patch result above replaces the glyph-only claim for region search.

1. Encoder: DINOv2 ViT-S/14 ONNX, Apache-2.0, CLS token, letterbox 224, ImageNet mean/std, L2. `pack_id` `region/dinov2-vits14@1/f22797eabf810a75/cls`. Vectors live in existing `embeddings` rows (`modality` `region` for crops, `scene` for the whole frame). Observation kind is `clip` with `display: false`. No new columns.
2. Ingest indexes contour/object crops plus one scene vector when the pack probes ready. The query embeds only the selection. Source media is excluded. Results dedupe by media. Score floor is 0.76 cosine.
3. Focus: point or draw searches. An object or text box click searches. A face box click stays on face similarity. Opening a result keeps the result strip (`openDiscoveryHit`); day scope is a separate action. Last search is stored beside the sqlite file as `{stem}.visual-discovery.json`.
4. Labels a person can read: "Similar look", "Same face", "Text in the selection", "Colour only", "Unknown region".
5. PDF, HEIC, and TIFF are not opened. A video tile opens sampled frame 0, not a player.
6. Machine for this evidence: Windows ARM64 host, emulated x64 Python (`.venv-312`, `platform.machine()` ARM64, `PROCESSOR_ARCHITECTURE` AMD64). Not native ARM64. MSI, CI, and native ARM64 were not run.

Synthetic glyph eval (`tools/eval_visual_discovery.py`, not a photo benchmark), floor 0.76:

| Metric | Value |
|---|---|
| Recall@5 (query has at least one other mark) | 1.0 |
| Other-mark recall@5 | 0.4 |
| Precision@5 | 0.857 |
| Colour-bar top1 | 0 |
| Top1 not a mark | 1 (clutter crop includes a disc) |
| Index, this floor-0.76 run | 19.924 s |
| Query mean / max | 0.676 s / 0.969 s |

Same-glyph neighbours on this fixture often score about 0.78–0.88. Rotated or darker variants of the first mark fall under the floor and are not returned. That is not reliable same-object retrieval across viewpoints.

A border-background suppression variant (`cls-fg`) was measured on this same glyph set and rejected: other-mark recall@5 stayed 0.4 and precision@5 fell to 0.667. Production stays CLS with floor 0.76. The rejected run is `docs/evidence/visual-discovery-eval-cls-fg-rejected.json`.

Generated textured objects (not photographs): `tools/eval_rendered_regions.py` — 3 mug queries, other-mug hit@5 1.0, a same-tint tile was never top1 but did appear in the list (scores about 0.79–0.83). `docs/evidence/visual-discovery-eval-rendered.json`.

Visible shell grab: `docs/evidence/visual-discovery-shell-windows.png` shows **Similar look** and `Similar (Similar look): 1 match.` on a generated mug. See `docs/evidence/visual-discovery-shell.md`.

Setup: `py -3 tools/fetch_region_pack.py` once. Search does not download.

## Behaviour landed — Focus discovery chrome (2026-10-23)

The search operations are unchanged. Focus presents them as one action, a results tray, and a visible running state.

1. With a region selected, the primary action is **Find similar**. **Describe this area** names the crop. **Find this person** appears only when the photo has a face box, and it uses the existing face search. Duplicates, whole-photo search, quality, Same look / Same kind, a word, and part chips sit in **More**.
2. The file-details drawer stays closed until **Details**. The photo keeps the width of the stage. Matches scroll in `focusTray` across the bottom, with the match rectangle on each thumbnail. Opening a thumbnail still uses `openDiscoveryHit`.
3. A running search shows an indeterminate spinner immediately (`focusSearchSpinner`), the backend note, and **Cancel search**. The phase chip stays hidden until that search is no longer busy, so a first look is not presented as finished. Completion, an empty list, cancel, and failure replace the spinner with the existing note. No percentage is invented.
4. Timings, the door name, retrieval detail, and the diagnostics panel stay on Advanced. A match is still not proof it is the same object.

## Behaviour landed — three search doors (2026-10-19)

The 2026-10-23 Focus chrome is how these doors appear now. This section records the operations as they landed.

1. Focus has separate controls for **Similar region**, **Same face**, **Duplicates**, and **Whole photo**. Similar region searches the highlighted area. Duplicates stays an exact and near-copy scan and does not replace that strip.
2. The result strip carries a phase badge. Focus also shows the time to the first look and the time to the refined result.
3. **Name this area** shows a confidence chip when the face, detector, or local noun has a score. An unlabelled area has no invented score.
4. Keys in Focus: S similar region, W whole photo, F same face, Ctrl+D duplicates.
5. Command: `python3 -m pytest tests/test_search_doors.py tests/test_local_lens.py tests/test_discovery_slice_d.py::test_unified_basis_messages_are_allowlisted tests/test_native_shell.py::test_focus_qml_keeps_the_strip_and_a_primary_similar_action tests/test_shell_frontend.py::test_qml_has_no_hardcoded_chrome_colors tests/test_shell_adapter.py::test_qml_exposes_four_operations_and_hides_places tests/test_discovery_workspace.py -q` → **20 passed, 1 skipped**.

## Behaviour landed — name the highlighted area (2026-10-19)

1. **Name this area** reads the highlighted crop and shows a face, a detector class, text, one local noun, or an unlabelled region. The similar strip stays as it is.
2. Similar search no longer waits on that naming model. A stored face, object, or text line can still appear with the matches. The noun runs only when Name this area is used.
3. Moving the box or opening another photo drops a name that has not finished. The name is not a person and it is not written onto a face.
4. Command: `python3 -m pytest tests/test_local_lens.py tests/test_discovery_slice_d.py::test_unified_basis_messages_are_allowlisted tests/test_similarity_quality.py tests/test_shell_frontend.py::test_every_qml_action_maps_to_a_real_bridge_slot_or_property tests/test_shell_frontend.py::test_qml_has_no_hardcoded_chrome_colors -q` → **24 passed, 1 skipped**.

## Behaviour landed — progressive similar search (2026-10-19)

1. Balanced and Max publish a Fast first look, then replace it with the fuller pass. Fast stays a single pass. The phase is named in Focus: First look, Refined, Fast look, or Kept the first look.
2. The highlighted box is stored once. The refine pass does not write a second user region, a face, or an embedding.
3. Cancel during refine keeps the first look on the strip. A fuller pass that comes back empty keeps those hits too.
4. Command: `python3 -m pytest tests/test_similarity_quality.py tests/test_discovery_workspace.py tests/test_discovery_slice_d.py tests/test_shell_frontend.py::test_qml_has_no_hardcoded_chrome_colors tests/test_shell_frontend.py::test_every_qml_action_maps_to_a_real_bridge_slot_or_property tests/test_region_search.py tests/test_visual_discovery.py -q` → **37 passed, 1 skipped**.

## Behaviour landed — search quality profiles (2026-10-19)

1. Settings and Focus expose **Fast**, **Balanced**, and **Max**. The choice is stored in `appearance.json` as `search_quality`. It is not a schema column and it does not change face identity.
2. Fast tightens region and whole-image floors and returns fewer hits. Max lowers those floors and keeps a wider result list. Duplicate scan stays the separate Duplicates action.
3. Focus shows the active quality beside the selection. A region search and a whole-image search both read the saved profile.
4. Command: `python3 -m pytest tests/test_similarity_quality.py tests/test_discovery_workspace.py tests/test_shell_frontend.py::test_qml_has_no_hardcoded_chrome_colors -q` → **13 passed**. Settings Fast / Balanced / Max are real controls, and Fast raises the colour and scene floors used by Similar.

## Behaviour landed — editorial Home launchpad (2026-10-18)

1. Home is a permanent stage (`showHome` / `homeOpen`), empty or populated. Adding a folder does not hide it.
2. Sidebar: Home, Library, People, Add folder, Settings. Library opens the timeline Field. Visual discovery opens Focus on a still (or Add a folder when empty).
3. Home cards: Library, Visual discovery, People. **Explore all capabilities** opens a filterable catalogue of actions the shell already runs.
4. Primary / Advanced and Atmosphere moved into the Settings sheet. Native Windows caption follows the shell background when DWM allows it.

## Behaviour landed — selection retrieval (SQ-5–SQ-7)

1. A screen selection runs one local retrieval: region/image similarity, OCR substring search, and object-label search. Hits merge by photo. Each hit keeps the basis that found it (`Similar look`, `Text in photos (OCR substring)`, `COCO object detection (NanoDet)`). Text-only mode does not run visual similarity. A missing region model stays unavailable when no other door matched.
2. Similar search reads the exact derived matrix through `index_provider.active_vector_index`. SQLite embeddings stay authoritative. ANN is named and disabled. FAISS and Chroma are not product dependencies.
3. Object detection and the vision-language describer are optional providers (`optional_providers`). A missing weight is reported. Neither provider writes face identity.
4. When the current search needs the object model or the local description, the shell offers one install button on that same screen. Confirmation downloads the pinned NanoDet file, or writes the local pixel-describer marker, then runs that search again. Search itself does not download. NanoDet MSI bundling stays blocked.

## Behaviour landed — multi-leg local retrieval (2026-10-19)

**Status:** IMPLEMENTED on the interactive path. Optional VLM judge and ANN stay off this path. Branch `cursor/lens-retrieval-strategy-1388`.

Focus **Similar region** now accepts a query spec (`look` / `kind`, a word, a part) and, after the Fast first look, fuses DINOv2 / colour with OCR+BM25, NanoDet class, and optional SigLIP same-kind recall via Reciprocal Rank Fusion plus a cheap feature rerank. Fast stays a single visual pass. Missing packs skip that door; they do not fail the search. Chrome uses **Same look**, **Same kind**, **Add a word**, and part chips. No model names. No identity writes. No new columns. No Chroma/FAISS.

After the fused list is on screen, a cheap match check can reorder the top hits (colour + local pixel description). The strip says **Checked the matches**. Fast skips this. A missing VLM does not block the grid. No identity writes.

Labelled eval harness (`semblon/lens_eval.py`, `tools/eval_lens_retrieval.py`) scores highlight / relevant / hard-negative tuples: brand text, same kind, same look, part vs whole, same-colour confuser. `--eval-set synthetic` prints ranks and `relevant_above_hard_neg` only. Precision stays refused without `--eval-set confirmatory`. No frozen confirmatory file is in the tree (`docs/LENS-CONFIRMATORY.md`). Historical synthetic run: **3/5**. Current synthetic run: **5/5** after pool-relative features; weights were not retuned. Kind door `SKIPPED` without SigLIP. ANN is out of ship. Report: `docs/evidence/lens-retrieval-eval.json`.

Command: `python3 -m pytest tests/test_lens_eval.py tests/test_lens_retrieval.py tests/test_selection_retrieval.py tests/test_discovery_slice_d.py tests/test_search_doors.py tests/test_similarity_quality.py tests/test_region_search.py tests/test_local_lens.py tests/test_discovery_slice_e.py tests/test_visual_discovery.py tests/test_discovery_workspace.py tests/test_shell_frontend.py::test_every_qml_action_maps_to_a_real_bridge_slot_or_property -q` → **80 passed, 2 skipped**.

Plan: `docs/decisions/2026-10-19-lens-style-retrieval.md`. Roadmap milestone 7.

## Behaviour landed — calendar column and photo field (2026-10-20)

1. Library stage at least 900 px wide places the calendar column on the left and the existing photo field on the right. `archiveSplit` remembers the ratio. Narrower windows stack the field underneath. Scope, Focus, Home, People, and Settings keep their current actions.
2. Years, Months, and Days change only the left column. Month cells show at most six thumbs. Years are twelve real month cards. Pinch or Ctrl+wheel moves between those densities and does not change the media scope. Scrolling the photos follows the visible month only.
3. `revealDay` highlights a date without filtering. A no-date chip opens the undated bucket. Person and folder filters can mark days. Opening a photo shows file name, archive day, pixel size, and byte size inside Focus.
4. Command: `QT_QPA_PLATFORM=offscreen python3 -m pytest tests/test_timeline_view.py -q` → **13 passed**.

## Behaviour landed — one library workspace (2026-10-23)

The calendar fills the library pane. A date (or the no-date chip) replaces it with that day's grid. A photo replaces the grid with Focus. Back and Escape take one step, and the task tray closes first. Year, month, and density stay on the calendar. Folder, moment, and Everything selections open the same grid. The split handle stays stored and is not shown. Contract: `docs/TIMELINE-VIEW.md`.

Command: `xvfb-run -a .venv/bin/python -m pytest -q tests/test_timeline_view.py tests/test_library_tasks.py tests/test_thumb_cache.py tests/test_shell_frontend.py tests/test_discovery_workspace.py tests/test_native_shell.py` → **95 passed**.

## Behaviour landed — library work tray and grid thumbs (2026-10-23)

1. The library is one workspace (calendar, then the day's grid, then Focus). A bottom pill stays on every depth. `Quiet` means nothing is scanning, and the sheet offers check-for-new-files or add-a-folder. A running add is `1 task`; a search at the same time makes `2 tasks`. Pause, resume, and cancel live on that sheet. A top-right chip shows `Scanning · current / total` and opens the same sheet. The old scan card no longer covers the field.
2. Grid thumbs write one 384 px JPEG under `<store stem>.thumbs/` the first time a file is decoded. The next cell reads that JPEG. Focus frames stay in memory. Clear library deletes the folder. No new table and no writes into the photo folder.
3. Command: `xvfb-run -a .venv/bin/python -m pytest -q tests/test_library_tasks.py tests/test_thumb_cache.py tests/test_timeline_view.py tests/test_shell_frontend.py tests/test_discovery_workspace.py tests/test_native_shell.py` → **95 passed**.

## Behaviour landed — pool-relative rerank (2026-10-24)

1. `feature_rerank` divides look, text, object, kind, and RRF by the best value of that feature in the candidate pool, then applies the existing weights (look 0.45 / 0.18, kind 0.18 / 0.42, text 0.22, object 0.15, RRF 0.30, word bonus 0.08, RRF `k` 60). No weight constant was edited. No floor was edited. S1 was not touched.
2. `brand-acme` and `part-logo` place the relevant hit above the hard negative. The kind door is still `SKIPPED` (SigLIP pack absent). That skip is the missing-pack contract, not a failed search.
3. Confirmatory precision stays null. The loader and the manifest rules are `docs/LENS-CONFIRMATORY.md`. Gates B and C procedures are `docs/SHIP-GATES.md`.
4. Command: `.venv/bin/python tools/eval_lens_retrieval.py --eval-set synthetic` → exit 0, status **PASS**, 5/5, precision null, `ann_justified` false, `exact_scan_ms` 43.428 on this run (corpus 10). Identity rows were not written. `--eval-set confirmatory` → exit 1, status `not_confirmatory`, precision null. That refusal is the missing frozen file, not a rank-bar failure.
5. Command: `xvfb-run -a .venv/bin/python -m pytest -q` → exit 0, **988 passed, 7 skipped** (Linux Python 3.12, offscreen Qt).
6. Gate B on this same commit: both GitHub `ci / test` jobs succeeded (URLs in the Gates table). Devin Review succeeded. That green is commit `558cbb2`, now on `main` via PR #184. The merge is not a release.

## What this file will not absorb

Architecture migration status stays in `docs/COMPLETION-MATRIX.md`. Closed FACE gates stay in `docs/FACE-GATES.md`. Product vision stays in `docs/PRODUCT.md`.

- Contact Sheet polish pass (PR #187): drop-zone first run, sticky month header, day breaks, clearer scrubber, receding bar, plain-words install dialogs, keyboard loupe and People actions. See docs/UX-CONTACT-SHEET.md.
- Contact Sheet fix-up pass (PR #187): month grouping and header corrected (per-month sections and counts), real day rows, even scrubber, in-theme confirm sheet replaces native pop-ups, pressed and focus states on the bottom bar. See docs/UX-CONTACT-SHEET.md.
