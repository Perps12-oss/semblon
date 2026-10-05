# Module / Capability Registry

**Superseded 2026-10-05 by the completed PySide6 production migration.**

**Current (2026-10-05):** `Application` owns the only `JobEngine` and the archive session. Production UI is PySide6. `lens_home.py` and `review_chrome/` are deleted. Entries below that still say Tk Home is the production GUI are historical as of the 2026-09-28 commit they cite.

**Date:** 2026-09-28  
**Commit:** `35eeb72` (`35eeb72ede013ca8d61a78661e9fa9ba1a15c1f4`, `origin/main`, merge of PR #115)  
**Source audits:**

1. Forensic runtime / GUI data-flow audit: `docs/GUI-ARCHITECTURE-FORENSIC-AUDIT.md` (anatomy written against `142e36f`, retested 2026-09-28 against `646d44b` and unmerged PR #112 at `1c40dd0`).
2. Capability / module exposure audit: `docs/GUI-CAPABILITY-EXPOSURE-MATRIX.md` (tables from `142e36f`, same retest notes).

**Code check:** every row below was checked against the tree at `35eeb72`. Where an audit and the code disagree, the code wins and the conflict is noted.  
**Not done in this session:** pytest, a Windows Tk launch, or a live provider probe. “Works” in the matrix is therefore not a fresh execution claim. Owner Windows evidence that still applies is cited from `docs/COMPLETION-MATRIX.md` and was not re-run here.

**Identity firewall (given, not re-opened):** FaceKit / InsightFace is the only identity compare. Geometry, color, OCR, CLIP, objects, Lens results, visual segments, and knowledge-pack hits must not write `faces.person_id` or `embeddings.modality='face'`. `report` must not write the store. Cluster id is not person id.

**Known and recorded, not fixed:** Home’s Available / Optional strip and the Lens “Available understanding” list are a **static catalog**. They call `status_report()` with no probe overrides (`home_ui.py:2444`, `home_ui.py:1687`, `runtime_contract.py:554-560`). A file on disk does not change those rows.

---

## Audit conflicts resolved by the code

| Audit claim | Code at `35eeb72` |
|---|---|
| Forensic audit: no feature registry on `main`; `HOME_NAV` is a static tuple in `home_ui.py`. | `FeatureRegistry` is on `main` (`gui_registry.py:109`, `product_features.build_product_registry` at `product_features.py:306`). `HOME_NAV` is rebuilt from the registry (`home_ui.py:200-213`). |
| Exposure matrix: command palette is destinations only; context menu missing; watch, identify, person history, backup, and person-folder export are missing from the GUI. | Palette includes registry commands (`home_ui.py:1839`). More menu is registry overflow (`home_ui.py:1757-1765`). Identify, history, backup, watch, and export views are registered (`product_features.py:255-510`). A `"context"` surface is named (`gui_registry.py:27`) and **no widget queries it**. |
| Exposure matrix retest: open-vocabulary hover exists at `646d44b`; SAM 2 spatial runtime is not that file. | `visual_segment.py`, `visual_analyze.py`, and `sam2_runtime.py` are on `main`. Lens grounding (`lens.ground_selection`) and Canvas discovery (`sam2_runtime.generate_regions`) are two paths. |
| `docs/UI-EXPOSURE-MAP.md` still says the strip is “Ready / Not installed” and that folder watch is not in Home. | Strip titles are “Available” and “Optional · component required” (`home_shell.py:35-36`). More includes “Watch a folder…” which starts one ingest, not `watch.watch_folder`. |
| `product_exposure.py` lists “Live / Watch” as one SECONDARY surface (`product_exposure.py:118-122`). | Live calls `run_live_overlay`. Watch-in-More calls `_start_process` (`product_features.py:255-276`). |

The exposure matrix’s hidden-register “when” column is product intent. This file does not adopt those proposals.

---

## Capability registry

Fields are the same for every entry. “State at `35eeb72`” means what the source shows. Runtime execution on Windows is “needs verification” unless an owner record is named.

### Shell and navigation

#### `product-home`

*Historical entry (commit `35eeb72`). Not the 2026-10-05 production UI. `lens_home.py` is deleted. The production door is `semblon shell` → `Application`.*

- **Label:** Semblon (window title). Sidebar Photos is the landing, not a separate app.
- **What it is:** The production GUI: one Tk process started by `semblon home`.
- **Where implemented:** `cli.py:1177-1181` `run_product_home`; `lens_home.py:102-107` installs the region mouse-up handler then `run_home_ui`; `home_ui.py` `HomeApp`.
- **Owner:** Home shell.
- **What it exposes:** CLI `semblon home`; double-click script `tools/semblon-interactive.ps1` (forensic audit).
- **Where the user accesses it:** The product window.
- **Dependencies:** Tk; default store `process.default_store_path` (CLI help: `%LOCALAPPDATA%\Semblon\store.sqlite`).
- **Persistence:** The library SQLite file. The window itself is not persisted.
- **Tests that prove it:** `tests/test_product_exposure.py` `test_canonical_entry_is_tk_home`, `test_interactive_launcher_opens_home_only`. Not re-run here.
- **Platform:** Windows is the product target. Tk can start elsewhere; this session did not start it.
- **State at `35eeb72`:** Present. Owner record: production GUI = tk Home **COMPLETE**; APP-1 C.3 **VERIFIED ON WINDOWS** 2026-09-22 (`docs/COMPLETION-MATRIX.md`). Not re-executed at this commit.
- **Notes:** `HomeApp` still owns chrome, settings, and inspector verbs. The registry feeds nav, More, palette, and some inspector buttons. It is not a plugin host (`gui_registry.py:1-8`).

#### `qt-shell`

- **Label:** none inside Tk Home.
- **What it is:** Optional PySide6 window, not product Home.
- **Where implemented:** `cli.py` parser `shell`; `native_shell/run.py`.
- **Owner:** Optional shell.
- **What it exposes:** CLI `semblon shell`.
- **Where the user accesses it:** CLI only. Not advertised in Tk Home.
- **Dependencies:** extra `[gui]` / PySide6.
- **Persistence:** Reads the same store. Does not replace tk Home.
- **Tests:** `tests/test_product_exposure.py` class coverage includes OPTIONAL. Not re-run here.
- **Platform:** Cross-platform only if PySide6 is installed. Product claim is Windows.
- **State at `35eeb72`:** KEEP optional (`product_exposure.py:125-129`, completion matrix).
- **Notes:** Audits say do not add features only here.

#### `review-ui`

- **Label:** Open Review.
- **What it is:** Secondary Toplevel for name, merge, split, ignore, note, and rule-out, including track rows.
- **Where implemented:** `review_ui.py` `ReviewApp`; command `shell.open_review` in `product_features.py:501-504`; `review.py` decision writers.
- **Owner:** Review.
- **What it exposes:** More menu, Ctrl+K, CLI `semblon review-ui`.
- **Where the user accesses it:** More → Open Review.
- **Dependencies:** A processed run; FaceKit embeddings already stored.
- **Persistence:** `decisions`, `persons`, `cluster_person`, `faces.person_id` when naming. Notes are decisions.
- **Tests:** `tests/test_review.py` (name, merge, split, ignore, note, track). `tests/test_jobs.py` `test_review_root_is_toplevel_on_parent`. Not re-run here.
- **Platform:** Tk. Windows is the owner record.
- **State at `35eeb72`:** Present, demoted. Forensic audit still matches the Toplevel shape.
- **Notes:** Home inspector has no Note button. Review does (`review_ui` note control; exposure audit).

#### `feature-registry`

- **Label:** none (internal).
- **What it is:** In-process map of nav contributions, routes, and `GuiCommand`s.
- **Where implemented:** `gui_registry.py` `FeatureRegistry`, `default_registry`; seed `product_features.build_product_registry`; Activity page `features/activity_feature.py`.
- **Owner:** Home shell.
- **What it exposes:** No user control. Shell loops `commands(surface=...)`.
- **Where the user accesses it:** Not exposed. Effects show up as sidebar, More, Ctrl+K, and extra inspector buttons.
- **Dependencies:** None beyond Home.
- **Persistence:** None. Process memory (`gui_registry.py:109-111`).
- **Tests:** `tests/test_gui_registry.py` (12 tests, including `test_product_registry_matches_home_nav_shape`, `test_overflow_and_palette_consume_registry`, `test_product_commands_expose_hidden_capabilities`). Not re-run here.
- **Platform:** Cross-platform Python.
- **State at `35eeb72`:** On `main`. The forensic audit’s “no registry” sentence is stale (it described `main` before PR #112).
- **Notes:** `CapabilitySpec` and `GUI_PATHS` stay separate catalogs (`gui_registry.py:5-6`). `register_demo_feature` is a test hook (`product_features.py:519`).

#### `command-palette`

- **Label:** none on screen until Ctrl+K. Settings lists the shortcut.
- **What it is:** Jump list of nav labels plus palette commands.
- **Where implemented:** `home_ui.py:1810` `_open_command_palette`; bind `home_ui.py:992`.
- **Owner:** Home shell.
- **What it exposes:** Keyboard shortcut.
- **Where the user accesses it:** Ctrl+K. Listed under Settings → Advanced (exposure audit; shortcut list still in settings build).
- **Dependencies:** Registry palette surface.
- **Persistence:** None.
- **Tests:** `tests/test_gui_registry.py` `test_overflow_and_palette_consume_registry`. Not re-run here.
- **Platform:** Tk.
- **State at `35eeb72`:** Palette includes actions, not only destinations. There is still no visible “command” button.
- **Notes:** Commands that `requires_context` are skipped when the current inspector context cannot satisfy them (`home_ui.py:1842`).

#### `context-command-surface`

- **Label:** none.
- **What it is:** A declared command surface `"context"` with no menu binding.
- **Where implemented:** `gui_registry.py:27`; several `GuiCommand.surfaces` include `"context"` (`product_features.py:323-335`, `451-461`).
- **Owner:** Home shell.
- **What it exposes:** None. Grep of `semblon/` finds no `surface="context"` consumer and no `Button-3` binding.
- **Where the user accesses it:** Not exposed.
- **Dependencies:** Would need a menu that asks the registry for `surface="context"`.
- **Persistence:** None.
- **Tests:** `test_command_discovery_by_surface` can see the surface in the registry. No test of a real menu was found in that file’s name list.
- **Platform:** n/a.
- **State at `35eeb72`:** Still unwired. Matches the exposure audit’s note on PR #112, which is now merged.
- **Notes:** Do not describe this as a context menu.

#### `keyboard-shortcuts`

- **Label:** Settings → Advanced shortcut lines (Ctrl+F, Ctrl+1…5, Ctrl+K).
- **What it is:** Focus search and switch sidebar sections.
- **Where implemented:** `home_ui.py` binds; nav shortcuts come from `NavContribution.shortcut` (`product_features.py`: Photos 1, Videos 2, People 3, People to name 4, Recent activity 5). Lens has no number.
- **Owner:** Home shell.
- **What it exposes:** Keys, listed in Settings.
- **Where the user accesses it:** Keyboard. Discoverable only if the user opens Settings → Advanced.
- **Dependencies:** Registry nav order.
- **Persistence:** None.
- **Tests:** Registry nav-shape test. Not re-run here.
- **Platform:** Tk.
- **State at `35eeb72`:** Present.
- **Notes:** UI-EXPOSURE-MAP still points at a hard-coded `HOME_NAV` line range that is no longer the source of labels.

#### `theme`

- **Label:** System / Light / Atmospheres (Mica Dark, Cyber Obsidian, Neon Ember, Tokyo Synth).
- **What it is:** Appearance preference — Atmosphere & Motion System (`docs/ATMOSPHERE.md`).
- **Where implemented:** `ui_prefs.py` `load_theme_mode` / `save_theme_mode` / `resolve_atmosphere_id`; `atmosphere.py` + `atmosphere_render.py`; Settings workspace Appearance + PreviewTheatre tiles in `home_ui.py` (`_fill_settings_body`).
- **Owner:** Home shell.
- **What it exposes:** Settings → Appearance.
- **Where the user accesses it:** Settings.
- **Dependencies:** On “System”, Windows theme registry when readable; otherwise light. Stored `dark` aliases to `mica_dark`.
- **Persistence:** `appearance.json` beside the library file (`ui_prefs.py`). Shared JSON also holds `grid_density`, `search_mode`, `library_filter`, `prefer_gpu`. Machine continuity keys `last_store` / `window_geometry` live in the default Semblon data-dir `appearance.json`. Not a SQLite column.
- **Tests:** `tests/test_atmosphere.py`, `tests/test_ui_prefs.py`, `tests/test_ui_prefs_continuity.py`.
- **Platform:** File write is cross-platform. “System” matching Windows theme is Windows-only; elsewhere it resolves to light.
- **State at `35eeb72`:** Present (extended on atmosphere branch).
- **Notes:** Opaque Tk — no Windows Mica/Acrylic APIs. Theme save merges; it must not wipe sibling keys. Reset removes the library `appearance.json` (canonical defaults = absent keys).

#### `settings-library`

- **Label:** Change… (library file).
- **What it is:** Point Home at a different `store.sqlite`.
- **Where implemented:** `home_ui.py` `_settings_change_library`; Settings workspace `_show_settings` / `_fill_settings_body` (in-shell route, not a popup).
- **Owner:** Home shell.
- **What it exposes:** Settings control.
- **Where the user accesses it:** Settings.
- **Dependencies:** An existing SQLite library file.
- **Persistence:** `last_store` in machine `appearance.json` (`ui_prefs.save_last_store` / `resolve_home_store`). Explicit CLI/`store=` still wins.
- **Tests:** `tests/test_ui_prefs_continuity.py`.
- **Platform:** Cross-platform file dialog via Tk.
- **State at `35eeb72`:** Present.
- **Notes:** Asks for `store.sqlite` (exposure audit). This session did not click the dialog.

#### `settings-reset`

- **Label:** Reset app.
- **What it is:** Factory-reset-like clear of Semblon-owned rebuildable application state (prefs + sidecars). Does **not** delete original media, library folders, identity decisions, notes, or saved regions.
- **Where implemented:** `semblon/app_reset.py` (`reset_app_to_defaults`, `RESET_MANIFEST`); Settings UI in `home_ui.py` `_reset_app_to_defaults` / `_fill_settings_body` Reset section; copy in `product_surface.py` (`SETTINGS_RESET_*`).
- **Owner:** Application operation (Settings invokes it; UI does not delete files itself).
- **What it exposes:** Settings → Advanced → Recovery → Reset app.
- **Where the user accesses it:** Settings Advanced (on-demand; confirmation required). Not an everyday top-level section.
- **Dependencies:** Active library store path for sidecar locations.
- **Persistence cleared:** library `appearance.json` (theme, grid_density, search_mode, library_filter, prefer_gpu; and machine keys when that file is the default-dir prefs), `visual_cache/`, `*.semblon-index.npz`, `review.html`, `home_completion*` schema_meta keys. Canonical defaults = missing keys (`system` / `comfortable` / `people` / `all` / unset GPU).
- **Persistence preserved:** `store.sqlite` media index, persons/faces/decisions, user_region items, embeddings in SQLite, model weights, user media paths. Machine `last_store` / `window_geometry` survive Reset of a non-default library.
- **Tests:** `tests/test_app_reset.py`, `tests/test_settings_contributions.py`, `tests/test_ui_prefs_continuity.py`.
- **Platform:** Cross-platform path clears; Home confirm dialog is Tk.
- **Notes:** Idempotent. Stage caches first; restore prefs only if cache clear succeeds. No second settings/cache architecture.

#### `diagnostics`

- **Label:** Diagnostics.
- **What it is:** Engineering readout of runtime, providers, models, schema, and jobs.
- **Where implemented:** `advanced_diagnostics.py`; Settings button `home_ui.py:4245` region.
- **Owner:** Diagnostics.
- **What it exposes:** Settings → Diagnostics.
- **Where the user accesses it:** Settings, buried. Not the sidebar.
- **Dependencies:** Store and provider probes used by that module.
- **Persistence:** Read-only display.
- **Tests:** Not re-run here. Exposure audit cites the module.
- **Platform:** Cross-platform readout; GPU/provider lines depend on the machine.
- **State at `35eeb72`:** Present.
- **Notes:** This is not the Home capability strip. Diagnostics may probe; the strip does not.

#### `empty-states`

- **Label:** Per-route sentences (Photos, Videos, People, Activity, Lens).
- **What it is:** Copy when a workspace has nothing to show.
- **Where implemented:** `empty_states.py`; used from page builders in `product_features.py` and Activity.
- **Owner:** Home shell.
- **What it exposes:** Inspector / workspace text.
- **Where the user accesses it:** The empty route itself.
- **Dependencies:** None.
- **Persistence:** None.
- **Tests:** `tests/test_product_exposure.py` `test_people_unknown_copy_avoids_uuid_and_keeps_unknown_valid`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present.
- **Notes:** Unknown remains valid copy on People to name.

#### `capability-honesty-strip`

- **Label:** Available / Optional · component required. Row labels come from `CapabilitySpec.label`.
- **What it is:** Landing cards that list catalog states.
- **Where implemented:** `home_shell.capability_sections` (`home_shell.py:60-105`); painted in `_refresh_library_shell` (`home_ui.py:2444`) **with no report argument**.
- **Owner:** Runtime contract, drawn by Home.
- **What it exposes:** Landing text only. No install button, no toggle.
- **Where the user accesses it:** Sidebar Photos (route `home`), the library landing.
- **Dependencies:** `default_catalog()` defaults. Tracked ids: `visual_embedding`, `ocr`, `translation`, `grounding`, `barcode`, `vlm`, `lkg`, `screen_capture` (`home_shell.py:18-27`). `library_query` is the only ready-by-default id (`home_shell.py:14`).
- **Persistence:** None. Recomputed from defaults every refresh.
- **Tests:** `tests/test_home_shell.py` `test_capability_sections_list_missing_models` (asserts catalog defaults, including that `ann_index` is absent). Not re-run here.
- **Platform:** The painted state does not depend on OS. That is the defect relative to a live check.
- **State at `35eeb72`:** Static catalog. Confirmed.
- **Notes:** `_state_label` (`home_shell.py:46-56`): AVAILABLE → Available; MISSING → Optional · install needed; DISABLED → Experimental; UNSUPPORTED_RUNTIME → Optional · not supported here. The module docstring still says “Ready vs Not installed” (`home_shell.py:3-4`, `:65`). `face`, `landmark`, `logo`, `product`, and `ann_index` are in the catalog and not on this strip. `tests/test_home_shell.py:33` asserts `ann_index` is not a tracked row.

#### `lens-honesty-rows`

- **Label:** Available understanding.
- **What it is:** The same catalog states, fewer ids, on the Lens page.
- **Where implemented:** `home_shell.lens_understanding_rows` (`home_shell.py:165`); call with no probe report `home_ui.py:1687`. Ids: ocr, barcode, grounding, visual_embedding, translation, vlm, lkg (`home_shell.py:154-162`).
- **Owner:** Lens presentation.
- **What it exposes:** Text rows beside the Lens workspace.
- **Where the user accesses it:** Sidebar Lens, and the top Lens button.
- **Dependencies:** Same `status_report()` defaults.
- **Persistence:** None.
- **Tests:** `tests/test_product_exposure.py` `test_lens_lines_use_plain_labels_not_internal_ids`. Not re-run here.
- **Platform:** Same as the strip: labels are cross-platform; states are not live.
- **State at `35eeb72`:** Static catalog. Screen capture is not in `_LENS_IDS`.
- **Notes:** A successful Lens query can still show an honest last-result card via `last_result_copy` (`home_shell.py:132`). That card is about the last ask, not about whether a weight file exists.

### Ingest and jobs

#### `add-folder-ingest`

- **Label:** Add a photo folder / Add another folder (landing CTA).
- **What it is:** Detect, embed, and cluster a folder through the Home job door.
- **Where implemented:** `JobEngine.submit_ingest` (`jobs.py`); `process_folder`; Home `_start_process`. Landing CTA plan in `home_ui.py` around `landing_cta_plan` (`home_ui.py:330` region).
- **Owner:** Ingest / JobEngine.
- **What it exposes:** Landing button; CLI `semblon process` and `semblon ingest`.
- **Where the user accesses it:** Photos landing and the job bar.
- **Dependencies:** FaceKit weights; OpenCV; ONNX Runtime. Optional observers are not the default Home set.
- **Persistence:** `runs`, `media`, `observations`, `faces`, `clusters`, and non-face `observation_items` / `embeddings` when observers run.
- **Tests:** `tests/test_jobs.py` `test_home_submits_through_job_engine`. Broader ingest tests exist. Not re-run here.
- **Platform:** Windows x64 is the S1 path. ARM64 OpenCV load is **BLOCKED** (`docs/COMPLETION-MATRIX.md`). Do not silent-swap.
- **State at `35eeb72`:** Owner record VERIFIED ON WINDOWS 2026-09-22 for live Home ingest. Not re-run at this commit.
- **Notes:** Home observers string is `face,color,object` (`home_ui.py:195`).

#### `incremental-sha256-skip`

- **Label:** none.
- **What it is:** Skip a file whose sha256 is already stored.
- **Where implemented:** `ingest.py` `media_skip_reason` (exposure audit cites `ingest.py:145-158`); `media` UNIQUE sha256 (`store.py:38` region).
- **Owner:** Ingest.
- **What it exposes:** No browser of duplicates. Skip is silent policy.
- **Where the user accesses it:** Not exposed.
- **Dependencies:** Ingest.
- **Persistence:** The existing `media` row is what makes the skip stick.
- **Tests:** Ingest skip tests landed with the forensic media-skip fixes (history). Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present. There is still no duplicate-file screen (exposure audit “Duplicate file browser: No”).
- **Notes:** Not a library view.

#### `resume-ingest`

- **Label:** Resume (progress chrome, when a resumable run exists).
- **What it is:** Continue an interrupted process.
- **Where implemented:** `process.find_resumable_run`; CLI `--resume`; Home resume control (exposure audit `home_ui.py:3286` region — line may have moved; control states are `home_control_states` at `home_ui.py:357`).
- **Owner:** Ingest.
- **What it exposes:** CLI flag and a progress-bar control.
- **Where the user accesses it:** Progress chrome, only in the resumable state.
- **Dependencies:** An unfinished run in `runs`.
- **Persistence:** Run rows and per-file progress in the store.
- **Tests:** Job pause/cancel tests. Resume-after-cancel is described in `home_control_states` (`home_ui.py:366`). Not re-run here.
- **Platform:** Same as ingest.
- **State at `35eeb72`:** Present.
- **Notes:** Resume while paused unpauses the same job; resume while idle resumes after cancel (`home_ui.py:366`).

#### `pause-cancel`

- **Label:** Pause / Cancel.
- **What it is:** Stop between files, or hold the job gate.
- **Where implemented:** `JobEngine.pause` / `cancel`; `Application.pause_job` / `cancel_job` (`application.py:207-213`).
- **Owner:** JobEngine.
- **What it exposes:** Progress chrome.
- **Where the user accesses it:** The job strip while a job runs.
- **Dependencies:** An active ingest job.
- **Persistence:** Cancel leaves a resumable run. Pause is process memory.
- **Tests:** `tests/test_jobs.py` `test_pause_blocks_until_unpause`, `test_cancel_while_paused`, `test_home_pause_and_unpause_wired`. Not re-run here.
- **Platform:** Windows verification is the APP-1 C.3 record.
- **State at `35eeb72`:** Present. APP-1 C.2 **COMPLETE** in the matrix.
- **Notes:** Visual analysis uses a separate lock and can run beside ingest (`jobs.py:329-343`).

#### `gpu-preference`

- **Label:** Settings processing checkbox (string `SETTINGS_GPU`), only if a GPU execution provider is reported.
- **What it is:** Prefer a GPU ONNX execution provider for FaceKit when one is listed.
- **Where implemented:** `engine.select_execution_provider`, `product_prefer_gpu`; checkbox `home_ui.py:4151-4174`; applied in `_effective_prefer_gpu` (`home_ui.py:3483`).
- **Owner:** Engine.
- **What it exposes:** Settings checkbox or a CPU sentence.
- **Where the user accesses it:** Settings → Processing.
- **Dependencies:** ONNX Runtime providers (CUDA / DirectML / TensorRT per `engine.py:111` comment).
- **Persistence:** None across restart. `_prefer_gpu_user` is an instance field (`home_ui.py:904`). Next launch calls `product_prefer_gpu()` again.
- **Tests:** Engine provider tests may exist; not executed here.
- **Platform:** The checkbox appears only when `select_execution_provider(prefer_gpu=True)["gpu"]` is true. That check is live, unlike the capability strip.
- **State at `35eeb72`:** Present. Whether this machine has a GPU EP was not queried.
- **Notes:** CLI `--prefer-gpu` is the script door. Needs verification on Windows ARM64 vs x64.

#### `progress-events`

- **Label:** Progress sentences on the processing pane.
- **What it is:** `on_event` progress spine.
- **Where implemented:** `progress.py`; Home consumes events (forensic audit cites the processing pane).
- **Owner:** Jobs.
- **What it exposes:** Progress copy.
- **Where the user accesses it:** Home while a job runs.
- **Dependencies:** JobEngine.
- **Persistence:** None beyond run rows.
- **Tests:** Job tests that pass `on_event`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Retained (AGENTS.md). Needs verification of the exact Home copy at this commit.
- **Notes:** Visual jobs can emit a `stage="visual"` event (`jobs.py:320`).

#### `worker-count`

- **Label:** none.
- **What it is:** CLI `--workers` / `--reprocess` for ingest throughput and forced redo.
- **Where implemented:** `cli.py` ingest/process flags; `ingest.py`.
- **Owner:** Ingest.
- **What it exposes:** CLI flags only.
- **Where the user accesses it:** CLI only.
- **Dependencies:** Ingest.
- **Persistence:** Reprocess rewrites embeddings (exposure audit). Worker count is not a stored preference.
- **Tests:** Worker harness docs `docs/PERF-WORKERS-HARNESS.md`. Default remains 1 until an owner Windows gate.
- **Platform:** Windows. Do not raise the default from this file.
- **State at `35eeb72`:** **COMPLETE** with product default **1** (completion matrix).
- **Notes:** Not a Settings control. Exposure audit says keep it out of the product UI.

### Identity and review

#### `facekit`

- **Label:** No “FaceKit” control. Users see faces, groups, and people.
- **What it is:** Detect and embed faces. The only identity engine.
- **Where implemented:** `providers.py` `FaceKitProvider`; `engine.py` `load_app`; ingest writes `faces`.
- **Owner:** FaceKit.
- **What it exposes:** Indirectly, via Photos, People, Review, and canvas boxes. Catalog id `face` (`runtime_contract.py:131-137`) is **not** a Home strip row. Its `default_model` is `MISSING`, which is the static catalog value, not a probe of local weights.
- **Where the user accesses it:** Photos / People / Review / canvas outlines.
- **Dependencies:** Local buffalo-family weights. `pack_id` includes weight hashes. `buffalo_l` is a family name, not the compare key. Redistribution is **UNAVAILABLE** (completion matrix).
- **Persistence:** `faces.embedding`, `faces` rows, mirrored `observation_items` via `observers.ensure_face_item` (`observers.py:722`).
- **Tests:** Ingest and identify tests. Schema contract: face embeddings are not `embeddings.modality='face'` (`observers.py:449` region, `compare.py`). Not re-run here.
- **Platform:** Windows x64 cv2 for S1. ARM64 OpenCV load **BLOCKED**.
- **State at `35eeb72`:** Identity gates CLOSED. Do not retune.
- **Notes:** Catalog default `MISSING` must not be read as “FaceKit is absent from the product.”

#### `dbscan`

- **Label:** “groups” on result copy. No eps control.
- **What it is:** Group still-photo faces with frozen DBSCAN.
- **Where implemented:** `cluster.cluster_run` (`cluster.py:206`). Home runs it inside `process_folder`.
- **Owner:** Cluster.
- **What it exposes:** CLI `semblon cluster` with eps flags. GUI shows groups, not parameters.
- **Where the user accesses it:** Result of Add folder. Parameters are CLI only.
- **Dependencies:** FaceKit embeddings; frozen `eps=0.40`, `min_samples=2`, stills only (`docs/S1-GOLDEN.md`).
- **Persistence:** `clusters`, `faces.cluster_id`. Does not create `persons` (`tests/test_review.py` `test_cluster_run_does_not_create_persons`).
- **Tests:** `tests/test_cluster.py` (not re-read function-by-function here) and `test_cluster_run_does_not_create_persons`. Not re-run here.
- **Platform:** Cross-platform given embeddings. S1 golden is a Windows evidence record.
- **State at `35eeb72`:** Frozen. Do not retune to shrink unassigned. Video DBSCAN stays off.
- **Notes:** Cluster id is not person id.

#### `name-person`

- **Label:** Name this person.
- **What it is:** Create or attach a person from a cluster or one face.
- **Where implemented:** `review.name_cluster` (`review.py:332`), `review.name_face` (`review.py:423`); inspector `apply_inspector_name` (`inspector_verbs.py:357`); button `home_ui.py:1295`.
- **Owner:** Review.
- **What it exposes:** Inspector primary button; Review; CLI `semblon name`.
- **Where the user accesses it:** Inspector when a face or group is selected; Review.
- **Dependencies:** A selected cluster or face; display name typed by the user.
- **Persistence:** `persons`, `cluster_person`, `faces.person_id`, `decisions`.
- **Tests:** `tests/test_review.py` `test_name_creates_person_and_decision`. Not re-run here.
- **Platform:** Cross-platform store logic. GUI needs Tk.
- **State at `35eeb72`:** Present. Naming is manual. Identify does not auto-assign.
- **Notes:** Same display name can create distinct persons (`test_name_same_display_creates_distinct_persons`).

#### `name-faces-batch`

- **Label:** none in Home.
- **What it is:** Name several unassigned faces in one CLI call.
- **Where implemented:** `review.name_faces` (`review.py:498`); CLI `semblon name --faces`.
- **Owner:** Review.
- **What it exposes:** CLI only.
- **Where the user accesses it:** CLI only.
- **Dependencies:** Unassigned faces. Refuses clustered faces (`test_name_faces_refuses_clustered`).
- **Persistence:** Same person tables as name.
- **Tests:** `tests/test_review.py` `test_name_faces_refuses_clustered`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** CLI. Exposure audit still accurate.
- **Notes:** Not an inspector verb.

#### `name-track`

- **Label:** Review track row name control.
- **What it is:** Name a derived video track as a person without treating the track as a cluster.
- **Where implemented:** `review.name_track` (`review.py:628`); Review UI track cards.
- **Owner:** Review.
- **What it exposes:** CLI `semblon name` track path; Review UI. Not the Home inspector.
- **Where the user accesses it:** Review, or CLI.
- **Dependencies:** `tracks` rows.
- **Persistence:** Person link on track members, plus a decision.
- **Tests:** `tests/test_review.py` `test_name_track_enrols_members_not_as_cluster`, `test_cli_name_track`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present. No Home track lane.
- **Notes:** A track is not a person until this command.

#### `assign-person`

- **Label:** Add to person.
- **What it is:** Attach the selection to an existing person.
- **Where implemented:** `inspector_verbs.apply_inspector_assign` (`inspector_verbs.py:364`); `review` attach path; CLI `--attach-to`.
- **Owner:** Review.
- **What it exposes:** Inspector button.
- **Where the user accesses it:** Inspector, after a person exists.
- **Dependencies:** `persons` rows; selection.
- **Persistence:** `cluster_person` / `faces.person_id` / `decisions`.
- **Tests:** `test_name_attach_to_reuses_person`. Not re-run here.
- **Platform:** Cross-platform store; Tk for the button.
- **State at `35eeb72`:** Present.
- **Notes:** Label does not say “cluster”.

#### `merge-groups`

- **Label:** Combine face groups.
- **What it is:** Merge clusters. The merge is a review correction, not a new person.
- **Where implemented:** `review.merge_clusters` (`review.py:662`); `apply_inspector_merge`.
- **Owner:** Review.
- **What it exposes:** Inspector; Review; CLI `semblon merge` and `semblon review merge`.
- **Where the user accesses it:** Inspector when more than one group can be combined; Review.
- **Dependencies:** Two clusters; refuses different persons (`test_merge_rejects_different_persons`).
- **Persistence:** Cluster membership and a `decisions` row. Survives recluster (`test_merge_is_not_a_person_and_survives_recluster`).
- **Tests:** `tests/test_review.py` merge tests. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present.
- **Notes:** Label is about groups, which matches the code.

#### `split-faces`

- **Label:** Split faces.
- **What it is:** Move selected faces into a new cluster.
- **Where implemented:** `review.split_cluster` (`review.py:779`); `apply_inspector_split`.
- **Owner:** Review.
- **What it exposes:** Inspector; Review; CLI `semblon split`.
- **Where the user accesses it:** Inspector. Status text tells the user to open Review to compare (exposure audit). Full-face compare before split is still Review.
- **Dependencies:** A face selection inside a cluster.
- **Persistence:** Cluster membership; clears person on moved faces (`test_split_clears_person_on_moved_faces`).
- **Tests:** `tests/test_review.py` split tests. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present. Easy to miss, as the exposure audit said.
- **Notes:** Does not auto-split.

#### `ignore`

- **Label:** Ignore.
- **What it is:** Mark a subject so it is not treated as a person to name.
- **Where implemented:** `review.ignore_subject` (`review.py:892`); `apply_inspector_ignore`.
- **Owner:** Review.
- **What it exposes:** Inspector; Review; CLI `semblon review ignore`.
- **Where the user accesses it:** Inspector and Review.
- **Dependencies:** A selected subject.
- **Persistence:** `decisions`. Ignored clusters refuse name (`test_name_refuses_ignored_cluster`).
- **Tests:** `test_ignore_and_note_export_without_person`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present.
- **Notes:** Separate from rule-out. The GUI confirm path does not offer a disposition.

#### `ignore-disposition`

- **Label:** none in the GUI. CLI `--as`.
- **What it is:** Ignore as `not_a_person`, singleton, or junk.
- **Where implemented:** `review.ignore_subject` disposition argument; CLI `review ignore --as` (parser near `cli.py:418`).
- **Owner:** Review.
- **What it exposes:** CLI only.
- **Where the user accesses it:** CLI only.
- **Dependencies:** Ignore.
- **Persistence:** Decision payload.
- **Tests:** Review ignore CLI test `test_cli_review_merge_ignore`. Disposition coverage needs verification beyond that name.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** CLI. Exposure audit still accurate.
- **Notes:** Home Ignore does not ask for a reason.

#### `review-note`

- **Label:** Note (Review only).
- **What it is:** A durable review note that is not an identity.
- **Where implemented:** `review.note_subject` (`review.py:978`); Review UI.
- **Owner:** Review.
- **What it exposes:** Review button; CLI `semblon review note`. No Home inspector button in the verb block (`home_ui.py:1284-1346`).
- **Where the user accesses it:** Review, or CLI.
- **Dependencies:** A subject.
- **Persistence:** `decisions`.
- **Tests:** `test_ignore_and_note_export_without_person`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present, not on the Home inspector.
- **Notes:** Exposure audit “Now” proposal was not implemented as an inspector command.

#### `rule-out`

- **Label:** Not this person.
- **What it is:** Record that a subject is not a chosen person. Default ON.
- **Where implemented:** `review.rule_out_subject` (`review.py:1057`); `gates.RULED_OUT`; `apply_inspector_rule_out`.
- **Owner:** Review.
- **What it exposes:** Inspector destructive button; Review; CLI `semblon review` rule-out parser (`cli.py:426`).
- **Where the user accesses it:** Inspector and Review.
- **Dependencies:** An active person. Opt out with `SEMBLON_RULED_OUT=0` (`gates.py:33-36`).
- **Persistence:** `decisions`. Does not delete the person by itself.
- **Tests:** Ruled-out contract tests exist (`docs/CONTRACTS-RULED-OUT.md`). Not re-run here.
- **Platform:** Cross-platform. Ship claim **WIRED** (#65) in the completion matrix.
- **State at `35eeb72`:** WIRED. Gate default ON.
- **Notes:** Label matches the verb better than the internal name `rule_out`.

#### `identify`

- **Label:** Is this someone I named?
- **What it is:** 1:N compare of one face against named persons. Suggestion only.
- **Where implemented:** `identify.identify_face` (`identify.py:178`); Home command `_cmd_identify_face` (`product_features.py:176`) calls `identify_face(..., record=False)` (`product_features.py:191`). Also `identify_image`, `identify_run`.
- **Owner:** Identify.
- **What it exposes:** Inspector button (registry), Ctrl+K when a face is in context, CLI `semblon identify`.
- **Where the user accesses it:** Inspector, after a face is selected. Not a sidebar item.
- **Dependencies:** Named-person gallery; same pack; existing threshold. Must not be retuned here.
- **Persistence:** CLI can write a decision. The Home button passes `record=False`, so that click does not assign and does not record.
- **Tests:** `tests/test_identify.py` `test_identify_does_not_auto_assign_person`, `test_identify_accepts_named_person_not_cluster`, `test_cli_identify_face`. Not re-run here.
- **Platform:** Cross-platform given embeddings.
- **State at `35eeb72`:** GUI command exists. The exposure matrix “MISSING in GUI” row is stale.
- **Notes:** Disabled reason: “Select a face first” (`product_features.py:170`). Wrong identity stays worse than unknown.

#### `inbox`

- **Label:** People to name (sidebar). Not the four bucket names.
- **What it is:** Classify faces as KNOWN, UNKNOWN, REVIEW_REQUIRED, or REJECTED.
- **Where implemented:** `inbox.inbox` (`inbox.py:75`); `Application.inbox` (`application.py:241`); Home unknown page reads unnamed clusters (exposure audit; page `_page_unknown` `product_features.py:58`).
- **Owner:** Inbox.
- **What it exposes:** CLI `semblon inbox` prints buckets. GUI flattens to unnamed groups.
- **Where the user accesses it:** Sidebar “People to name” (route `unknown`). The four buckets are CLI only.
- **Dependencies:** Decisions and faces for the run.
- **Persistence:** Read-only classification of stored rows.
- **Tests:** Inbox tests exist in the suite; exact function names were not re-listed in this session. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** CLI complete; GUI partial. Exposure audit still right about the missing chips.
- **Notes:** Do not show the enum names in the product (exposure audit risk note). That advice is unchanged; the chips were not added.

#### `people-list`

- **Label:** People.
- **What it is:** List named people.
- **Where implemented:** `search.search_people` (`search.py:111`); `Application.people`; `_page_people` (`product_features.py:52`).
- **Owner:** Search / Home.
- **What it exposes:** Sidebar; CLI `semblon search --people`.
- **Where the user accesses it:** Sidebar People. Inspector text list, not a face gallery.
- **Dependencies:** `persons`.
- **Persistence:** Read-only.
- **Tests:** Search tests. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present, text list. Exposure audit “PARTIAL (text list)” still matches.
- **Notes:** Activity and More also have “Open People”, which only navigates (`activity_feature.py:164`).

#### `search-person-name`

- **Label:** Search (top bar).
- **What it is:** Find a person by display name.
- **Where implemented:** `search.search_person` (`search.py:44`); `home_ui.py:3971` `_search_person`.
- **Owner:** Search.
- **What it exposes:** Top search box; CLI `semblon search`.
- **Where the user accesses it:** Top bar, Ctrl+F.
- **Dependencies:** Named persons.
- **Persistence:** Read-only.
- **Tests:** `tests/test_product_exposure.py` `test_home_search_tries_text_without_modality_gate` covers the fallthrough, not only the name hit. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present.
- **Notes:** If no person matches, the same box calls `search_text` (`home_ui.py:4008`, `4032`). The box label does not say that until the user invokes “Search text in photos”.

#### `search-face-id`

- **Label:** none.
- **What it is:** Look up one face id inside a run.
- **Where implemented:** `search.search_face` (`search.py:95`); CLI `--face`.
- **Owner:** Search.
- **What it exposes:** CLI only.
- **Where the user accesses it:** CLI only.
- **Dependencies:** `run_id` and `face_id`.
- **Persistence:** Read-only.
- **Tests:** Search tests. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** CLI. Exposure audit still accurate.
- **Notes:** Identify is the product question; this is an id lookup.

### Non-face search and index

#### `search-ocr-text`

- **Label:** Search text in photos (More / Ctrl+K). The top box has no such label until that command runs.
- **What it is:** Substring search over stored OCR text.
- **Where implemented:** `search.search_text` (`search.py:342`); Home fallthrough `home_ui.py:4008` and `4032`; command `_cmd_search_text_hint` (`product_features.py:218`) **only focuses the box and explains the fallthrough**. It does not run a separate query.
- **Owner:** Search.
- **What it exposes:** Silent fallthrough in the top box; a hint command; CLI text search.
- **Where the user accesses it:** Top search, unlabeled, or More → Search text in photos.
- **Dependencies:** Stored text from OCR. A missing OCR read is not an empty match (search honesty fixes on `main`).
- **Persistence:** Reads `observation_items` payloads. Does not write.
- **Tests:** `tests/test_product_exposure.py` `test_home_search_tries_text_without_modality_gate`; OCR honesty tests in the search suite. Not re-run here.
- **Platform:** Cross-platform over stored rows. New reads need tesseract.
- **State at `35eeb72`:** Partial. The exposure matrix “PARTIAL (silent fallback)” is still right. The new command only adds a hint.
- **Notes:** Hint copy (`product_features.py:227-228`) is truthful about the fallthrough.

#### `search-similar`

- **Label:** none for `search_similar` itself. “Find similar photos” is a different command (see `region-similar`).
- **What it is:** Nearest non-face embeddings for an observation item.
- **Where implemented:** `search.search_similar` (`search.py:189`); CLI `--similar`.
- **Owner:** Search.
- **What it exposes:** CLI. Optional use of the ANN file.
- **Where the user accesses it:** CLI only, as its own action.
- **Dependencies:** `embeddings` with `modality != 'face'`. Refuses to be identity.
- **Persistence:** Read-only.
- **Tests:** `tests/test_schema_open.py` `test_derived_index_is_used_and_faces_stay_out`; `tests/test_region_search.py` is the other similarity path. Not re-run here.
- **Platform:** Cross-platform. Numpy cosine, not FAISS (completion matrix).
- **State at `35eeb72`:** **PARTIAL**. CLI. Not a Home action.
- **Notes:** Do not merge this with FaceKit.

#### `ann-index`

- **Label:** Fast visual index (catalog only). Hidden on Home (`home_shell.py:16-17`).
- **What it is:** A disposable `.npz` index of non-face embeddings.
- **Where implemented:** `ann_index.build_index` / `search_index` (`ann_index.py:11-19`). File is `{store}.semblon-index.npz`.
- **Owner:** Index.
- **What it exposes:** CLI `semblon lab index`. Search may use it. Not a nav item.
- **Where the user accesses it:** Lab only.
- **Dependencies:** Non-face embedding rows. SQLite stays authoritative.
- **Persistence:** The `.npz` file. Rebuildable. Not a vector database.
- **Tests:** `test_derived_index_is_used_and_faces_stay_out`. `test_capability_sections_list_missing_models` expects the id off the strip. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** **PARTIAL** (completion matrix). Catalog `default_model` is `MISSING`.
- **Notes:** Home must not grow a row for it.

### Canvas and open-vocabulary vision

#### `photo-grid`

- **Label:** Browse photos (More). Sidebar label Photos is the landing.
- **What it is:** Still-photo grid (`source_type=folder`).
- **Where implemented:** Route `photos` → `_page_photos` (`product_features.py:22`); `CanvasWorkspace`.
- **Owner:** Canvas.
- **What it exposes:** More → Browse photos; landing CTA when the library is non-empty. CLI `semblon canvas` is the standalone process, not this embed.
- **Where the user accesses it:** More, or the landing browse CTA. Not the sidebar item named Photos.
- **Dependencies:** `media` rows; image decode via `canvas.load_bgr`.
- **Persistence:** Read-only grid. Opening a photo can start a visual job that writes a sidecar (see `visual-cache`).
- **Tests:** Canvas and visual-region tests. Not re-run here.
- **Platform:** Tk plus OpenCV decode. ARM64 OpenCV load remains blocked for a native cv2 swap.
- **State at `35eeb72`:** The Photos-versus-grid split from the forensic audit is still true (`_page_home` calls `_show_home_landing`, `product_features.py:18-19`).
- **Notes:** Sidebar “Photos” is a library dashboard. That label over-promises a grid.

#### `video-grid`

- **Label:** Videos.
- **What it is:** Grid of `source_type=video` media.
- **Where implemented:** `_page_videos` (`product_features.py:31`); `canvas.py` source filter.
- **Owner:** Canvas.
- **What it exposes:** Sidebar Videos.
- **Where the user accesses it:** Sidebar.
- **Dependencies:** Video media rows from ingest. Not a player with a track lane.
- **Persistence:** Read-only grid.
- **Tests:** Canvas load tests. Not re-run here.
- **Platform:** Same as the photo grid.
- **State at `35eeb72`:** Present.
- **Notes:** Sampled video is holdout evidence (`docs/S7A.md`), not a second identity engine.

#### `canvas-hit-test`

- **Label:** Outlines and inspector lines. No separate control name.
- **What it is:** Hover and click a face, object, or visual segment on an open photo.
- **Where implemented:** `canvas.py` motion/click handlers; hover schedules analysis (`canvas.py:938-980`); `product_surface` soft lines.
- **Owner:** Canvas.
- **What it exposes:** Pointer on an open photo inside Home’s embedded canvas.
- **Where the user accesses it:** Photo stage, after Browse photos / Videos / Explore. Not from the Photos landing.
- **Dependencies:** Home passes `job_engine=self.engine` (`home_ui.py:1215`).
- **Persistence:** Hover lookup reads cache or stored rows. It does not assign a person.
- **Tests:** `tests/test_sam2_spatial.py` `test_canvas_hover_never_infers_and_job_runs`; `tests/test_visual_regions.py` `test_hover_module_does_not_import_a_model`; `tests/test_visual_understanding.py`. Not re-run here.
- **Platform:** Tk. Needs verification on Windows with a real photo.
- **State at `35eeb72`:** On the production canvas path. Completion matrix: real-photo quality is not a finished product claim.
- **Notes:** Hover must not infer a name the cache does not already have (`test_canvas_hover_never_infers_and_job_runs`).

#### `canvas-drag-region-hits`

- **Label:** Inspector lines for a dragged box. No action menu.
- **What it is:** Hit-test stored observations inside a drag rectangle.
- **Where implemented:** `canvas.py` drag; `product_surface.region_hits`.
- **Owner:** Canvas / product surface.
- **What it exposes:** Pointer drag on the photo stage.
- **Where the user accesses it:** Open photo.
- **Dependencies:** Stored boxes.
- **Persistence:** Read-only hit test. Distinct from persisting a user rectangle (Lens release path).
- **Tests:** Geometry / canvas tests. Not re-run here.
- **Platform:** Tk.
- **State at `35eeb72`:** Present, per the exposure audit. Not re-clicked here.
- **Notes:** This drag is not `query_image` and not the Lens “Select a region” mouse-up.

#### `explore-workspace`

- **Label:** Explore workspace.
- **What it is:** Canvas of all media types inside Home.
- **Where implemented:** Route `canvas` → `_page_canvas` (`product_features.py:41`); command `canvas.explore`.
- **Owner:** Canvas.
- **What it exposes:** More menu and palette.
- **Where the user accesses it:** More → Explore workspace.
- **Dependencies:** Store media.
- **Persistence:** Read-only navigation. Visual jobs may still write sidecars when a photo opens.
- **Tests:** Registry overflow test. Not re-run here.
- **Platform:** Tk.
- **State at `35eeb72`:** Present. `product_exposure.py` still classifies it SECONDARY / DEMOTE (`product_exposure.py:110-115`).
- **Notes:** Not a second process.

#### `standalone-canvas`

- **Label:** none in Home.
- **What it is:** `semblon canvas` as its own Tk process.
- **Where implemented:** `canvas.run_canvas` (`canvas.py:1717`); CLI parser `canv` near `cli.py:531`.
- **Owner:** Canvas.
- **What it exposes:** CLI. More navigates inside Home instead of spawning this process.
- **Where the user accesses it:** CLI only.
- **Dependencies:** Tk. Without `job_engine`, visual analysis uses an inline thread (`canvas.py:939-970`).
- **Persistence:** Same store and `visual_cache`.
- **Tests:** Canvas tests. Not re-run here.
- **Platform:** Tk.
- **State at `35eeb72`:** Present.
- **Notes:** Forensic audit: one production process is `semblon home`. This command is a second door.

#### `visual-segment`

- **Label:** Hover chip / inspector soft name. No sidebar item.
- **What it is:** Open-vocabulary regions on a photo. Not people.
- **Where implemented:** `visual_segment.py` `VisualSegment`; `visual_analyze.analyze_image` / `analyze_and_cache` / `hover_lookup`; `semantic_visual.py`; `application.analyse_visual` (`application.py:160`).
- **Owner:** Visual understanding.
- **What it exposes:** Canvas hover after a photo is open; CLI `semblon lab visual-understand` (`cli.py:80-88`).
- **Where the user accesses it:** Open photo on the canvas. Not the Photos landing.
- **Dependencies:** OpenCV for the coarse pass. SAM 2 only when `sam2-spatial` is ready. Optional naming can abstain.
- **Persistence:** Sidecars, not new SQLite columns (`docs/VISUAL-UNDERSTANDING.md`). `tests/test_sam2_spatial.py` `test_analysis_does_not_mutate_store_or_identity`.
- **Tests:** `tests/test_visual_understanding.py`, `tests/test_visual_regions.py`, `tests/test_sam2_spatial.py`. Not re-run here.
- **Platform:** CPU OpenCV path is the fallback. GPU is not required for the coarse pass.
- **State at `35eeb72`:** On `main`. An older visual-path note that “VisualSegment does not exist” is false at this commit.
- **Notes:** Must not enrol a person (`test_persist_does_not_create_a_person`, `test_user_proper_name_is_not_a_person`). Completion matrix: **PARTIAL**.

#### `sam2-spatial`

- **Label:** none. Catalog label “Grounding” is the other SAM 2 door (`grounding-lens`).
- **What it is:** Automatic region proposals for visual discovery when a local checkpoint is ready.
- **Where implemented:** `sam2_runtime.py` `probe_sam2`, `generate_regions`, `predict_point`, `predict_box`, `Sam2SpatialProvider`; called from visual discovery / `visual_analyze.py`.
- **Owner:** Visual discovery.
- **What it exposes:** No control. Runs inside the canvas visual job when the probe is ready. CLI visual-understand can exercise analysis.
- **Where the user accesses it:** Not exposed as its own action.
- **Dependencies:** Local checkpoint. `SEMBLON_SAM2_WEIGHTS` or `~/.cache/semblon/sam2` (`docs/VISUAL-REGIONS.md`). `sam2_runtime.checkpoint_path`. Nothing is downloaded. `SEMBLON_SAM2_CHECKPOINT` is the Lens grounding variable and is not this function’s only key.
- **Persistence:** Masks in `visual_cache` (`masks.npz`). No new DDL.
- **Tests:** `tests/test_sam2_spatial.py` (missing package, missing file, load failure, nested masks, hover does not call SAM 2). `tests/test_visual_regions.py` `test_sam2_is_not_ready_without_weights`. Not re-run here.
- **Platform:** Needs the SAM 2 package and a checkpoint. DirectML is not the SAM 2 backend (completion matrix).
- **State at `35eeb72`:** **PARTIAL**. Absent checkpoint → not ready; OpenCV regions remain, with an explicit state.
- **Notes:** Two SAM 2 uses. This one proposes regions for the owner map. `lens.ground_selection` outlines one user rectangle. Do not treat them as one capability.

#### `visual-cache`

- **Label:** none.
- **What it is:** Sidecar folder for segments, pixel map, and masks.
- **Where implemented:** `visual_cache.py`; directory `{store_parent}/visual_cache` (`visual_cache.py:38`); layout in `docs/VISUAL-UNDERSTANDING.md`.
- **Owner:** Visual understanding.
- **What it exposes:** None.
- **Where the user accesses it:** Not exposed.
- **Dependencies:** A visual analyze run.
- **Persistence:** Files beside the library. Survives restart. SQLite remains authoritative for identity and for observation rows.
- **Tests:** `test_reanalysis_replaces_cache`. Not re-run here.
- **Platform:** Cross-platform filesystem.
- **State at `35eeb72`:** Present.
- **Notes:** Not a schema column. Deleting the folder drops hover detail until reanalysis.

### Lens query and catalog capabilities

Catalog ids live in `runtime_contract.default_catalog` (`runtime_contract.py:119-239`). Home shows only the tracked subset, and only the default model state.

#### `lens-workspace`

- **Label:** Lens.
- **What it is:** A Home route to open a photo, select a region, and ask.
- **Where implemented:** `_page_lens` → `home_ui._open_lens` (`product_features.py:48`; `home_ui.py:1531`); workspace `_build_lens_workspace` (`home_ui.py:1538`). Honesty rows confirmed at `home_ui.py:1687`.
- **Owner:** Lens.
- **What it exposes:** Sidebar ASK → Lens; top Lens button; inspector “Ask with Lens” and “Select a region”.
- **Where the user accesses it:** Sidebar and the brand button.
- **Dependencies:** A photo (`lens_home.py:12-20` if none is open).
- **Persistence:** Depends on the action (region persist vs query persist).
- **Tests:** Lens home tests in the suite (not re-run). `test_lens_lines_use_plain_labels_not_internal_ids`.
- **Platform:** Tk.
- **State at `35eeb72`:** Present.
- **Notes:** One route, not one sidebar item per model (`docs/UI-EXPOSURE-MAP.md` rule, still correct).

#### `user-region-persist`

- **Label:** Select a region.
- **What it is:** Save the user’s rectangle as an unnamed observation, then search.
- **Where implemented:** `user_region.persist_user_region` (`user_region.py:54`); production mouse-up `lens_home.open_region_select` (`lens_home.py:8-55`) → `lens_release.remember_selection`. `Application.remember_region` (`application.py:249`).
- **Owner:** Lens.
- **What it exposes:** Inspector button; palette; the same command id as the region gesture. Production launch installs this handler (`lens_home.py:97-107`).
- **Where the user accesses it:** Inspector “Select a region”, or Lens stage when that route is open.
- **Dependencies:** An open photo with a `media_id`.
- **Persistence:** `observation_items` kind object / user box. Not a person (`tests/test_user_region.py` `test_box_survives_reconnect_and_is_not_a_person`).
- **Tests:** `tests/test_user_region.py`. Not re-run here.
- **Platform:** Tk for the gesture. Store write is cross-platform.
- **State at `35eeb72`:** On the production mouse-up path. Completion matrix drag-to-select row is **PARTIAL** because Tk was not clicked in that environment either.
- **Notes:** Mouse-up does not run the capability catalog (`query_image`). It persists and finds similar.

#### `name-user-region`

- **Label:** none.
- **What it is:** Attach a name to a saved user region without creating a person.
- **Where implemented:** `user_region.name_user_region` (`user_region.py:171`); `Application.name_region` (`application.py:278`).
- **Owner:** Lens.
- **What it exposes:** API only. No inspector field found.
- **Where the user accesses it:** Not exposed.
- **Dependencies:** A persisted region item id.
- **Persistence:** Name on the observation item payload.
- **Tests:** `tests/test_visual_regions.py` `test_user_proper_name_is_not_a_person` covers a proper name that is not a person. Direct `name_user_region` coverage needs verification if that test uses another door.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** API present. GUI missing, as the exposure audit said.
- **Notes:** Must not create a person.

#### `region-similar`

- **Label:** Find similar photos. The mouse-up result lines say similar, not identified.
- **What it is:** Query-time color / appearance vector on the crop. Not FaceKit.
- **Where implemented:** `region_search.remember_and_find` (`region_search.py:181`), `find_similar_region` (`region_search.py:156`); wired by `lens_release.remember_selection`. Command `lens.find_similar` calls `_open_region_select` (`product_features.py:121-123`), the same function as “Select a region”.
- **Owner:** Lens / region search.
- **What it exposes:** The mouse-up path. The palette command is registered. The inspector loop **skips** `lens.find_similar` (`home_ui.py:1332-1338`), so there is no separate inspector button.
- **Where the user accesses it:** After Select a region (mouse-up). Palette label “Find similar photos” opens the same gesture. Not `semblon search --similar`.
- **Dependencies:** A decodable image. Does not write an embedding for the user box (`tests/test_region_search.py` `test_query_time_search_does_not_write_embeddings`).
- **Persistence:** The region row is persisted. The similarity hit list is a query result.
- **Tests:** `tests/test_region_search.py`. Not re-run here.
- **Platform:** Needs OpenCV for the histogram / crop.
- **State at `35eeb72`:** Production mouse-up path. Distinct from `search_similar` and from SAM 2.
- **Notes:** “Find similar photos” as a command name promises its own action. The handler only opens region select.

#### `lens-query`

- **Label:** Ask with Lens.
- **What it is:** Run the installed Lens capabilities on a whole image (or a CLI rectangle).
- **Where implemented:** `lens.query_image` (`lens.py:589`); `selection` / Home `_ask_with_lens`; CLI `semblon lab query`.
- **Owner:** Lens.
- **What it exposes:** Inspector “Ask with Lens”; Lens page; lab CLI. Not the region mouse-up.
- **Where the user accesses it:** Inspector and the Lens route.
- **Dependencies:** Whatever probes succeed at call time (`probe_siglip`, `probe_sam2`, `probe_ocr_status`, and the other `probe_*` functions in `lens.py:119-161`). Circuits wrap calls.
- **Persistence:** `persist_successes` (`lens.py:718`) writes non-face observation items. Not people (`test_hits_persist_without_becoming_people`).
- **Tests:** `tests/test_lens.py`. Not re-run here.
- **Platform:** Cross-platform for file query. Screen source is Windows-only.
- **State at `35eeb72`:** Code present. Whether weights exist on a given PC is unknown from the repo (exposure audit closing paragraph, still true).
- **Notes:** Missing providers must say unavailable, not “nothing matched” (`lens` module contract; `last_result_copy`).

#### `visual-embedding`

- **Label:** Visual embedding.
- **What it is:** SigLIP ONNX embedding for similar pictures. Not identity.
- **Where implemented:** `lens.embed_siglip` (`lens.py:295`); `probe_siglip`. Catalog id `visual_embedding` (`runtime_contract.py:139-146`), default `MISSING`.
- **Owner:** Lens.
- **What it exposes:** Strip row; Lens row; `lab query` / `lab install`. No install button.
- **Where the user accesses it:** Landing strip and Lens list, as a static “Optional · install needed” unless some caller passes a probe report. Home does not.
- **Dependencies:** A local ONNX file installed by `semblon lab install` (no download). Env paths used by the probe.
- **Persistence:** `embeddings.modality='siglip'` when a query persists. Never `modality='face'`.
- **Tests:** `tests/test_lens.py` `test_corrupt_siglip_file_is_not_an_empty_embedding`; `tests/test_schema_open.py` `test_siglip_onnx_session_runs` (tiny ONNX fixture, not real SigLIP weights). Not re-run here.
- **Platform:** ONNX Runtime. Completion matrix **PARTIAL**.
- **State at `35eeb72`:** Implementation partial. Strip state is the catalog default.
- **Notes:** Label “Visual embedding” is an engineering name. The catalog description is “Similar pictures. Not identity.” (`runtime_contract.py:143`).

#### `read-text`

- **Label:** Read text.
- **What it is:** OCR a crop or image. Also an ingest observer when enabled.
- **Where implemented:** `lens.read_text` (`lens.py:272`); `observers.ocr_image` (`observers.py:302`); `probe_ocr_status`.
- **Owner:** Lens and Observers.
- **What it exposes:** Strip / Lens rows (static); lab query; ingest only when the modality gate and probe say so.
- **Where the user accesses it:** Listed on the landing and Lens. No “turn on OCR” control. Search uses text already stored.
- **Dependencies:** Tesseract. `SEMBLON_MODALITY_PRODUCT` for product ingest observers (`gates.py:18`, `observers.resolve_product_observers` `observers.py:243`).
- **Persistence:** `observation_items` kind text. Stored text remains if a new read cannot run (catalog description, `runtime_contract.py:151`).
- **Tests:** Lens and schema-open OCR/circuit tests (`test_ingest_ocr_circuit_skips_the_provider`). Not re-run here.
- **Platform:** Needs a local tesseract binary.
- **State at `35eeb72`:** Optional. Home base observers omit OCR (`home_ui.py:195`).
- **Notes:** Strip cannot show “available” just because tesseract is installed.

#### `translation`

- **Label:** Translation.
- **What it is:** Dictionary translation of OCR text. Argos only if that import exists.
- **Where implemented:** `lens.translate_text` (`lens.py:340`); catalog default `MISSING` (`runtime_contract.py:155-160`).
- **Owner:** Lens.
- **What it exposes:** Strip and Lens rows; `lab query` after text exists.
- **Where the user accesses it:** Listed. No result-action button of its own beyond Ask with Lens.
- **Dependencies:** A JSON dictionary file. Does not replace the original text.
- **Persistence:** Query items if persist runs. Original OCR row stays.
- **Tests:** `tests/test_schema_open.py` `test_dictionary_translation_runs`. Not re-run here.
- **Platform:** Cross-platform for the dictionary. No neural model shipped (completion matrix **PARTIAL**).
- **State at `35eeb72`:** Partial. Strip shows install needed from the default.
- **Notes:** Name does not say “dictionary”.

#### `grounding-lens`

- **Label:** Grounding.
- **What it is:** Outline one selected rectangle with SAM 2, or keep the rectangle if the model is missing.
- **Where implemented:** `lens.ground_selection` (`lens.py:210`); `_sam2_predict` (`lens.py:248`); env `SEMBLON_SAM2_CHECKPOINT`, `SEMBLON_SAM2_CONFIG`, `SEMBLON_SAM2_SHA256`.
- **Owner:** Lens.
- **What it exposes:** Inside `query_image` / `lab query` with a region. The product mouse-up does not call it.
- **Where the user accesses it:** Ask with Lens or lab query, not “Select a region”.
- **Dependencies:** Those env vars and a local checkpoint. No download. Fallback `RECTANGULAR_CROP` (`runtime_contract.py:164-171`).
- **Persistence:** Mask digest in observation payload, not a mask column (`lens.persist_successes`).
- **Tests:** `tests/test_schema_open.py` `test_sam2_mask_is_recorded_when_the_predictor_returns_one`; `tests/test_runtime_contract.py` `test_rectangle_is_not_a_mask`. Not re-run here.
- **Platform:** SAM 2 package plus checkpoint. Otherwise the rectangle remains.
- **State at `35eeb72`:** **PARTIAL**. Distinct from `sam2-spatial`.
- **Notes:** “Grounding” does not say “outline the box you drew.” The catalog sentence does (`runtime_contract.py:167`).

#### `barcode`

- **Label:** Barcode.
- **What it is:** Read a QR / barcode with OpenCV. OCR must not stand in for it.
- **Where implemented:** `lens.read_symbology` (`lens.py:163`); `probe_barcode`.
- **Owner:** Lens.
- **What it exposes:** Strip, Lens list, `lab query`.
- **Where the user accesses it:** Listed; runs as part of Ask / lab query.
- **Dependencies:** OpenCV `QRCodeDetector`.
- **Persistence:** Observation item on success.
- **Tests:** `tests/test_lens.py` `test_qr_is_a_hit_and_missing_models_do_not_match`, `test_blank_barcode_ran_and_found_nothing`. Not re-run here.
- **Platform:** OpenCV. Completion matrix does not claim a hardware scanner.
- **State at `35eeb72`:** Code present. Strip state is the catalog default `MISSING`, even though the detector is a library call. Needs verification of `probe_barcode` versus that default — the strip will not show the probe.
- **Notes:** A blank image is `NO_RESULT`, not a missing model (`test_blank_barcode_ran_and_found_nothing`), but only when the function actually runs.

#### `describe-vlm`

- **Label:** Describe. Strip state from default `DISABLED` is “Experimental” (`home_shell.py:50-51`).
- **What it is:** A local description. A `pixel-describer` marker runs a colour model. A bad schema is ERROR.
- **Where implemented:** `lens.describe_vlm` (`lens.py:438`); `validate_vlm_payload`; catalog `runtime_contract.py:181-187`.
- **Owner:** Lens.
- **What it exposes:** Strip and Lens rows; `lab query`.
- **Where the user accesses it:** Listed as Experimental from the default, not from a live model check.
- **Dependencies:** `SEMBLON_VLM_MODEL` or the pixel marker. Setting the env does not flip the strip.
- **Persistence:** Description item. Must not rename a person (catalog sentence).
- **Tests:** `tests/test_lens.py` `test_valid_vlm_is_a_description_not_a_name`, `test_invalid_vlm_output_is_rejected`; `tests/test_schema_open.py` `test_pixel_describer_is_a_real_structured_description`. Not re-run here.
- **Platform:** Local only. Not a downloaded VLM (completion matrix **PARTIAL**).
- **State at `35eeb72`:** Disabled by catalog default.
- **Notes:** “Describe” can be read as a captioning product. The shipped path is a local structured description, often the pixel model.

#### `knowledge-pack`

- **Label:** Knowledge (one strip row, id `lkg`).
- **What it is:** Local JSON pack lookup from OCR or barcode text.
- **Where implemented:** `knowledge.lookup` (`knowledge.py:51`); called from `lens._lookup_pack` (`lens.py:554`) when `SEMBLON_LKG_PACK` is set (`lens.py:582`).
- **Owner:** Knowledge.
- **What it exposes:** One Home row. Invoked inside `query_image` if a pack path is set. CLI `lab query`.
- **Where the user accesses it:** Listed. No pack picker.
- **Dependencies:** `SEMBLON_LKG_PACK`. Missing pack is UNAVAILABLE, not an empty library (`runtime_contract.py:193`).
- **Persistence:** Match items if persist runs. Pack file is outside the store.
- **Tests:** `tests/test_schema_open.py` `test_pack_matches_a_barcode_and_a_missing_pack_does_not`. Not re-run here.
- **Platform:** Cross-platform file read.
- **State at `35eeb72`:** **PARTIAL**. Not a world recognizer.
- **Notes:** Landmark, logo, and product are separate catalog ids that share this pack and do not get their own strip rows.

#### `landmark`

- **Label:** Landmark (catalog). Not shown as its own Home row.
- **What it is:** Substring match in a local pack. Not a world landmark model.
- **Where implemented:** Catalog `runtime_contract.py:197-203`; `knowledge.lookup` kind. Listed in `lens.LENS_CAPABILITIES` (exposure audit `lens.py:25-36`).
- **Owner:** Knowledge.
- **What it exposes:** Lab query. Folded into the Knowledge strip row.
- **Where the user accesses it:** Not as its own control.
- **Dependencies:** `SEMBLON_LKG_PACK`.
- **Persistence:** Same as knowledge hits.
- **Tests:** Pack test above. Per-kind landmark coverage needs verification.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Catalog row, default `MISSING`.
- **Notes:** The name promises a landmark recognizer. The catalog sentence denies that (`runtime_contract.py:201`).

#### `logo`

- **Label:** Logo (catalog only).
- **What it is:** Local pack match. Not a logo crawler.
- **Where implemented:** `runtime_contract.py:205-210`; `knowledge.lookup`.
- **Owner:** Knowledge.
- **What it exposes:** Lab / query only.
- **Where the user accesses it:** Not as its own control.
- **Dependencies:** Pack file.
- **Persistence:** Query items.
- **Tests:** Same pack test. Per-kind coverage needs verification.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Catalog row.
- **Notes:** Same over-name pattern as landmark.

#### `product-pack`

- **Label:** Product (catalog only). Not the product GUI.
- **What it is:** Local pack match. A barcode is not a person.
- **Where implemented:** `runtime_contract.py:212-218`; `knowledge.lookup`.
- **Owner:** Knowledge.
- **What it exposes:** Lab / query only.
- **Where the user accesses it:** Not as its own control.
- **Dependencies:** Pack file and/or barcode text.
- **Persistence:** Query items.
- **Tests:** Pack test matches a barcode. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Catalog row.
- **Notes:** Do not confuse this id with “the Semblon product”.

#### `screen-capture`

- **Label:** Screen capture. Strip state from default `UNSUPPORTED_RUNTIME` is “Optional · not supported here” on every OS, including Windows.
- **What it is:** Grab a screen rectangle after a privacy intersection check.
- **Where implemented:** `lens.capture_screen` (`lens.py:473`); `probe_screen` (`lens.py:153`); `privacy.py` `blocked_hit`, `semblon_windows_win32`. CLI `semblon lab capture`.
- **Owner:** Privacy + Lens.
- **What it exposes:** Lab CLI. Not a Home button. The strip row is static.
- **Where the user accesses it:** Lab only.
- **Dependencies:** Windows for a real grab. ImageGrab fallback. WGC import does not return frames (completion matrix).
- **Persistence:** Query can persist hits. Capture itself is not a library import.
- **Tests:** `tests/test_lens.py` `test_screen_capture_off_windows_does_not_search`, `test_empty_screen_region_is_not_a_full_desktop_grab`; `tests/test_schema_open.py` `test_privacy_filter_refuses_the_semblon_window`. Not re-run here.
- **Platform:** Windows-only for a successful grab. Off Windows the probe stays unsupported.
- **State at `35eeb72`:** **PARTIAL**. Not tried on a Windows desktop in the matrix, and not tried here.
- **Notes:** Keep it in lab. The strip’s “not supported here” is untruthful on Windows because it never calls `probe_screen`.

#### `circuit-breaker`

- **Label:** none.
- **What it is:** After repeated provider crashes, skip that capability with `{id}.CIRCUIT_OPEN`.
- **Where implemented:** `circuits.py` `before_call` / `after_call` (`circuits.py:22-38`); used by Lens query and ingest OCR/CLIP/pose.
- **Owner:** Runtime.
- **What it exposes:** None. Must not be a per-capability Home toggle (exposure audit and UI map).
- **Where the user accesses it:** Not exposed. A failed ask can surface as unavailable.
- **Dependencies:** In-process counter. Threshold is three crashes (completion matrix).
- **Persistence:** Process memory only. Restart closes the circuit.
- **Tests:** `tests/test_schema_open.py` `test_circuit_opens_after_repeated_provider_errors`, `test_ingest_ocr_circuit_skips_the_provider`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** **PARTIAL**. Not used by Home text search (matrix).
- **Notes:** Not a user setting.

### Ingest observers (non-identity)

#### `color-object-ingest`

- **Label:** none. Boxes appear on the canvas.
- **What it is:** Color histogram and contour objects during ingest.
- **Where implemented:** `observers.color_histogram`, `contour_objects`, `observe_bgr` (`observers.py:157`, `175`, `524`). Home passes `HOME_OBSERVERS = "face,color,object"` (`home_ui.py:195`). Face token is ignored inside `observe_bgr` (face goes through FaceKit).
- **Owner:** Observers.
- **What it exposes:** No settings toggle. Results are canvas boxes and observation rows.
- **Where the user accesses it:** Indirectly, on the canvas after ingest.
- **Dependencies:** OpenCV. Not identity.
- **Persistence:** `observation_items` and appearance `embeddings`.
- **Tests:** `tests/test_observers.py` (file exists; function names not re-listed here). Not re-run here.
- **Platform:** OpenCV.
- **State at `35eeb72`:** On the Home ingest string.
- **Notes:** Contour objects are not open-vocabulary names. `visual-segment` is the later naming path and is separate.

#### `optional-modality-ingest`

- **Label:** none in Settings.
- **What it is:** OCR, CLIP, and pose at ingest when the modality gate and probes succeed.
- **Where implemented:** `observers.resolve_product_observers` (`observers.py:243`); probes `probe_ocr_status`, `probe_clip_status`, `probe_pose_status`; gate `SEMBLON_MODALITY_PRODUCT` (`gates.py:18`).
- **Owner:** Observers.
- **What it exposes:** No Settings switch. Diagnostics may list them. CLI ingest can pass an observer string.
- **Where the user accesses it:** Not exposed. Diagnostics only, if that panel lists probes.
- **Dependencies:** Tesseract, local CLIP weights, MediaPipe. They must not vote on identity.
- **Persistence:** Text / clip / pose `observation_items` and non-face embeddings.
- **Tests:** Observer and circuit tests. Not re-run here.
- **Platform:** Each probe is a local binary or weight check.
- **State at `35eeb72`:** Off unless the gate and probes pass. Home’s default string does not include them.
- **Notes:** `docs/OPTIONAL-MODALITY-STATUS.md` is the status note. This session did not re-verify that doc line by line.

### Memory

#### `memory-together`

- **Label:** People together (Activity section).
- **What it is:** Named people who appear on the same still or clip. Read-only. Not a social graph of confirmed facts.
- **Where implemented:** `memory.together` (`memory.py:343`); Activity via `activity_surface` and `Application.activity_memory` (`application.py:235`).
- **Owner:** Memory.
- **What it exposes:** Sidebar Recent activity.
- **Where the user accesses it:** Sidebar Recent activity.
- **Dependencies:** Named persons. Time and place must not change identity scores.
- **Persistence:** Read-only over faces, media, and EXIF. Does not write identity.
- **Tests:** `tests/test_memory.py` `test_history_together_events`, `test_memory_does_not_change_compare`. Not re-run here.
- **Platform:** Cross-platform. EXIF read is local.
- **State at `35eeb72`:** Present on Activity.
- **Notes:** Rows from the snapshot writer are `confirmed=0` (exposure audit). The Activity list must not say confirmed. Needs verification of the exact Activity sentence at this commit.

#### `memory-moments`

- **Label:** Moments.
- **What it is:** Burst / day / folder groupings. No LLM titles.
- **Where implemented:** `memory.events` (`memory.py:459`); Activity section.
- **Owner:** Memory.
- **What it exposes:** Activity page; CLI `semblon memory events`.
- **Where the user accesses it:** Recent activity.
- **Dependencies:** Timestamps from EXIF or filename (`memory.py` helpers).
- **Persistence:** Read-only. Separate from `events` table rows written by the snapshot.
- **Tests:** `test_history_together_events`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present.
- **Notes:** “Moments” is a soft label. The function is `events`, and it is not a calendar product.

#### `memory-history`

- **Label:** Show history.
- **What it is:** One named person’s when/where list.
- **Where implemented:** `memory.history` (`memory.py:323`); command `_cmd_person_history` (`product_features.py:136`).
- **Owner:** Memory.
- **What it exposes:** Inspector button when a person is in context; palette; CLI `semblon memory history --person`.
- **Where the user accesses it:** Inspector after a person is selected. Not a timeline page.
- **Dependencies:** A named person. “Select one named person” when missing (`product_features.py:132`).
- **Persistence:** Read-only.
- **Tests:** `tests/test_memory.py` `test_history_together_events`, `test_cli_memory`, `test_history_includes_named_video_presence`. Not re-run here. A GUI click test was not confirmed by name.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Inspector command exists. Exposure matrix “MISSING” is stale.
- **Notes:** Shows up to 16 lines in the inspector (`product_features.py:153`). Not a full timeline UI.

#### `memory-graph-rows`

- **Label:** none. Soft lines only.
- **What it is:** `relationships` and `events` rows snapshotted from review/cluster, with `confirmed=0`.
- **Where implemented:** `observers.snapshot_memory_graph` (`observers.py:795`); called from review (`review.py:33` region `_memory_snapshot`).
- **Owner:** Observers / Memory.
- **What it exposes:** No graph UI.
- **Where the user accesses it:** Not exposed as a graph. Activity uses `memory.together`, which is a different read.
- **Dependencies:** Review or cluster snapshot.
- **Persistence:** `relationships`, `events` tables (`store.py:227-237`).
- **Tests:** Memory tests that identity scores do not move. Direct snapshot tests need verification.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Rows can be written. No product graph.
- **Notes:** A “connections” UI would over-claim. Do not say confirmed.

### Video, live, watch

#### `derived-tracks`

- **Label:** none on Home. Review shows track cards.
- **What it is:** Group video faces into tracks.
- **Where implemented:** `tracks.derive_tracks`; `observers.persist_derived_tracks` (`observers.py:859`); canvas loads tracks for video (exposure verification). CLI `semblon tracks`.
- **Owner:** Tracks.
- **What it exposes:** CLI; Review track rows; canvas data for a video. No Home track lane.
- **Where the user accesses it:** Review, or by opening a video. Not a sidebar item.
- **Dependencies:** Video faces. A track is not a person.
- **Persistence:** `tracks`, `track_members` (`store.py:198-208`).
- **Tests:** `test_name_track_enrols_members_not_as_cluster` and track derivation tests. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present.
- **Notes:** Videos grid does not show a player with a track lane.

#### `sampled-video-ingest`

- **Label:** Videos (the grid of ingested video media).
- **What it is:** Sample frames from video into `media.source_type=video`.
- **Where implemented:** Ingest. Module docstring states S7a sampling (`cli.py:11`). `semblon ingest` help: “FACE-005 folder stills + S7a sampled video” (`cli.py:241`). Holdout policy `docs/S7A.md`.
- **Owner:** Ingest.
- **What it exposes:** CLI ingest flags; Videos nav shows the rows.
- **Where the user accesses it:** Sidebar Videos after ingest. Sampling policy is not a GUI control.
- **Dependencies:** OpenCV video read. Samples stay out of still-photo DBSCAN.
- **Persistence:** `media` rows with `source_type=video`.
- **Tests:** Ingest video-frame tests from the media-skip work. Not re-run here.
- **Platform:** OpenCV. ARM64 load blocked for native cv2.
- **State at `35eeb72`:** Ingest path exists. S7a remains holdout evidence, not a second identity engine.
- **Notes:** Needs verification of which CLI flags are documented versus required at `cli.py` ingest parser. This session did not re-read every flag.

#### `live-overlay`

- **Label:** Live…
- **What it is:** Explicit camera or RTSP overlay. Must not write `faces.person_id`.
- **Where implemented:** `live_overlay.run_live_overlay` (`live_overlay.py:105`); command `_cmd_live` (`product_features.py:105`); gates `SEMBLON_LIVE_OVERLAY`, `SEMBLON_WIRE_HOME_LIVE` (`gates.py:16-17`, `37-39`). CLI `semblon live` and `semblon lab live-overlay`.
- **Owner:** Live.
- **What it exposes:** More → Live… Technical prompts for index, URL, and seconds (exposure audit). Not the sidebar.
- **Where the user accesses it:** More menu.
- **Dependencies:** OpenCV capture; FaceKit; explicit start. Default gate ON, opt out with `0`.
- **Persistence:** Must not assign persons. Whether frames are stored needs verification in `live.py` beyond the gate comment. The gate text says the overlay must not write `faces.person_id` (`gates.py:39`).
- **Tests:** Live tests exist in the suite. Not re-run here. Not launched.
- **Platform:** Webcam / RTSP. Windows is the product machine. Out of frozen v1 identity (no live ID).
- **State at `35eeb72`:** More menu entry exists. Experimental.
- **Notes:** `product_exposure.py` pairs this with watch. They are not the same command.

#### `folder-watch`

- **Label:** Watch a folder…
- **What it is:** Two different behaviors. CLI `watch.watch_folder` (`watch.py:24`) polls and ingests until cancelled. The More command starts **one** `JobEngine` ingest and tells the user to use `semblon watch` for continuous watch (`product_features.py:255-276`).
- **Owner:** Watch (CLI) versus Home ingest (GUI).
- **What it exposes:** CLI `semblon watch`. GUI label that does not call `watch_folder`.
- **Where the user accesses it:** More → Watch a folder… (one scan). Continuous poll is CLI only.
- **Dependencies:** A folder. GUI refuses when `engine.busy`.
- **Persistence:** Same as ingest. No watch-daemon row.
- **Tests:** Watch tests may exist; the GUI command’s “one ingest” behavior is source at `product_features.py:271`. Not executed here.
- **Platform:** Cross-platform poll.
- **State at `35eeb72`:** CLI present. GUI label is ahead of the CLI behavior.
- **Notes:** `docs/UI-EXPOSURE-MAP.md` still says watch is not in Home. `product_exposure.py:118-122` says More → Live / watch as if both were the continuous tools. Both docs are behind this command, and the command is behind its own label.

### Reports, export, library files

#### `activity-surface`

- **Label:** Recent activity.
- **What it is:** Processing counts plus together and moments.
- **Where implemented:** `features/activity_feature.py` `activity_feature`; `activity_surface.py`; `Application.activity_memory`.
- **Owner:** Activity.
- **What it exposes:** Sidebar shortcut 5. Buttons “Review people” (goes to People to name) and “Open People”.
- **Where the user accesses it:** Sidebar.
- **Dependencies:** Store. Read-only (`activity_feature.py` module docstring).
- **Persistence:** None of its own.
- **Tests:** Activity/memory tests. Not re-run here.
- **Platform:** Tk.
- **State at `35eeb72`:** Present. Nav label is “Recent activity”, not “Activity” (`activity_feature.py:179`).
- **Notes:** “Review people” navigates to route `unknown`. It does not open Review UI (`activity_feature.py:168-169`).

#### `stats`

- **Label:** Landing tiles: Photos, Video frames, Named, To name, Observations.
- **What it is:** Read-only counts. CLI `stats` is a larger set than the five tiles.
- **Where implemented:** `stats.stats` (`stats.py:25`); CLI `semblon stats`; tiles `home_shell.shell_stats` (`home_shell.py:108-129`).
- **Owner:** Stats.
- **What it exposes:** CLI. Tiles are a different, smaller query.
- **Where the user accesses it:** Photos landing for the five numbers. Full stats are CLI only.
- **Dependencies:** Store. Does not write.
- **Persistence:** Read-only.
- **Tests:** `tests/test_home_shell.py` `test_shell_stats_and_enrichment`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Present.
- **Notes:** Tile “Observations” is a technical word (`home_shell.py:124-128`). The number is a real count.

#### `report`

- **Label:** none.
- **What it is:** Markdown summary written only to `--out`.
- **Where implemented:** `report.write_report` (`report.py:46`); CLI `semblon report`.
- **Owner:** Report.
- **What it exposes:** CLI only. No Home button found.
- **Where the user accesses it:** CLI only.
- **Dependencies:** A run. Must not write the store.
- **Persistence:** The markdown file the user named. Not the library.
- **Tests:** Report tests. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** CLI. Exposure audit still accurate.
- **Notes:** Easy to leak ids if the markdown is raw (exposure audit). Not changed here.

#### `export-review-html`

- **Label:** Open export review page… (Settings → Advanced).
- **What it is:** Write or open `review.html`. Not the product UI.
- **Where implemented:** `export.export_review` / `render_review_html` (`export.py:519`); `Application.review_document` (`application.py:229`).
- **Owner:** Export.
- **What it exposes:** Settings → Advanced. CLI `semblon export`.
- **Where the user accesses it:** Settings → Advanced. Not More (product chrome removed the old More entry; `product_exposure.py:131-143`).
- **Dependencies:** A processed run.
- **Persistence:** An HTML file outside the identity contract. Export reads the store.
- **Tests:** Export tests. Not re-run here.
- **Platform:** Cross-platform file write. Opening the page uses the OS browser.
- **State at `35eeb72`:** **SUPERSEDED as UX**. Export only.
- **Notes:** `product_exposure.py` still lists a STALE “review.html product chrome” row (`product_exposure.py:131-136`) describing a removed entry. That row is classification history, not a live button.

#### `export-person-folders`

- **Label:** Export person folders…
- **What it is:** A folder of views per named person. Originals stay put.
- **Where implemented:** `export.export_views` (export module; command `product_features.py:282-300`); CLI `semblon export --views`.
- **Owner:** Export.
- **What it exposes:** More menu and palette. CLI flag.
- **Where the user accesses it:** More → Export person folders…
- **Dependencies:** `latest_run_id`. Empty library shows “Nothing to export yet.”
- **Persistence:** New folders of views. Does not move originals (`product_features.py:299`).
- **Tests:** Export view tests. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** GUI command exists. Exposure matrix “MISSING” is stale.
- **Notes:** Message says originals stay put. That matches the product rule.

#### `backup-library`

- **Label:** Back up library…
- **What it is:** WAL-aware SQLite backup to `semblon-backup.sqlite` in a chosen folder.
- **Where implemented:** `store.backup_store` (`store.py:352`); command `_cmd_backup_library` (`product_features.py:235`); CLI `semblon lab backup`.
- **Owner:** Store.
- **What it exposes:** More menu and `lab backup`.
- **Where the user accesses it:** More → Back up library…
- **Dependencies:** The open store file.
- **Persistence:** A copy of the SQLite file. Does not alter the source (CLI help, `cli.py:69`).
- **Tests:** Store backup tests. Not re-run here.
- **Platform:** Cross-platform SQLite backup API.
- **State at `35eeb72`:** GUI command exists. Exposure matrix “MISSING” and “lab only” are stale for backup. Restore is still lab-only.
- **Notes:** The More label does not say “lab”. The implementation is the store backup helper, which is appropriate. It is not a full disaster-recovery wizard.

#### `restore-library`

- **Label:** none in Home.
- **What it is:** Replace a library from a backup. Refuses to overwrite unless `--force`.
- **Where implemented:** `store.restore_store` (`store.py:480`); CLI `semblon lab restore`.
- **Owner:** Store.
- **What it exposes:** Lab CLI only.
- **Where the user accesses it:** Lab only.
- **Dependencies:** A backup file. Can destroy the current library if forced.
- **Persistence:** Overwrites the destination store when forced.
- **Tests:** Store tests. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Lab. Exposure audit still accurate for restore.
- **Notes:** Do not pair this mentally with the More backup item. Home cannot restore.

#### `integrity`

- **Label:** none as a repair flow. Diagnostics may mention store health.
- **What it is:** Read-only integrity report.
- **Where implemented:** `store.integrity_report` (`store.py:415`); CLI `semblon lab integrity`.
- **Owner:** Store.
- **What it exposes:** Lab CLI. Not a user repair button.
- **Where the user accesses it:** Lab. Diagnostics only if that panel includes the report (exposure audit cites `advanced_diagnostics.py`; this session did not re-read that function).
- **Dependencies:** Store file.
- **Persistence:** Read-only.
- **Tests:** Store tests. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Lab.
- **Notes:** Not a repair tool.

#### `model-install`

- **Label:** none. Strip says “Optional · install needed” with no next step.
- **What it is:** Atomically copy a local model file. No downloader.
- **Where implemented:** `model_install`; CLI `semblon lab install` (`cli.py:89-95`).
- **Owner:** Models.
- **What it exposes:** Lab CLI only.
- **Where the user accesses it:** Lab only.
- **Dependencies:** A local source file and optional `--sha256`. Checksum mismatch does not replace the destination.
- **Persistence:** The destination file on disk.
- **Tests:** `tests/test_schema_open.py` `test_atomic_install_rejects_a_bad_checksum_and_keeps_the_old_file`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** **COMPLETE** for a local file (completion matrix). No network download.
- **Notes:** The strip’s “install needed” does not name this command.

#### `lab-providers-models`

- **Label:** none in Home. Diagnostics is the product-adjacent surface.
- **What it is:** `semblon lab providers` lists observation providers. `semblon lab models` reports local buffalo_l weights and does not download.
- **Where implemented:** CLI parsers `cli.py:78-79`.
- **Owner:** Diagnostics / models.
- **What it exposes:** Lab CLI. OCR is the provider line a previous verification said `lab providers` can override; this session did not re-read the providers dispatcher to confirm which probes it runs.
- **Where the user accesses it:** Lab, and possibly Diagnostics.
- **Dependencies:** Local files.
- **Persistence:** Read-only.
- **Tests:** Provider listing tests. Not re-run here.
- **Platform:** Cross-platform listing. Weight files are machine-local.
- **State at `35eeb72`:** Lab. buffalo_l redistribution **UNAVAILABLE**.
- **Notes:** These commands are closer to a live check than the Home strip. They are not wired into `capability_sections`.

### Engineering-only

#### `eval-harness`

- **Label:** none.
- **What it is:** FACE-002 confirmatory eval. Precision requires `--eval-set confirmatory`.
- **Where implemented:** `eval.py`; CLI `semblon lab eval` create/pair/freeze/mine/score (`cli.py:195-227`).
- **Owner:** Eval.
- **What it exposes:** Lab only.
- **Where the user accesses it:** Must stay out of product nav.
- **Dependencies:** Frozen confirmatory set. Discovery mine must not touch confirmatory.
- **Persistence:** `eval_sets`, `eval_pairs` (`store.py:131-140`).
- **Tests:** `tests/test_eval.py`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Lab. FACE-002 is a closed validation index, not the queue.
- **Notes:** Do not print precision without the confirmatory set.

#### `observatory`

- **Label:** none.
- **What it is:** Measurement snapshot, freeze, compare, and enter. Not a development gate.
- **Where implemented:** CLI `semblon lab observatory` (`cli.py:33-57`).
- **Owner:** Observatory.
- **What it exposes:** Lab only.
- **Where the user accesses it:** Forbidden in product chrome.
- **Dependencies:** A run board.
- **Persistence:** `golden-*.json` beside the store on freeze. Snapshot print is read-only.
- **Tests:** `tests/test_observatory.py`. Not re-run here.
- **Platform:** Cross-platform.
- **State at `35eeb72`:** Lab.
- **Notes:** Progress `on_event` is a different spine and stays in the product.

#### `engineering-probes`

- **Label:** none.
- **What it is:** FACE-000 profile, OpenCV probe, IPC loopback probe, R3 bake-off, lab live-overlay harness.
- **Where implemented:** CLI `lab profile`, `lab opencv`, `lab ipc-probe`, `lab r3-bakeoff`, `lab live-overlay` (`cli.py:29`, `124`, `152`, `169`, `181`). Modules `opencv_probe.py`, `ipc_probe.py`.
- **Owner:** Engineering.
- **What it exposes:** Lab only.
- **Where the user accesses it:** Must not appear in product nav.
- **Dependencies:** Platform-specific for OpenCV and bake-off. `SEMBLON_BAKEOFF_WINNER` must not be auto-set (`gates.py:7-8`).
- **Persistence:** Probe artifacts only when a command writes them. IPC probe is not product IPC (completion matrix **COMPLETE** as a probe).
- **Tests:** Probe test modules. Not re-run here.
- **Platform:** OpenCV ARM64 load **BLOCKED**. IPC probe is loopback.
- **State at `35eeb72`:** Present as lab.
- **Notes:** Bake-off / §8.7 is CLOSED. These commands must not reopen it.

#### `schema-store`

- **Label:** none. No schema browser.
- **What it is:** SQLite schema v4 (`store.py:9`), including the v2 observation tables.
- **Where implemented:** `store.py` `init_db` / `apply_migrations`. Tables: `schema_meta`, `runs`, `media`, `observations`, `clusters`, `persons`, `faces`, `cluster_person`, `decisions`, `eval_sets`, `eval_pairs`, `schema_migrations`, `observation_items`, `embeddings`, `tracks`, `track_members`, `observation_groups`, `group_members`, `relationships`, `events` (`store.py:15-237`).
- **Owner:** Store.
- **What it exposes:** None in the product UI.
- **Where the user accesses it:** Not exposed.
- **Dependencies:** SQLite. Originals stay in place. The database does not contain the image bytes as the authority.
- **Persistence:** This is the persistence layer.
- **Tests:** `tests/test_schema.py`, `tests/test_schema_open.py`. Not re-run here.
- **Platform:** Cross-platform SQLite.
- **State at `35eeb72`:** Schema version 4. No new columns in the visual-segment work (`docs/VISUAL-UNDERSTANDING.md`).
- **Notes:** “Schema v2” in older docs means the observation write-through migration, while `SCHEMA_VERSION` is `"4"`. Both statements are about this file. Do not invent columns.

### Explicit absences

These are not capabilities. They are listed so a later reader does not infer them.

| Name | Evidence |
|---|---|
| Collections / albums | No module. Exposure audit: no. |
| Duplicate-file browser | Skip is ingest policy only. |
| User-installable plugins | `gui_registry.py` docstring forbids them. `register_demo_feature` is a test. |
| Context menu widget | Surface string only. See `context-command-surface`. |
| Per-capability circuit toggles | Forbidden. |
| Sidebar item per Lens model | Forbidden. |

---

## Exposure matrix

Legend: **✓** yes, **✗** no, **~** partial or not executed here.

**Works** uses **~** whenever this session did not run the production path, even if tests exist. **✓** is not used in the Works column. Owner Windows evidence is named in the registry entry, not treated as a fresh run at `35eeb72`.

**Discoverable** means a person can find it from the window without reading code or CLI `--help`. A More item counts. A Settings control counts. Ctrl+K alone does not, unless Settings text mentions it.

| Capability | Exists | Works | Persisted | GUI exposed | Discoverable | Truthful |
|---|---|---|---|---|---|---|
| product-home | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| qt-shell | ✓ | ~ | ~ | ✗ | ✗ | ✓ |
| review-ui | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| feature-registry | ✓ | ~ | ✗ | ✗ | ✗ | ✓ |
| command-palette | ✓ | ~ | ✗ | ~ | ~ | ~ |
| context-command-surface | ~ | ✗ | ✗ | ✗ | ✗ | ✓ |
| keyboard-shortcuts | ✓ | ~ | ✗ | ~ | ~ | ✓ |
| theme | ✓ | ~ | ✓ | ✓ | ✓ | ~ |
| settings-library | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| diagnostics | ✓ | ~ | ✗ | ✓ | ~ | ~ |
| empty-states | ✓ | ~ | ✗ | ✓ | ✓ | ✓ |
| capability-honesty-strip | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ |
| lens-honesty-rows | ✓ | ✗ | ✗ | ✓ | ✓ | ✗ |
| add-folder-ingest | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| incremental-sha256-skip | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| resume-ingest | ✓ | ~ | ✓ | ✓ | ~ | ✓ |
| pause-cancel | ✓ | ~ | ~ | ✓ | ✓ | ✓ |
| gpu-preference | ✓ | ~ | ✗ | ~ | ~ | ~ |
| progress-events | ✓ | ~ | ✗ | ✓ | ✓ | ~ |
| worker-count | ✓ | ~ | ✗ | ✗ | ✗ | ✓ |
| facekit | ✓ | ~ | ✓ | ~ | ~ | ~ |
| dbscan | ✓ | ~ | ✓ | ~ | ~ | ✓ |
| name-person | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| name-faces-batch | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| name-track | ✓ | ~ | ✓ | ~ | ~ | ✓ |
| assign-person | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| merge-groups | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| split-faces | ✓ | ~ | ✓ | ✓ | ~ | ~ |
| ignore | ✓ | ~ | ✓ | ✓ | ✓ | ~ |
| ignore-disposition | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| review-note | ✓ | ~ | ✓ | ~ | ~ | ✓ |
| rule-out | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| identify | ✓ | ~ | ✗ | ✓ | ~ | ✓ |
| inbox | ✓ | ~ | ✗ | ~ | ~ | ~ |
| people-list | ✓ | ~ | ✗ | ✓ | ✓ | ~ |
| search-person-name | ✓ | ~ | ✗ | ✓ | ✓ | ~ |
| search-face-id | ✓ | ~ | ✗ | ✗ | ✗ | ✓ |
| search-ocr-text | ✓ | ~ | ✗ | ~ | ~ | ~ |
| search-similar | ✓ | ~ | ✗ | ✗ | ✗ | ✓ |
| ann-index | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| photo-grid | ✓ | ~ | ✗ | ~ | ~ | ✗ |
| video-grid | ✓ | ~ | ✗ | ✓ | ✓ | ~ |
| canvas-hit-test | ✓ | ~ | ~ | ~ | ~ | ~ |
| canvas-drag-region-hits | ✓ | ~ | ✗ | ~ | ~ | ~ |
| explore-workspace | ✓ | ~ | ✗ | ✓ | ✓ | ✓ |
| standalone-canvas | ✓ | ~ | ~ | ✗ | ✗ | ✓ |
| visual-segment | ✓ | ~ | ✓ | ~ | ~ | ~ |
| sam2-spatial | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| visual-cache | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| lens-workspace | ✓ | ~ | ~ | ✓ | ✓ | ~ |
| user-region-persist | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| name-user-region | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| region-similar | ✓ | ~ | ~ | ~ | ~ | ~ |
| lens-query | ✓ | ~ | ✓ | ✓ | ✓ | ~ |
| visual-embedding | ✓ | ~ | ✓ | ~ | ✓ | ✗ |
| read-text | ✓ | ~ | ✓ | ~ | ✓ | ✗ |
| translation | ✓ | ~ | ~ | ~ | ✓ | ✗ |
| grounding-lens | ✓ | ~ | ~ | ~ | ✓ | ✗ |
| barcode | ✓ | ~ | ~ | ~ | ✓ | ✗ |
| describe-vlm | ✓ | ~ | ~ | ~ | ✓ | ✗ |
| knowledge-pack | ✓ | ~ | ~ | ~ | ✓ | ~ |
| landmark | ✓ | ~ | ~ | ✗ | ✗ | ~ |
| logo | ✓ | ~ | ~ | ✗ | ✗ | ~ |
| product-pack | ✓ | ~ | ~ | ✗ | ✗ | ~ |
| screen-capture | ✓ | ~ | ✗ | ~ | ✓ | ✗ |
| circuit-breaker | ✓ | ~ | ✗ | ✗ | ✗ | ✓ |
| color-object-ingest | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| optional-modality-ingest | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| memory-together | ✓ | ~ | ✗ | ✓ | ✓ | ~ |
| memory-moments | ✓ | ~ | ✗ | ✓ | ✓ | ~ |
| memory-history | ✓ | ~ | ✗ | ✓ | ~ | ✓ |
| memory-graph-rows | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| derived-tracks | ✓ | ~ | ✓ | ~ | ~ | ✓ |
| sampled-video-ingest | ✓ | ~ | ✓ | ~ | ~ | ~ |
| live-overlay | ✓ | ~ | ✗ | ✓ | ✓ | ~ |
| folder-watch | ✓ | ~ | ✓ | ~ | ✓ | ✗ |
| activity-surface | ✓ | ~ | ✗ | ✓ | ✓ | ~ |
| stats | ✓ | ~ | ✗ | ~ | ✓ | ~ |
| report | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| export-review-html | ✓ | ~ | ✓ | ✓ | ~ | ✓ |
| export-person-folders | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| backup-library | ✓ | ~ | ✓ | ✓ | ✓ | ✓ |
| restore-library | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| integrity | ✓ | ~ | ✗ | ✗ | ✗ | ✓ |
| model-install | ✓ | ~ | ✓ | ✗ | ✗ | ~ |
| lab-providers-models | ✓ | ~ | ✗ | ✗ | ✗ | ✓ |
| eval-harness | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| observatory | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |
| engineering-probes | ✓ | ~ | ~ | ✗ | ✗ | ✓ |
| schema-store | ✓ | ~ | ✓ | ✗ | ✗ | ✓ |

### Matrix footnotes

- **Works ~** on every other row: source shows a callable production or lab path, and this session did not execute it. APP-1 C.3 (2026-09-22) is the owner Windows record for Home ingest and pause/resume. It was not repeated at `35eeb72`.
- **capability-honesty-strip / lens-honesty-rows Works ✗:** the functions run, but they do not check installs. `home_ui.py:2444` and `home_ui.py:1687` call them with catalog defaults (`runtime_contract.py:554-560`).
- **context-command-surface Exists ~ / Works ✗:** the string `"context"` is on commands. No menu reads it.
- **screen-capture GUI ~:** a strip row exists and is not a control. Lab capture is the real door. Truthful ✗ because the row says “not supported here” from `default_model`, including on Windows.
- **visual-embedding, read-text, translation, grounding-lens, barcode, describe-vlm Truthful ✗:** the landing and Lens lists show catalog defaults (`MISSING` or `DISABLED`), not `probe_*`.
- **folder-watch Truthful ✗ / GUI ~:** More → Watch a folder… calls `_start_process`, not `watch.watch_folder` (`product_features.py:255-276`).
- **photo-grid Truthful ✗ / GUI ~:** sidebar Photos opens the landing (`product_features.py:18-19`). The grid is More → Browse photos.
- **region-similar Truthful ~:** mouse-up does find similar (`lens_home.py:32-56`). The palette command of that name only opens region select, and the inspector hides that command (`home_ui.py:1332-1338`).
- **identify Persisted ✗:** Home passes `record=False` (`product_features.py:191`). CLI identify can write a decision.
- **pause-cancel Persisted ~:** cancel leaves a resumable run; pause is memory.
- **gpu-preference GUI ~:** the checkbox exists only when ORT reports a GPU EP (`home_ui.py:4151-4174`). The choice is not saved (`home_ui.py:904`).
- **facekit GUI ~ / Truthful ~:** there is no FaceKit control, which is correct, but catalog id `face` defaults to `MISSING` (`runtime_contract.py:137`) and is omitted from the strip. A reader of `status_report()` alone would think the identity engine is missing.
- **model-install Truthful ~:** the strip says install is needed and does not point at `semblon lab install`.
- **activity-surface Truthful ~:** “Review people” opens People to name, not Review (`activity_feature.py:168-169`).
- **search-person-name Truthful ~:** the same box falls through to OCR text without saying so until the hint command (`home_ui.py:4008`).
- **inbox Truthful ~:** People to name is real and is not the four CLI buckets.
- **split-faces Discoverable ~:** the button exists; comparing faces first still means opening Review.
- **command-palette Discoverable ~:** Ctrl+K is listed in Advanced settings; there is no on-screen button.
- **people-list Truthful ~:** it is a text list, which the sidebar word “People” does not spell out.
- **stats GUI ~:** five tiles, not `semblon stats`.
- **video-grid / sampled-video Truthful ~:** Videos is a grid, not a player.
- **live-overlay Truthful ~:** the menu item exists; the prompts are technical (camera index, RTSP). Not re-tested.
- **memory-together / memory-moments Truthful ~:** labels are soft. Confirmation that the UI never says “confirmed” was not re-read in `activity_surface.py` line by line in this session.
- **theme Truthful ~:** System-on-non-Windows resolves to light (`ui_prefs.py` docstring). Fine if the UI does not claim it detected a dark OS theme. Not executed here.
- **diagnostics Truthful ~:** buried engineering text. Honest if it does not pretend to be a repair tool. Not executed here.
- **knowledge-pack Truthful ~:** one “Knowledge” row hides landmark/logo/product. The word is broad; the code is a local JSON pack.
- **landmark / logo / product-pack Truthful ~:** catalog sentences are honest (`runtime_contract.py:201-217`); the ids are not shown in Home, so the over-name is in the catalog, not in the window.
- **qt-shell Truthful ✓:** Tk Home does not call it a second Home.
- **feature-registry Truthful ✓:** users never see the word registry.

---

## Code-only capabilities

“Code-only” here means no product UI control that runs the implementation. A dishonest strip row does not count as exposure of the underlying tool.

| Capability | Entry | Why code-only | Audits |
|---|---|---|---|
| feature-registry | `gui_registry.default_registry` | Internal shell table | Forensic audit said it was missing; it should stay internal |
| context-command-surface | `GuiCommand.surfaces` contains `context` | Declared, no widget | Exposure audit: do not pretend a menu exists |
| incremental-sha256-skip | `ingest` skip reason | Policy, not a screen | Stay internal |
| worker-count | `--workers`, `--reprocess` | Performance flags | Stay out of product UI |
| name-faces-batch | `review.name_faces` | Power-user CLI | Exposure audit: no GUI proposed as required |
| ignore-disposition | `review ignore --as` | CLI reason codes | Audit said a later secondary menu; not required to be internal forever, but it is internal now |
| search-face-id | `search.search_face` | Id lookup | Stay CLI |
| search-similar | `search.search_similar` | Non-face neighbour search | Audit: later, as its own command; not wired |
| ann-index | `ann_index.build_index` | Accelerator | Stay invisible (`home_shell.py:16-17`) |
| standalone-canvas | `canvas.run_canvas` | Second process door | Home uses the embed |
| sam2-spatial | `sam2_runtime.generate_regions` | Called by the visual job when ready | No separate control; keep it that way |
| visual-cache | `visual_cache.py` | Sidecar files | Stay internal |
| name-user-region | `Application.name_region` | API only | Audit: later inspector field; not exposed now |
| circuit-breaker | `circuits.before_call` | Backend safety | Must stay internal |
| color-object-ingest | `observers.observe_bgr` | No toggle; boxes are a side effect | Do not add a nav item |
| optional-modality-ingest | `resolve_product_observers` | Gate plus probes | Audit: status row later, never a sidebar item per observer |
| memory-graph-rows | `snapshot_memory_graph` | `confirmed=0` rows, no graph | Stay internal until copy can stay honest |
| report | `report.write_report` | CLI file | Audit: later, soft report only |
| restore-library | `store.restore_store` | Lab, destructive | Stay lab |
| integrity | `store.integrity_report` | Lab readout | Stay lab |
| model-install | `semblon lab install` | No downloader, no Home button | Stay lab; strip should not imply a button that is not there |
| lab-providers-models | `lab providers`, `lab models` | Engineering honesty | Diagnostics may mirror them; product nav must not |
| screen-capture | `lens.capture_screen` | Lab. Strip row is not a control | Audit: not in product UI |
| eval-harness | `lab eval` | Engineering | Never in the product shell |
| observatory | `lab observatory` | Engineering | Never in the product shell |
| engineering-probes | `lab profile/opencv/ipc-probe/r3-bakeoff/live-overlay` | Engineering | Never in the product shell |
| schema-store | `store.py` | No browser | Stay internal |
| qt-shell | `semblon shell` | Optional extra window | Do not advertise inside Tk Home |
| grounding-lens as a gesture | `lens.ground_selection` | Runs from query, not from mouse-up | The rectangle fallback is intentional |
| landmark, logo, product-pack | `knowledge.lookup` kinds | Folded into Knowledge or lab | Do not add three sidebar items |

Borderline, not counted as code-only: identify, history, backup, export views, and the one-shot watch command are on More or the inspector. Continuous `watch.watch_folder` is still code-only.

---

## Over-named capabilities

| Capability | Current name | What it does | What the name implies | Truthful name (not implemented) |
|---|---|---|---|---|
| capability-honesty-strip | Available / Optional · install needed | Paints `CapabilitySpec.default_model` | A live “is it installed?” check | Catalog (not checked on this computer) |
| lens-honesty-rows | Available understanding | Same defaults, shorter list | These understandings are actually available | Same as the strip |
| folder-watch | Watch a folder… | One ingest via `_start_process` | A continuous watch | Add or update this folder |
| photo-grid vs sidebar | Photos | Landing dashboard | The photo grid | Library, with Browse photos kept for the grid |
| activity “Review people” | Review people | `_navigate("unknown")` | Opens Review | People to name |
| region-similar command | Find similar photos | Opens Select a region | A distinct search action | Select a region (the mouse-up already searches) |
| visual-embedding | Visual embedding | Optional SigLIP, usually absent | A ready similarity model | Similar pictures (not installed) |
| grounding-lens | Grounding | SAM 2 outline or the same rectangle | A grounding product | Outline this selection |
| describe-vlm | Describe | Local describer, default DISABLED; often the pixel model | A captioning model | Experimental local description |
| translation | Translation | JSON dictionary, Argos only if imported | Neural translation | Dictionary translation |
| knowledge-pack | Knowledge | One local JSON pack | A knowledge base | Local pack |
| landmark | Landmark | Pack substring | A world landmark model | Pack match (catalog already says this) |
| logo | Logo | Pack substring | A logo crawler | Pack match |
| product-pack | Product | Pack or barcode match | Product recognition | Pack match |
| screen-capture strip | Optional · not supported here | Default `UNSUPPORTED_RUNTIME` on every OS | This computer cannot capture | Checked only by `semblon lab capture` |
| face catalog default | Face provider / MISSING | FaceKit is the identity engine | FaceKit is not installed | Do not show this default as product status |
| people-list | People | Text list in the inspector | A face gallery | Named people |
| inbox GUI | People to name | Unnamed clusters | The four inbox buckets | People to name (already closer than “Unknown”) |
| search box | Search | Person name, then OCR text | People only, until the hint | Search people or text |
| video-grid | Videos | A grid of video media | A player with tracks | Video stills |
| memory-moments | Moments | Burst/day/folder signals | Edited events | Times and folders |
| live-overlay | Live… | Index / RTSP / seconds prompts | A finished live product | Camera (experimental) |
| stats tile | Observations | A count of observation rows | A user concept | Needs a plainer noun; the count itself is real |
| home_shell docstring | Ready vs Not installed | Code titles are Available / Optional | Those older words are on screen | The docstring is the stale name |
| product_exposure “Live / Watch” | One SECONDARY row | Two commands | One continuous surface | Split the classification |
| UI-EXPOSURE-MAP strip words | Ready / Not installed | Code no longer uses them | The map matches the window | Available / Optional · component required |
| sam2 name collision | SAM 2 / Grounding | Lens rectangle outline vs Canvas proposals | One SAM 2 feature | Ground a selection / discover regions |

---

## Uncertainties

1. **No execution at this commit.** Pytest was not run. Tk was not started. ORT providers were not queried. “Works” is ~ for that reason. The APP-1 C.3 Windows record is dated 2026-09-22 and predates visual jobs, the feature registry, and `sam2_runtime.py`.
2. **Weight files on a real PC.** SigLIP, SAM 2, VLM, translation dictionary, and buffalo_l presence cannot be known from the git tree. `probe_*` would answer on that machine. Home does not call those probes for the strip (`home_ui.py:2444`).
3. **`lab providers` override scope.** A prior read of this tree said `semblon lab providers` applies a live override for OCR and not for every catalog id. This session did not re-open the providers dispatcher, so the exact override set is unverified here.
4. **Diagnostics versus integrity.** The exposure audit says diagnostics may mention store health (`advanced_diagnostics.py`). This session did not re-read that function, so whether integrity text is actually shown is unverified.
5. **Activity “confirmed”.** `relationships.confirmed` is written as 0 by the snapshot path (exposure audit). This session did not re-read every Activity string in `activity_surface.py` to prove the word “confirmed” is absent.
6. **`name_user_region` tests.** `test_user_proper_name_is_not_a_person` proves a proper name is not a person. It may not call `user_region.name_user_region` specifically. That call’s test name was not confirmed.
7. **Ingest video flags.** The ingest command is documented as sampled video (`cli.py:11`, `cli.py:241`). Per-flag defaults (`--hz` and siblings) were not re-listed in this pass. The Videos grid and `source_type=video` are confirmed.
8. **GPU checkbox on ARM64.** `select_execution_provider` is live code (`home_ui.py:4153`). Whether DirectML appears in the product venv was not run. ARM64 OpenCV load stays **BLOCKED** and is a different binary problem.
9. **Stale line numbers in the two audits.** Many citations point at `142e36f` or `646d44b` (for example `cli.py:1126` for `home`). At `35eeb72`, `home` dispatches at `cli.py:1177-1181`. Behavior notes were re-checked; old line numbers were not.
10. **Dual SAM 2 env vars.** Lens uses `SEMBLON_SAM2_CHECKPOINT` and `SEMBLON_SAM2_CONFIG` (`lens.py:128`, `249`). Visual discovery also consults `SEMBLON_SAM2_WEIGHTS` (`docs/VISUAL-REGIONS.md`, `visual/discovery.py`). This session did not execute either probe, so which file wins when both are set is unverified.

---

## Summary

At `35eeb72` the product window is still one Tk Home. Identity, ingest, review verbs, People, Videos, Activity, Lens, and Settings are real doors. A feature registry now feeds the sidebar, the More menu, Ctrl+K, and a few inspector commands, which makes the September 27 exposure matrix wrong about identify, history, backup, person-folder export, and “no registry.” It remains right that continuous folder watch, `search --similar`, batch face naming, ignore reasons, review notes, region naming, screen capture, restore, and the lab tools are not honest product controls.

The least truthful surface is the one that looks most like a status panel. The landing strip and the Lens understanding list are a static catalog: they render `default_model` and will keep saying “install needed” or “not supported here” after a weight file or a Windows capture stack is present. “Watch a folder…” and sidebar “Photos” are the other labels that promise a different behavior than the function they call. Optional models, SAM 2 discovery, and SigLIP stay partial, local, and off the identity path.
