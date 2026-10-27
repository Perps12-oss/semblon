# SEMBLON completion matrix — Blueprint v3 frontend

**Historical snapshot:** 2026-10-09. **Does not replace** `docs/COMPLETION-MATRIX.md`.  
**Current-source correction — 2026-10-27:** the production shell QML root is `native_shell/qml/Table.qml`; current surfaces and category routes are documented in `docs/UI-EXPOSURE-MAP.md`. This matrix's Windows exercise and counts are historical evidence, not current branch verification.  
**Annotated blueprint:** `docs/FRONTEND-BLUEPRINT-V3-ANNOTATED.md`

Verdicts: COMPLETE | PARTIAL | NOT EXPOSED | NOT IMPLEMENTED.  
A disabled control is not an implementation. NOT IMPLEMENTED has no UI entry.

Windows exercise is the real PySide6 shell on this machine under `QT_QPA_PLATFORM=offscreen`. It is not a human click-through of a visible window. Host: Windows 11 `10.0.26200`, machine ARM64, process AMD64 (`C:\Users\S8633\AppData\Local\Python\pythoncore-3.14-64\python.exe`). That process is **emulated**, not native.

## Summary

| Verdict | Count |
|---|---|
| COMPLETE | 26 |
| PARTIAL | 28 |
| NOT EXPOSED | 4 |
| NOT IMPLEMENTED | 1 |
| **Total** | **59** |

## Rows

Columns: backend, adapter, UI, data flow, dependency, branch, Windows, verdict.

