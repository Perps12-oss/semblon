# Frontend Blueprint v3 — annotated lock

**Date:** 2026-10-09  
**Branch:** `grok/frontend-blueprint-v3`  
**Status:** stack locked to the existing production shell. Candidate web stacks are rejected.

This file is a historical blueprint annotation (2026-10-09). It does not replace `docs/PRODUCT.md`, `docs/BUILD-STATUS.md`, or `docs/ARCHITECTURE.md`. `docs/SHELL-IA.md` is the retired Tk lock.

## §1.1 Stack lock

| Question | Decision | Evidence |
|---|---|---|
| Shell | PySide6 archive, `semblon shell` | `semblon/native_shell/run.py` `run_native_shell`; `semblon/native_shell/host.py` `build_shell`; `docs/ARCHITECTURE.md` |
| Runtime bridge | In-process `Application`. No HTTP, SSE, pipe, or stdio product bridge | `semblon/application.py` `Application`; `semblon/ipc_probe.py` is a probe, not the product door |
| UI framework | Qt Quick (`Shell.qml`) through `ShellBridge` | `semblon/native_shell/qml/Shell.qml`; `semblon/native_shell/bridge.py` |
| Adapter | One typed layer. QML calls `ShellBridge`. The bridge calls `ArchiveAdapter`. The adapter calls existing symbols | `semblon/native_shell/adapter.py` |
| Packaging | Checkout install `tools/install-windows.ps1` (`pip install -e ".[gui]"`). WiX MSI source exists; `wix build` was not run here | `docs/PACKAGING.md` |
| Windows baseline | **Not** “Windows 10 1809+”. Recorded host is Windows 11 `10.0.26200`. This process is AMD64 Python (`pythoncore-3.14-64`) on an ARM64 machine: **emulated**, not native | `platform.platform()` → `Windows-11-10.0.26200-SP0`; `platform.machine()` → `ARM64`; `PROCESSOR_ARCHITECTURE` → `AMD64`; `docs/runtime.md` |
| GPU states | CUDA / DirectML / TensorRT may be listed by ONNX Runtime. Otherwise CPU. Listed is not a proof the device runs | `semblon/engine.py` `select_execution_provider` |

**Lock:** production UI remains PySide6 → `Application` → domain / storage / providers. Field + Focus, archive first.

**Rejected:** React, Tauri, Electron, Zustand, a new HTTP backend, FastAPI, CustomTkinter, a permanent Tk AppShell, and any second application or storage path. The repository already has a shell, so blueprint §1.1 requires using it.

## Information architecture

`docs/SHELL-IA.md` says Model D is locked for the legacy Tk Home client and that production work is Field + Focus, not another Model D shell. `AGENTS.md` still forbids a permanent MAIN sidebar. The blueprint’s 48px icon rail conflicts with that ban.

**Resolution:** the rail was not built. Lenses are compact in-canvas chips on the same archive session: Memory, Days, Folders, and (Advanced only) Moments. People is a full-stage desk opened from the header, not a sidebar destination. Settings is a dismissible sheet. Similar floats on the open photo. There is no permanent right inspector on the Field.

Atmosphere ids still persist in `appearance.json`. New chrome uses the blueprint dark tokens (`semblon/native_shell/tokens.py`). The `light` atmosphere id uses a derived light set. Older controls still carry the previous mica hex. Named atmospheres are stored and do not each repaint the shell.

## §16 hypotheses

| Hypothesis | Result |
|---|---|
| Runtime bridge | **Confirmed.** In-process `Application`. No product HTTP/SSE/pipe/stdio. |
| Windows baseline | **Not 1809+.** Evidence is Windows 11 `10.0.26200`. This Python process is emulated AMD64 on ARM64. |
| Event channel `job.*` / `library.changed` / `identity.changed` | **Absent before this slice.** Added `semblon/native_shell/events.py` around `JobEngine` callbacks and review success. Not inside clustering or FaceKit. |
| Detachable lightbox | **NOT IMPLEMENTED.** Focus stays in the archive window. No detach API. No UI entry. |
| Map / Places | **NOT IMPLEMENTED** as a lens. `semblon/memory.py` `when_where` reads still EXIF. There is no place-bucket query. No UI entry. |
| Moments | **Backend exists.** `semblon/library_browse.py` `moment_buckets`. Advanced chip calls `ArchiveAdapter.browse("moments")`. Windows slot not invoked this run. |
| Identity undo | **NOT IMPLEMENTED.** No reversal function in `semblon/review.py`. No undo control. |
| Job pause / resume | **Exists and is wired.** `Application.pause_job` / `unpause_job`; resume-after-cancel is `submit_ingest(..., resume=True)`. |
| Job cancel | **Exists and is wired.** `Application.cancel_job`. |
| Knowledge-pack install | **Backend exists, UI not exposed.** `semblon/knowledge.py` `load_pack` and `semblon/model_install.py` `install_model`. Bridge slots `inspectPack` / `installModelFile` have no settings button. |

