# Semblon build status — completion programme tracker

**Authority:** this file is the single completion tracker for the 12-issue programme.  
**Architecture ledger:** `docs/COMPLETION-MATRIX.md` (closed migration / capability ledger).  
**Product contract:** `docs/PRODUCT.md` (vision fixed; this file does not amend it).  
**Roadmap sequence:** `docs/ROADMAP.md` (milestones only; not a second status SoT).

| Field | Value |
|---|---|
| Evidence date | 2026-10-18 (editorial Home launchpad) |
| Branch | `grok/home-launchpad` |
| Parent HEAD | (see git log on branch) |
| Working tree at evidence | Permanent Home stage + capability catalogue; shell journey updated |

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
| 09 Visual-memory search | P0 | **VERIFIED** on photographs (2026-10-18) | Dense `region_patch` late interaction, not the six proposal crops. `docs/evidence/photo-region-eval.json`: 4/4 photographs, viewpoint and lighting ahead of the same-colour distractor, match box on the paste. Colour histogram remains the labelled fallback. Face Similar stays a separate door. |
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

- Region Similar uses pinned DINOv2 ViT-S/14 CLS vectors (`modality=region`) when the pack is installed. Whole-image Similar prefers `scene`, then `clip`, then appearance. Colour histogram (`appearance/rgb8@1`) is only the labelled fallback. Not face identity.
- Focus face Similar is face embedding (same pack); not a name; not auto-assign.
- People desk groups are hypotheses until Name; Name remains the only person-create path.
- Named person → Time uses archive day scope (neighbours may include other people that day) unless person-only filter is explicit.
- Results chrome is one strip; basis labels stay distinct per door.
- Pack gate unchanged. ARM64 OpenCV load remains BLOCKED historically (`docs/PERF-P1-ARM64.md`).
- Identity runtime is YuNet + SFace (`opencv/yunet_sface`); buffalo_l retired from deps (BYO historical only).
- Object/OCR search never votes on identity. NanoDet/SFace/YuNet MSI bundling remains L OPEN.

## Outstanding blockers (exact)

1. **GHA CI matrix green** (Gate B) — aggregate `test` job landed; remote green not evidenced here.
2. **FaceKit owner pack run** (issue 06) — helper/workflow ready; needs real pack → PASS evidence JSON.
3. **buffalo_l redistribution licence** (Gate C) — BYO decision recorded; commercial redistribute still UNAVAILABLE.
4. **Authenticode certificate** (Gate C) — signing path in `msi-release.yml`; secrets not provisioned.
5. WiX owner run on a machine with WiX + (optional) cert — workflow exists; not executed here.

## Behaviour landed — photographic patch retrieval (2026-10-18)

1. Contract centre of gravity is point → understand → find (`docs/PRODUCT.md`, `docs/decisions/2026-10-18-local-visual-discovery.md`). Archive, people, and time stay supporting capabilities.
2. Ingest stores every content patch of the frame plus overlapping windows (`modality=region_patch`, pack id ending `/patch`). A query crop is scored by late interaction against those patches. Proposal CLS rows remain only when the patch map is absent. No new columns. No face writes.
3. The selection says face, a detector class, text, or unlabelled region. It does not invent a product or a person.
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

1. The selection is a clear crop on the stored rectangle: white corner brackets and a dim on the picture outside the frame. A drawn region stays unnamed. An empty similar search says nothing was close enough. Edges and corners resize it. Dragging inside it moves it. Click still points. Drag still draws. Ctrl+wheel, trackpad pinch, and touch pinch zoom the photo (1×–8×). Middle-drag or Alt-drag pans. Left and Right move to the previous and next photo and reset that zoom. Search this area repeats the search on that rectangle.
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

## Behaviour landed — editorial Home launchpad (2026-10-18)

1. Home is a permanent stage (`showHome` / `homeOpen`), empty or populated. Adding a folder does not hide it.
2. Sidebar: Home, Library, People, Add folder, Settings. Library opens the timeline Field. Visual discovery opens Focus on a still (or Add a folder when empty).
3. Home cards: Library, Visual discovery, People. **Explore all capabilities** opens a filterable catalogue of actions the shell already runs.
4. Primary / Advanced and Atmosphere moved into the Settings sheet. Native Windows caption follows the shell background when DWM allows it.

## What this file will not absorb

Architecture migration status stays in `docs/COMPLETION-MATRIX.md`. Closed FACE gates stay in `docs/FACE-GATES.md`. Product vision stays in `docs/PRODUCT.md`.