| # | Capability | Backend | Adapter | UI | Data flow | Dependency | Branch | Windows | Verdict | Why |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Explore / Archive | `ArchiveSession.window`, `Application.archive_count` | `archive_summary` | `fieldGrid`, empty state | model window | empty library stays empty | existing session | shell suite loads the grid | COMPLETE | Archive stills render through Application. |
| 2 | Folder management | `Application.submit_ingest` | `addFolder` | Add folder | ingest then `library.changed` | files stay put | existing job door | add-folder test in `tests/test_native_shell.py` | COMPLETE | Add is the folder operation. No delete of originals. |
| 3 | Photo / video browsing | stills in the time window; `source_type=video` stored separately | `set_library_filter` | grid; Focus player | stills only | videos are not on this window | did not widen `ArchiveSession.window` SQL | stills exercised; video grid not listed | PARTIAL | Video rows have no Field list. |
| 4 | Search | `search.search_person`; board name match | `search` / `_search_people` | `searchField` | command to `resultText` | no people → empty copy | people search stays on the board | `submitCommand("ada")` | COMPLETE | Named-people search ran. Text search is row 15. |
| 5 | Similar items | `remember_and_find_region`, `search_similar_media` | `findSimilar`, `similar_media` | `similarAction`, strip | strip model | missing embeddings → unavailable | no identity score | region `findSimilar` passed; whole-image button not invoked | PARTIAL | Primary Similar control was not exercised against embeddings. |
| 6 | Time lens | `library_browse.timeline_buckets` | `browse("timeline")` | Days chip | buckets then `selectBucket` | empty → empty copy | in-canvas chip, not a rail | `setFacet("days")` + `selectBucket` | COMPLETE | Day bucket filtered the Field model. |
| 7 | Folder lens | `folder_buckets` | `browse("folders")` | Folders chip | same as days | empty → empty copy | chip, not a sidebar | adapter unit only; shell did not call `setFacet("folders")` | PARTIAL | UI exists. Live shell did not select it. |
| 8 | People workspace | `Application.board` | `openPeople` | People desk | people model | no run → empty copy | full-stage desk | people desk test | COMPLETE | Same session, not a second archive. |
| 9 | Unresolved items | `Application.inbox` | `unresolved` | `unresolvedLine` | counts on the desk | no run → empty | rejected hidden unless Advanced | line is bound; test did not assert inbox counts | PARTIAL | Copy is wired. Windows did not check the numbers. |
| 10 | Selection / batch | `review.split_cluster` | `splitSelectedFaces` | split faces | review.py | cannot split every face | review action, not auto-confirm | split test | COMPLETE | Batch is the face split. No media multi-confirm. |
| 11 | Image-based search | `search_similar_media` | `similar_media` | `findSimilarWhole` | strip | no embedding → unavailable | whole photo is not identity | adapter returned unavailable/empty; button not clicked | PARTIAL | Honest miss. Button not driven. |
| 12 | Region search | `remember_and_find_region` | `findSimilar` | drag release | strip | unavailable stays unavailable | existing region door | region similar test | COMPLETE | Drag door still calls Application. |
| 13 | Region selection | `ShellBridge.setRegion` | pixel rect | focus drag | normalized rect | no photo → no rect | existing | `setRegion` in shell tests | COMPLETE | Selection is the drawn rect. |
| 14 | SigLIP | `lens.probe_siglip`, `query_image` `visual_embedding` | `capabilities` | Ask photo; Capabilities | probe dict | missing weights → unavailable | no download | capabilities string returned; embed bytes not asserted | PARTIAL | Availability is reported. A vector was not shown. |
| 15 | Search modes | `ui_prefs` `people/text/whole/region` | `set_search_mode` | Settings | prefs JSON | whole/region tell you to open a photo | prefs, not schema | mode buttons not clicked | PARTIAL | Control exists. Windows did not switch modes. |
| 16 | Result inspection | `format_query_lines`, `Result.message` | `_apply_result` | `resultText` | property | primary copy is sanitized | existing result line | `resultText` asserted | COMPLETE | Inspection is the result line. |
| 17 | OCR | `lens.read_text` via `query_media` | inside Ask | Ask photo | lens lines | missing OCR → unavailable line | no new engine | `askPhoto` runs the lens door; OCR hit not asserted | PARTIAL | Door exists. This machine did not show a read. |
| 18 | Translation | `lens.translate_text` | inside Ask | Ask photo | lens lines | no source text → blocked | no download | not asserted | PARTIAL | Same lens door. No translation hit. |
| 19 | Description / VLM | `lens.describe_vlm` | inside Ask | Ask photo | lens lines | no local VLM → unavailable | no download | not asserted | PARTIAL | Probe can say unavailable. No description shown. |
| 20 | Barcode | `lens.read_symbology` | inside Ask | Ask photo | lens lines | missing reader → unavailable | no download | not asserted | PARTIAL | Same door. No barcode hit. |
| 21 | Text grounding | `lens.ground_selection` | inside Ask | Ask photo | lens lines | rectangular fallback is not a hit | existing | not asserted | PARTIAL | Grounding stays inside the lens report. |
| 22 | SAM2 | `lens.probe_sam2`, `visual.engine.capabilities` | `capabilities` | Capabilities | probe state | not ready → unavailable | SAM2 is not a FaceKit swap | `showCapabilities` ran; no mask drawn | PARTIAL | Availability only. No SAM2 action. |
| 23 | Saved text | `search.search_text` | `search("text")` | Search text | result text | no OCR rows → unavailable/empty | read-only | adapter test saw empty or unavailable | PARTIAL | Honest. Settings text mode was not clicked. |
| 24 | Named items | `Application.name_region` | `name_region` | none | — | — | no chrome without a control | not invoked | NOT EXPOSED | Symbol exists. No button. |
| 25 | Knowledge packs | `knowledge.load_pack` | `inspect_pack` | none | — | missing file → unavailable | slot only | not invoked | NOT EXPOSED | Local pack load has no settings row. |
| 26 | Named people | `review.name_cluster` | `decide("name")` | Name | board refresh | name required | review.py only | name test saved Ada | COMPLETE | Human name. Not a score. |
| 27 | Unnamed groups | board unnamed items | people model | review tint | `named == false` | unknown stays valid | not batch-confirmed | unnamed row in the people test | COMPLETE | Proposed treatment. Not auto-named. |
| 28 | Face review | `review.py` decisions | `decide` | desk actions | `identity.changed` on success | ReviewError shown | no second writer | name, merge, split, ignore, note | COMPLETE | Decisions go through review.py. |
| 29 | Name a person | `name_cluster` | `decide("name")` | name field | person row via review | empty name refused | approved workflow | Windows decide name | COMPLETE | Same as the name test. |
| 30 | Confirm / reject | `ignore_subject`, `rule_out_subject` | `decide` | Ignore, Rule out | review.py | no undo | reject is rule out | ignore ran; `rule_out` was not called | PARTIAL | Reject control exists. Windows did not fire it. |
| 31 | Unassigned faces | board count `unassigned` | `review_counts` | `reviewCounts` | count text | no run → empty | count from the board | text not asserted | PARTIAL | Not a client estimate, but not checked live. |
| 32 | Person detail | board members | `selectGroup` | desk detail | member list | missing group clears selection | same desk | `selectGroup` / evidence id | COMPLETE | Detail is the selected group. |
| 33 | Face-to-source | member media id | `openEvidence` | evidence | `openFocus` | missing media no-ops | same session | `openEvidence("m1")` | COMPLETE | Opens the source still. |
| 34 | Accurate review counts | `load_board` `counts` | `review_counts` | `reviewCounts` | named / groups / unassigned | no invented faces | board counts | not asserted | PARTIAL | Formula is the board. Windows did not read it. |
| 35 | Timeline / date nav | `timeline_buckets` | `selectBucket` | bucket row | filtered model | empty day list stays empty | chip | `selectBucket` after Days | COMPLETE | Date bucket changed the Field. |
| 36 | Moments | `moment_buckets` | `browse("moments")` | Moments chip, Advanced | buckets | no named moments → empty | hidden in Primary | not invoked | PARTIAL | Advanced entry exists. Not run. |
| 37 | Place lens | none | none | none | — | — | no simulated map | — | NOT IMPLEMENTED | EXIF `when_where` is not a place lens. |
| 38 | Similar-items lens | region similar | strip | `similarStrip` | thumb → focus | empty/unavailable notes | contextual strip | strip tests | COMPLETE | Lens is the strip, not a sidebar. |
| 39 | Unresolved lens | `inbox` | `unresolved` | people desk line | counts | rejected hidden by default | not a destination rail | not asserted | PARTIAL | Same gap as row 9. |
| 40 | Lens-to-focus | `open_focus` | `openFocus` | tile and strip | focus id | non-folder media refused by the session | same window | `openFocus` tests | COMPLETE | Focus replaces the Field in place. |
| 41 | Import / add folder | `submit_ingest` | `addFolder` | Add folder | job then library refresh | second submit is JobBusy | one engine | add-folder test | COMPLETE | Import is ingest. |
| 42 | Processing status | `Application.state` | `jobLabel` | processing mark | poll | idle shows nothing | existing | pause test sees running/paused | COMPLETE | Status matches the engine. |
| 43 | Progress / results | `ProgressEvent` | `job.progress` | label `current/total` when present | queued to the Qt thread | no invented percent | channel around the job API | event record not asserted in UI | PARTIAL | Channel exists. A fractional label was not shown in a test. |
| 44 | Pause / resume | `pause_job`, `unpause_job`, resume submit | `pauseJob`, `resumeJob` | job chrome | engine state | resume-after-cancel is a new submit | existing | pause/unpause/resume test | COMPLETE | Same job door. |
| 45 | Cancel | `cancel_job` | `cancelJob` | job chrome | `job.cancelled` | cancel is not success | existing | cancel test reaches idle | COMPLETE | Cooperative cancel. |
| 46 | Library health | `store.integrity_report` | `library_health` | Settings | `noticeText` | missing file → empty; problems → error | read-only | `libraryHealth()` notice | COMPLETE | Report text came back. Does not repair. |
| 47 | Check for new photos / rescan | `Application.submit_ingest(..., reprocess=True)` / `ShellBridge.rescanFolder()` | existing ingest job | Settings → Check for new photos | full ingest + cluster | full pipeline dependencies | existing JobEngine | not re-run for this snapshot | PARTIAL | User-facing broad reprocess exists. It is not category-scoped and must not be reused as a People/Objects/Regions/Words backfill. |
| 48 | Duplicate review | `duplicates.find_integrity_groups` | `duplicates` | Settings, Advanced | notice | OpenCV miss → unavailable | Advanced only | not invoked | PARTIAL | Button exists. Scan did not run. |
| 49 | Error reporting | failed `JobResult` | `_terminal_status` | “Last add failed” | job label | failure is not success | existing job result | no failed job in this run | PARTIAL | Path exists. No failure was produced. |
| 50 | Background activity | `Application.activity_memory` | `activity` | Settings | notice | no run → empty | read-only | not invoked | PARTIAL | Button exists. Not clicked. |
| 51 | Appearance | `save_theme_mode`; `tokens.py` | `tokens_for` | window, header, atmosphere picker | prefs | light id uses derived light tokens | blueprint tokens; named atmospheres still stored | atmosphere id persisted; pixels of every atmosphere not compared | PARTIAL | Tokens cover new chrome. Older hex remains. |
| 52 | Grid density | `save_grid_density` | `set_density` / `cycleDensity` | Settings; cell 220/160/110 | `cellSize` | unset shell key → cozy | JSON prefs, not a column | `cycleDensity` notice | COMPLETE | Cozy is selectable. Shared loader default stays comfortable. |
| 53 | Search preferences | `save_search_mode` | `set_search_mode` | Settings | prefs | unknown mode refused | prefs | not clicked | PARTIAL | Control exists. Not exercised. |
| 54 | GPU prefs | `save_prefer_gpu`, `select_execution_provider` | `set_gpu` | Settings, Advanced | next ingest `prefer_gpu` | no CUDA/DirectML/TensorRT → CPU copy | does not claim a GPU that is not listed | not clicked | PARTIAL | Honest CPU/GPU copy exists. Toggle not run. |
| 55 | Library preferences | `save_library_filter` | `set_library_filter` | Ctrl+1 | notice | videos → unavailable stills message | did not list video rows | not invoked | PARTIAL | Filter copy exists. Not invoked. |
| 56 | Capability availability | lens probes + `visual.engine.capabilities` | `capabilities` | Settings, Advanced | notice | missing tool → unavailable | no download | `showCapabilities()` | COMPLETE | The report ran and named the state. |
| 57 | Pack management | `install_model` | `install_model_file` | none | — | checksum miss does not replace | slot only | not invoked | NOT EXPOSED | Install function has no button. |
| 58 | Reset to defaults | `reset_app_to_defaults` | `reset_defaults` | Settings | prefs and caches cleared | library file kept | reset manifest | adapter test compared sqlite bytes; button not clicked | PARTIAL | Library preserved in the unit test. Button not driven. |
| 59 | Diagnostics | `diagnosticsText` | last shell event | Advanced status | result text | hidden in Primary | existing | `submitCommand("status")` contains `mode=advanced` | COMPLETE | Advanced diagnostics still render. |