## §6 Capability symbols

Adapter: `semblon/native_shell/adapter.py` `ArchiveAdapter`.  
Bridge: `semblon/native_shell/bridge.py` `ShellBridge`.  
UI: `semblon/native_shell/qml/Shell.qml`.

Normal and Advanced labels match the task. Verdicts and the Windows log are in `SEMBLON_COMPLETION_MATRIX.md`. This table is the symbol map only.

| # | Capability | Backend symbol | Adapter | UI |
|---|---|---|---|---|
| 1 | Explore / Archive | `ArchiveSession.window` / `Application.archive_count` | `archive_summary` | Field `fieldGrid` |
| 2 | Folder management | `Application.submit_ingest` | bridge `addFolder` | Add folder |
| 3 | Photo / video browsing | stills: `ArchiveSession.window` (`source_type='folder'`); video rows exist as `source_type=video` | library filter | grid lists stills; Focus can play a video if one is opened |
| 4 | Search | `semblon/search.py` `search_person` (named people); board name match in `ShellBridge._search_people` | `search` | `searchField` |
| 5 | Similar items | `Application.remember_and_find_region`; `search_similar_media` | `similar_media`; bridge `findSimilar` | `similarAction`, `similarStrip` |
| 6 | Time lens | `library_browse.timeline_buckets` | `browse("timeline")` | Days chip |
| 7 | Folder lens | `library_browse.folder_buckets` | `browse("folders")` | Folders chip |
| 8 | People workspace | `Application.board` | bridge `openPeople` | People desk |
| 9 | Unresolved items | `Application.inbox` | `unresolved` | `unresolvedLine` |
| 10 | Selection / batch | `semblon/review.py` `split_cluster` | bridge `splitSelectedFaces` | face split on the desk |
| 11 | Image-based search | `search.search_similar_media` | `similar_media` | `findSimilarWhole` |
| 12 | Region search | `Application.remember_and_find_region` | bridge `findSimilar` | drag release |
| 13 | Region selection | `ShellBridge.setRegion` | — | focus drag |
| 14 | SigLIP | `lens.embed_siglip` / `probe_siglip`; `query_image` capability `visual_embedding` | `capabilities` | Ask photo; Capabilities |
| 15 | Search modes | `ui_prefs.save_search_mode` (`people`,`text`,`whole`,`region`) | `set_search_mode` | Settings |
| 16 | Result inspection | lens `format_query_lines`; adapter `Result.message` | `_apply_result` | `resultText`, `surfaceState` |
| 17 | OCR | `lens.read_text` via `Application.query_media` | `capabilities` | Ask photo |
| 18 | Translation | `lens.translate_text` | `capabilities` | Ask photo |
| 19 | Image description | `lens.describe_vlm` | `capabilities` | Ask photo |
| 20 | Barcode | `lens.read_symbology` | `capabilities` | Ask photo |
| 21 | Text grounding | `lens.ground_selection` | `capabilities` | Ask photo |
| 22 | SAM2 | `lens.probe_sam2`; `visual.engine.capabilities` | `capabilities` | Capabilities (availability) |
| 23 | Saved text | `search.search_text` over `kind='text'` items | `search("text")` | Search text mode |
| 24 | Named items | `Application.name_region` / `regions` | `name_region`, `regions` | **no control** |
| 25 | Knowledge packs | `knowledge.load_pack` | `inspect_pack` | **no control** |
| 26 | Named people | `review.name_cluster`; board `named` | people model | People desk |
| 27 | Unnamed groups | `Application.board` unnamed items | people model | review tint, not a confirmed batch |
| 28 | Face review | `review.py` name / merge / split / ignore / note / `rule_out_subject` | bridge `decide` | People desk |
| 29 | Name a person | `review.name_cluster` | bridge `decide("name")` | Name field |
| 30 | Confirm / reject | `ignore_subject`, `rule_out_subject` | bridge `decide` | Ignore, Rule out |
| 31 | Unassigned faces | `load_board` counts `unassigned` | `review_counts` | `reviewCounts` |
| 32 | Person detail | board members | `selectGroup` | desk detail |
| 33 | Face-to-source | board member `media_id` | `openEvidence` | evidence open |
| 34 | Review counts | `load_board` `counts` | `review_counts` | `reviewCounts` |
| 35 | Timeline / date nav | `timeline_buckets` | `selectBucket` | bucket row |
| 36 | Moments | `moment_buckets` | `browse("moments")` | Moments chip (Advanced) |
| 37 | Place lens | **no place-bucket function** | none | **no entry** |
| 38 | Similar-items lens | same as 5 | strip model | `similarStrip` |
| 39 | Unresolved lens | `Application.inbox` | `unresolved` | line on the people desk |
| 40 | Lens-to-focus | `ArchiveSession.open_focus` | `openFocus` | tile, strip, evidence |
| 41 | Import / add folder | `Application.submit_ingest` | bridge `addFolder` | Add folder |
| 42 | Processing status | `Application.state` | `jobLabel` | `processingMark` |
| 43 | Progress / results | `ProgressEvent` via `on_event` | `ShellEvents` `job.progress` | job label |
| 44 | Pause / resume | `pause_job` / `unpause_job` / resume submit | `pauseJob` / `resumeJob` | job chrome |
| 45 | Cancel | `cancel_job` | `cancelJob` | job chrome |
| 46 | Library health | `store.integrity_report` | `library_health` | Settings |
| 47 | Rescan | `process_folder(..., reprocess=True)` only. `Application.submit_ingest` does not pass `reprocess` | none | **no entry** |
| 48 | Duplicate review | `duplicates.find_integrity_groups` | `duplicates` | Settings, Advanced |
| 49 | Error reporting | `JobResult.status == failed` | `_terminal_status` | “Last add failed” |
| 50 | Background activity | `Application.activity_memory` | `activity` | Settings |
| 51 | Appearance | `ui_prefs.save_theme_mode`; tokens | `tokens_for` | atmosphere picker; blueprint tokens on window/header |
| 52 | Grid density | `ui_prefs.save_grid_density` including `cozy` | `set_density` | Settings. Sizes 220 / 160 / 110 |
| 53 | Search preferences | `save_search_mode` | `set_search_mode` | Settings |
| 54 | GPU prefs | `save_prefer_gpu`; `select_execution_provider` | `set_gpu` / `gpu_status` | Settings, Advanced. Next add passes `prefer_gpu` |
| 55 | Library preferences | `save_library_filter` | `set_library_filter` | Ctrl+1; videos report stills-only |
| 56 | Capability availability | lens probes + `visual.engine.capabilities` | `capabilities` | Settings, Advanced |
| 57 | Pack management | `install_model`, `load_pack` | `install_model_file`, `inspect_pack` | **no control** |
| 58 | Reset to defaults | `app_reset.reset_app_to_defaults` | `reset_defaults` | Settings. Does not delete the library |
| 59 | Diagnostics | bridge `diagnosticsText` plus last shell event | — | Advanced status |

### Identity

Proposed (unnamed) groups use the review tint and are not a confirmed multi-select. Confirmed (named) groups use the standard row. Rejected inbox faces stay out of the default unresolved line; Advanced includes the rejected count. Counts come from `load_board` / `inbox`, not a client guess. Undo is not offered.

### Density default conflict

Blueprint cozy (160) is the Qt shell default when `appearance.json` has no `grid_density`. `load_grid_density()` still falls back to `comfortable` for other clients. The key is presentation JSON, not a schema column.

## Not built, and why

- 48px rail and any permanent MAIN sidebar.
- Detachable lightbox, Places, identity undo.
- Rescan button (`reprocess` is not on `Application`).
- Named-item and pack buttons (symbols exist; no chrome, so they stay NOT EXPOSED).
- Video grid (time lens SQL stays `source_type='folder'`).
- A second shell, schema columns, clustering retune, or identity threshold change.