## Honest gaps

- Offscreen Qt is the Windows exercise. No visible window was clicked through by a person.
- This process is emulated AMD64 on ARM64 Windows. It is not a native ARM64 or native x64 identity run.
- Full `pytest -q` for the whole repository was not re-run.
- Video browsing, rescan, places, detachable lightbox, and identity undo are not finished product surfaces.
- Named items and pack install have adapters and no chrome.
- Blueprint cozy is the shell default only when the density key is absent. Other clients still default to comfortable.

## Regressions

- `tests/test_native_shell.py` previously forbade a Similar label. That assertion now requires `similarAction` plus the existing strip and `findSimilar()` drag door.
- `GRID_DENSITIES` accepts `cozy`. Default of `load_grid_density()` is still `comfortable`. `tests/test_ui_prefs.py` passed.
- Native shell suite after the change: 25 passed.
- No schema, clustering, or identity-threshold edits.

## Git reconciliation

- Branch: `grok/frontend-blueprint-v3`
- Remote: not pushed
- Build commit: `f4db056` (local only)

## Verification log

```text
py -3.14 -c "import platform,os,sys; print(platform.platform()); print(platform.machine()); print(os.environ.get('PROCESSOR_ARCHITECTURE')); print(sys.executable)"
Windows-11-10.0.26200-SP0
ARM64
AMD64
C:\Users\S8633\AppData\Local\Python\pythoncore-3.14-64\python.exe

py -3.14 -m pytest tests/test_shell_adapter.py tests/test_native_shell.py::test_focus_qml_keeps_the_strip_and_a_primary_similar_action tests/test_ui_prefs.py -q --tb=line
15 passed in 2.89s

py -3.14 -m pytest tests/test_native_shell.py -q --tb=line
25 passed in 45.87s
```

Exit codes: 0, 0, 0.
