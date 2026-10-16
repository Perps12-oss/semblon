# Capability inventory, hidden register, and exposure matrix

**Superseded 2026-10-05 by the completed PySide6 production migration.**

**Historical inventory.** Production UI is PySide6 `semblon shell` → `Application`. Capability status is `docs/BUILD-STATUS.md`. The tables below are the 2026-09-27 inventory. Where they name Tk as the shipping path or `review.html` as an export the process writes, that line is historical.

**Date:** 2026-09-27. **Retest:** 2026-09-28 against `origin/main` `646d44b` and PR #112 (`cursor/gui-feature-registry-c466`, not merged).  
**Source of the tables below:** `main` at `142e36f`, adjusted by the retest notes.  
**Rule:** a capability is listed because a function, CLI parser, schema table, or test exists. Docs alone are not evidence.  
**This audit did not execute the Windows GUI or pytest.** “Production-ready” means the shipping Tk path calls it and the module is on the product side of `semblon lab`. It does not mean this environment re-verified Windows.

Legend for the exposure matrix at the end: **EXISTING**, **PARTIAL**, **MISSING**, **UNKNOWN**.

Identity firewall (unchanged by this research): FaceKit is the only identity compare. Geometry, color, OCR, CLIP, objects, and Lens results must not write `faces.person_id` or `embeddings.modality='face'`.

---

## Capability inventory

| Capability | Implemented? | Production-ready? | User-facing? | GUI exposed? | Current entry point | Evidence |
|---|---|---|---|---|---|---|
| Product window | Yes | Yes (Tk Home is the product door) | Yes | Yes | `semblon home` | `cli.py:1126-1129`, `lens_home.py:102-107`, `home_ui.py:4338` |
| Optional Qt window | Yes | Optional extra, not product Home | Only if the user knows `semblon shell` | Separate window, divergent nav | `native_shell/run.py:8` | `cli.py:460-463`, `native_shell/window.py:134-136` |
| Choose folder + ingest + cluster | Yes | Yes on the Home job path | Yes | Yes — Add folder / Choose folder | `JobEngine.submit_ingest` → `process_folder` | `jobs.py:114-125`, `home_ui.py:3462` |
| Incremental skip by sha256 | Yes | Yes, default ingest behavior | Silent | No duplicate browser | `media_skip_reason` | `ingest.py:145-158`, `store.py:38-47` UNIQUE sha256 |
| Resume interrupted ingest | Yes | Yes when Home sets resume | Partial — Resume control | Pause/Resume on the progress bar | `process.find_resumable_run`, `--resume` | `cli.py:297-300`, `home_ui.py:3286-3294` |
| Pause / cancel between files | Yes | Yes | Yes | Yes | `JobEngine.pause/cancel` | `jobs.py:100-105`, `home_ui.py:3442-3454` |
| GPU preference | Yes | Honesty depends on ORT providers | Yes, if a GPU EP exists | Settings checkbox only when `select_execution_provider` reports GPU | `home_ui.py:4108-4131` | `engine.select_execution_provider` |
| Face detect + embed (FaceKit) | Yes | Identity engine | Indirect — user sees faces and groups | Photos/People/Review, not a “FaceKit” control | `providers.FaceKitProvider` | `providers.py:24-61`, `HOME_OBSERVERS` `home_ui.py:194` |
| DBSCAN grouping | Yes | Frozen params; Home job runs cluster inside `process_folder` | Groups, not a clustering screen | Result card “groups”; no eps control in GUI | `cluster.cluster_run` | `cli.py:303-307` (eps flags are CLI) |
| Name a cluster or face | Yes | Yes | Yes | Inspector “Name this person”; Review Name | `review.name_cluster` / `name_face` | `review.py:332`, `review.py:423`, `home_ui.py:1964` |
| Name several unassigned faces | Yes | CLI | Power user | No | `semblon name --faces` | `cli.py:330`, `review.name_faces` `review.py:498` |
| Name a video track | Yes | CLI + Review track row | Review can name a track | Review UI only, not Home inspector | `review.name_track` | `review.py:628`, `review_ui.py:819-826` |
| Attach to existing person | Yes | CLI `--attach-to`; GUI Assign | Yes if user opens People then a group | “Add to person” | `inspector_verbs` VERB_ASSIGN | `inspector_verbs.py:129-133`, `product_surface.py:17` |
| Merge clusters | Yes | Yes | Yes | “Combine face groups”; Review Merge | `review.merge_clusters` | `review.py:662`, `home_ui.py:1891` |
| Split cluster | Yes | Yes, needs face selection | Yes, easy to miss | “Split faces”; status tells user to open Review to compare | `review.split_cluster` | `review.py:779`, `home_ui.py:1812-1822` |
| Ignore | Yes | Yes | Yes | Inspector Ignore; Review Ignore | `review.ignore_subject` | `review.py:892`, `home_ui.py:1997` |
| Ignore disposition (`not_a_person`, singleton, junk) | Yes | CLI `--as` | Power user | GUI confirm dialog does not offer the disposition | `cli.py:409-412` | `review_ui.apply_ignore` |
| Review note | Yes | Yes in Review UI and CLI | Review UI | Home inspector has no Note button | `review.note_subject` | `review.py:978`, `review_ui.py:1088` |
| Rule out | Yes | Default ON; env opt-out | Yes | “Not this person” | `review.rule_out_subject` | `review.py:1057`, `gates.py:15`, `product_surface.py:20` |
| Inbox buckets | Yes | CLI prints KNOWN / UNKNOWN / REVIEW_REQUIRED / REJECTED | Partial | People to name uses unnamed clusters, not the four buckets | `inbox.inbox` | `inbox.py:75`, `cli.py:364-367`, `home_ui.py:3806-3860` |
| Identify 1:N vs named persons | Yes | CLI | No in GUI | Missing | `identify.identify_face` / `identify_run` / `identify_image` | `identify.py:178`, `cli.py:357-362` |
| People list | Yes | Yes | Yes | Sidebar People — text list in the inspector, not a gallery | `search.search_people` | `search.py:111`, `home_ui.py:3733-3792` |
| Search person by name | Yes | Yes | Yes | Top search box | `search.search_person` | `search.py:44`, `home_ui.py:3928-3983` |
| Search face id | Yes | CLI `--face` | No | Missing | `search.search_face` | `search.py:95`, `cli.py:478` |
| Search OCR text | Yes | CLI `--text`; Home falls through when people miss | Partial, unlabeled | Same search box, no “search text” affordance | `search.search_text` | `search.py:342`, `home_ui.py:3955-4004` |
| Search similar observation | Yes | CLI `--similar`; requires embeddings | No | Missing as its own action | `search.search_similar` | `search.py:189`, `cli.py:481` |
| ANN index | Yes | Lab rebuild; search can use it | No (by design) | Not a nav item | `ann_index.build_index` | `ann_index.py:19`, `cli.py:87-91` |
| Photo grid | Yes | Yes on route `photos` | Hard to find | Not the sidebar Photos item | `CanvasWorkspace` `source_types=folder` | `home_ui.py:3334-3343`, `2177-2182` |
| Video grid | Yes | Yes | Yes | Sidebar Videos | `home_ui.py:3345-3347` | `canvas.py:378` |
| Canvas hover / click face or object | Yes | Yes on the grid | Yes once a photo is open | Outline + inspector | `canvas.py:505-510`, `974` | `product_surface.soft_inspector_for_*` |
| Canvas drag hit-test | Yes | Yes | Yes, tip text on the preview | Inspector lines for hits; no action menu | `canvas.py:1016-1057` | `product_surface.region_hits` |
| Explore all media types | Yes | Secondary | More menu | “Explore workspace” | route `canvas` | `home_ui.py:1013-1014` |
| Standalone canvas process | Yes | CLI | Power user | More menu navigates inside Home instead of a new process | `canvas.run_canvas` | `canvas.py:1086`, `cli.py:1273-1277` |
| Lens route | Yes | Yes as a page | Yes | Sidebar Lens + brand button | `home_ui.py:1495-1568` | |
| Persist user rectangle | Yes | Yes on region mouse-up | Yes | “Select a region” | `user_region.persist_user_region` | `application.py:200-222`, `user_region.py:54` |
| Name a saved region | Yes | API | No | Missing | `user_region.name_user_region` | `user_region.py:171`, `application.py:229-232` |
| Similar-looking region (color histogram) | Yes | Yes on product mouse-up | Yes, copy says “similar” not “identified” | Lens region result lines | `region_search.remember_and_find` | `region_search.py:43-59`, `lens_release.py:83-96` |
| Lens capability query (OCR, barcode, grounding, SigLIP, translation, VLM, packs) | Yes as code | Catalog rows default MISSING or DISABLED until files exist | Honesty list + “Ask about this photo” | Whole-image query, not the region gesture | `lens.query_image` | `lens.py:25-36`, `589`, `home_ui.py:1572-1635`, `runtime_contract.py:131-220` |
| Screen capture query | Yes | Windows-only; catalog default UNSUPPORTED_RUNTIME off Windows | Lab | Missing in Home | `lens.capture_screen` / `query_screen` | `lens.py:473`, `cli.py:106-114` |
| Local knowledge packs | Yes | Lab lookup | No | Invoked only inside `query_image` if packs exist | `knowledge.lookup` | `knowledge.py:51`, `runtime_contract.py:189-219` |
| Optional observers color / object | Yes | In `HOME_OBSERVERS` | Indirect (boxes on canvas) | No settings toggle | `observers.observe_bgr` | `home_ui.py:194`, `observers.py:524` |
| Optional OCR / CLIP / pose at ingest | Yes | When `SEMBLON_MODALITY_PRODUCT` and probes succeed | No control | Not in Settings (diagnostics can list them) | `observers.resolve_product_observers` | `observers.py:243`, `gates.py:45-48` |
| Circuit breaker | Yes | Backend | No | Must not be a per-capability toggle | `circuits.py:14-38` | |
| S6 memory: together | Yes | Yes, read-only | Yes | Activity “People together” | `memory.together` | `memory.py:343`, `activity_surface.py:266` |
| S6 memory: moments / events | Yes | Yes, read-only | Yes | Activity “Moments” | `memory.events` | `memory.py:459`, `activity_surface.py:28` |
| S6 memory: one person’s history | Yes | CLI | No timeline UI | Missing | `memory.history` | `memory.py:323`, `cli.py:380-383` |
| Relationship + event snapshot rows | Yes | Written on review/cluster snapshot; `confirmed=0` | Soft lines only | No graph | `observers.snapshot_memory_graph` | `observers.py:795-856`, `review.py:33-37` |
| Derived video tracks | Yes | CLI; Review loads them | Review track cards | No Home track lane | `tracks.derive_tracks` | `tracks.py:285`, `review_ui.py:230-245` |
| Sampled video ingest | Yes | Ingest path | Videos nav shows `source_type=video` media | Grid, not a player with tracks | `cli.py:230-232` ingest help | `store.py` media `source_type` includes `video` |
| Live / webcam / RTSP | Yes | Gate default ON; explicit start | More → Live… | Technical prompts (camera index, RTSP, seconds) | `live_overlay.run_live_overlay` | `home_ui.py:4256-4313`, `gates.py:41-43` |
| Folder watch | Yes | CLI | No | Missing | `watch.watch_folder` | `watch.py:24`, `cli.py:488-497` |
| Activity / recent processing counts | Yes | Yes | Yes | Activity first section | `activity_surface._processing_stats` | `activity_surface.py:181`, `401-416` |
| Stats | Yes | CLI, read-only | No | Home stat tiles are a different, smaller set | `stats.stats` | `stats.py:25`, `cli.py:369-371`, `home_shell.py:108-129` |
| Report markdown | Yes | CLI, writes `--out` only | No | Missing | `report.write_report` | `report.py:46`, `cli.py:373-376` |
| Export review.html | Yes | Export artifact | Settings → Advanced | “Open export review page…” | `export.export_review` | `export.py:577`, `home_ui.py:4195-4200` |
| Export person view folders | Yes | CLI `--views` | No | Missing | `export.export_views` | `export.py:640-647`, `cli.py:313` |
| Review UI (Name/Merge/Split/Ignore/Note/Rule out) | Yes | Secondary Toplevel | More → Open Review | Yes, demoted | `review_ui.ReviewApp` | `review_ui.py:847`, `home_ui.py:1008` |
| review.html as the product UI | Superseded | Export only | Advanced only | Not primary chrome | `home_ui.py:3716` | `product_exposure.py:138-144` |
| Backup / restore store | Yes | Lab | No | Missing | `cli.py:69-75` | |
| Integrity report | Yes | Lab | No | Diagnostics may mention store health; not a user repair flow | `cli.py:76-77` | `advanced_diagnostics.py:185` |
| Model file install (no download) | Yes | Lab | No | Missing | `model_install` via `cli.py:80-86` | |
| Provider / model honesty | Yes | Diagnostics + Home capability rows | Partial | Landing “Available / Optional”; catalog labels can be technical | `home_shell.capability_sections` | `home_shell.py:60-105`, `runtime_contract.py:119` |
| Advanced diagnostics | Yes | Engineering surface | Settings → Diagnostics | Yes, buried | `advanced_diagnostics.py:90` | `home_ui.py:4248` |
| Theme light/dark/system | Yes | Yes | Yes | Settings Appearance | `ui_prefs`, `home_ui.py:4140-4157` | |
| Change library file | Yes | Yes | Yes, asks for `store.sqlite` | Settings | `home_ui.py:4230-4245` | |
| Empty states | Yes | Yes | Yes | Per-route copy | `empty_states.py` | used from `home_ui.py:46-66` |
| Command palette | Partial | Jump list only | Ctrl+K, listed under Advanced shortcuts | Not an action search | `home_ui.py:3035-3079`, `product_surface.py:50-58` | |
| Keyboard shortcuts Ctrl+F, Ctrl+1…5 | Yes | Yes | Listed in Settings → Advanced | No shortcut cheatsheet in the sidebar | `home_ui.py:973-979` | |
| Eval sets / confirmatory score | Yes | Lab only | No | Must stay out of product nav | `eval.py`, `cli.py:186-228` | |
| Observatory snapshot / freeze / compare | Yes | Lab only | No | Forbidden in product chrome | `cli.py:33-67` | |
| OpenCV / IPC / bake-off probes | Yes | Lab only | No | Forbidden | `cli.py:115-184` | |
| Progress `on_event` spine | Yes | Yes | Progress copy | Home processing pane | `progress.py`, `home_ui.py:2742` | |
| Schema v4 tables | Yes | Store | Not a screen | No schema browser in product UI | `store.py:9-237` | tables: runs, media, observations, clusters, persons, faces, cluster_person, decisions, eval_*, observation_items, embeddings, tracks, track_members, observation_groups, group_members, relationships, events |
| Duplicate file browser | No separate feature | n/a | n/a | Missing | Skip is ingest policy, not a library view | `ingest.py:145` |
| Collections / albums | No | n/a | n/a | Missing | No module | |
| Command / action registry | No on `main`. Yes on PR #112 | `FeatureRegistry` on #112 only | No | Not in the shipping Home | `home_ui.py` methods on `main`; `product_features.py` on #112 | see retest row below |
| Context menu | No on `main` | n/a | n/a | Missing | No `Button-3` binding. PR #112 names a `"context"` surface and does not bind a menu | grep of `home_ui.py` on both trees |
| Open-vocabulary region hover (`VisualSegment`) | Yes on `main` `646d44b` | Partial (`JobEngine.submit_visual_analyze`) | Partial (`semblon` visual CLI added in #109) | Yes, once a photo is open on the canvas | Canvas hover/click. Sidebar Photos still opens the dashboard, not this grid | `visual_segment.py`, `canvas.py`, `tests/test_visual_understanding.py` (10 passed) |
| GUI feature registry | Yes on PR #112 only | `FeatureRegistry` | No | Not on `main` | Sidebar / palette / overflow / inspector commands from `product_features.py` | `gui_registry.py`; `tests/test_gui_registry.py` 12 passed on `1c40dd0` |

---

## Hidden capability register

Question used for each row: if a non-technical person opened Semblon once, how would they find this?

| Capability | Why it is hidden | Technical entry | Intended user task | Proposed natural UI | Interaction | Dependencies | Risks | When |
|---|---|---|---|---|---|---|---|---|
| Photo grid | Sidebar “Photos” opens the library dashboard (`home` → `_show_home_landing`). Grid is route `photos`. | More → Browse photos; landing CTA when the library is non-empty (`home_ui.py:2177`, `300-333`) | Look at my pictures | The Photos destination itself | Open Photos → grid; click a photo | Canvas, store | None if the dashboard remains a first-run / status state with a clear name (Library or Home), not the word Photos | Now, as an information-architecture fix, not a new engine |
| Full-face compare before split | Inspector status mentions Review only after a cluster is selected (`home_ui.py:1812-1822`) | More → Open Review | See the faces in a group and separate the wrong one | Contextual “Compare faces” on a selected group | Opens Review focused on that cluster (`focus_cluster_id` already passed, `home_ui.py:3683-3696`) | Review UI | Do not auto-split | Now |
| Review note | Note button exists only inside Review (`review_ui.py:1088`) | `semblon review note` | Remember why a group looks wrong | Inspector action when a cluster or face is selected | Text field, same as name | `review.note_subject` | Notes must stay decisions, not identity | Now, via a command, not a new page |
| Per-person history | Activity shows aggregate together/moments, not one person’s timeline | `semblon memory history --person` | When and where did I see this person? | Person inspector section | Select a person → “Show history” | `memory.history`; EXIF via `memory.when_where` | Time/place must not change identity scores | Now as a contextual command; not a sidebar item |
| Identify against people you have named | CLI only | `semblon identify` | Is this face someone I already named? | Contextual on a selected face, result is a suggestion | Confirm still goes through Name / Assign | `identify.identify_face`; threshold stays the existing one | Wrong identity is worse than unknown. UI must show a suggestion, never auto-assign | Later, after the command host exists. Do not retune the threshold |
| Inbox buckets beyond “to name” | GUI flattens unnamed clusters. KNOWN / REVIEW_REQUIRED / REJECTED are CLI | `semblon inbox` | See what still needs a human decision | People to name filters, plain language | Chips: To name, Needs a look, Set aside | `inbox.inbox` | Do not show bucket enum names | Later |
| Ignore reason | CLI `--as` | `semblon review ignore --as` | Not a person / junk / single photo | Secondary menu on Ignore | One extra choice | `review.ignore_subject` | Default can stay today’s Ignore | Later |
| Similar photos for a saved observation | CLI `--similar` | `semblon search --similar` | Find library items in the same non-face space | Command on a selected region or object | “Find similar” | Embeddings present; `search_similar` refuses to be identity | Must keep `modality != face` | Later; do not merge with FaceKit |
| Region capability query | Shipping mouse-up runs the color histogram path, not `query_image` | `semblon lab query` or “Ask about this photo” (whole frame) | What is in this box — text, barcode, outline | Contextual “Ask about this selection” | Same rectangle already drawn | Whatever providers are actually installed | Missing model must say unavailable, not “nothing matched” (`lens.py` module docstring) | Later, as a second command beside “Find similar” |
| Name a kept region | API only | `Application.name_region` | Call this thing something without making it a person | Inspector field on a user region | Name saved on the observation item | `user_region.name_user_region` | Must not create a person | Later |
| OCR / CLIP / pose ingest | Runs only when the modality gate and probes say ready. No user sentence in Settings | `SEMBLON_MODALITY_PRODUCT`, `observers.resolve_product_observers` | Read text in photos; optional extra observations | Settings → Processing honesty, not extra nav | Status: on / needs a component | Local weights, tesseract | Observers must not vote on identity | Later for a status row; never a sidebar item per observer |
| Folder watch | CLI | `semblon watch` | Keep a folder up to date | Settings or Activity: “Watch this folder” | Explicit start, cancellable | `watch.watch_folder`, JobEngine (today watch is its own loop) | Must not start a hidden always-on job | Later |
| Live camera | More menu, then two `simpledialog`s asking for an index or RTSP URL | `semblon live` | Watch a camera for a moment | A Live sheet with Start, only if the user asked | Explicit start, no auto-webcam (`gates.py:41-43`) | OpenCV capture, FaceKit | Out of frozen v1 product identity (live ID). Keep experimental and explicit | Later; do not promote to the sidebar |
| Person view folders | CLI | `semblon export --views` | A folder per named person without moving originals | Person or Settings action “Export views…” | Folder picker | `export.export_views` | Originals stay put (`export.py:641`) | Later |
| Report | CLI | `semblon report --out` | A readable summary file | Activity overflow | Save dialog | `report.write_report` (must not write the store) | Easy to leak ids if the markdown is raw | Later, and only the soft report |
| Stats beyond the five tiles | CLI | `semblon stats` | How many faces, groups, unknowns | Already partly on the landing tiles | Keep tiles; do not add a stats page | `home_shell.shell_stats` | Tile “Observations” is already technical (`home_shell.py:124-128`) | Now as copy (rename or drop the jargon tile); full stats stay CLI |
| Backup / restore / integrity | Lab | `semblon lab backup\|restore\|integrity` | Don’t lose the library | Settings → Library → “Copy library…” much later | Explicit, refuses overwrite unless forced | SQLite backup API | Restore can destroy a library | Later, not lab-branded |
| Model install | Lab, no downloader | `semblon lab install` | Turn on reading text / similar pictures | The Optional rows on the landing should explain the next human step | Link or instructions, not a silent download | `model_install` | Product rule: do not download weights from the app | Later as honesty, not a store |
| Screen capture | Lab | `semblon lab capture` | Ask about a screen region | Out of the photo library product | — | Windows, privacy window filter `privacy.py` | Easy to become surveillance. Keep lab | Not in product UI |
| Eval, observatory, probes, IPC, bake-off | Lab by design | `semblon lab …` | Engineering | Nowhere in the product | — | — | Leaking these into nav is a product bug | Never in the product shell |
| Qt shell | Separate command | `semblon shell` | Not a user task | Do not advertise inside Tk Home | — | PySide6 extra | A second Home | Keep optional; do not add features only there |
| Ctrl+K | No button. Listed under Settings → Advanced | `home_ui.py:974` | Jump, and later run an action | Keep the shortcut; add actions once a command registry exists | Type-to-filter | Today: `HOME_NAV` labels only | A palette of every lab command would be noise | Palette host now; action list after the registry |
| Ctrl+1…5 | Same | `home_ui.py:975-979` | Switch section | Keep, generate from nav contributions | Keys | Order must stay stable | Lens has no number | With the registry |
| Diagnostics | Settings bottom | `home_ui.py:4202-4217` | Something is wrong | Stay under Settings | Button | `advanced_diagnostics.py` | Runtime/provider jargon | Keep buried |
| review.html | Settings → Advanced | `home_ui.py:4195` | Open the export page | Stay export-only | Button | A file must exist | Users treating HTML as the app | Do not promote |
| Tracks as their own browser | Review includes track items; no Home lane | `semblon tracks` | Follow a face through a video | Video page, contextual | Open a video → tracks | `tracks.derive_tracks` | A track is not a person | Later |
| Connections graph | Rows exist (`relationships`) | Snapshot on review | Who appears with whom, beyond the Activity list | Activity detail, or a person inspector | Select a together-line | `memory.together` | Graph UI can imply confirmed social facts; rows are `confirmed=0` | Later, and the UI must not say “confirmed” |
| Worker count / reprocess | CLI flags | `--workers`, `--reprocess` | Performance / force redo | Not a normal control | — | Ingest | Reprocess rewrites embeddings; workers default stays 1 until a harness says otherwise | Not in the product UI |
| Dead library-home layout | Removed | `_show_library_home` deleted | Was a photos+review strip | Do not restore it | — | — | Reviving it silently changes Photos | Deleted in the audit fix |

---

## Feature exposure matrix

Engine = Python module on `main`. Service/API = `Application` method or a stable function a UI can call without widgets. CLI = `semblon` parser. Current GUI = shipping Tk Home. Contextual = should appear from a selection, not from the sidebar.

| Capability | Engine | Service/API | CLI | Current GUI | Natural GUI surface | Contextual? | Priority |
|---|---|---|---|---|---|---|---|
| Add a photo folder | EXISTING | EXISTING (`submit_ingest`) | EXISTING (`process`) | EXISTING | Landing + job bar | No | Keep |
| Pause / cancel / resume | EXISTING | EXISTING | PARTIAL (`--resume`) | EXISTING | Progress chrome | No | Keep |
| Photo grid | EXISTING | EXISTING (`canvas`) | EXISTING (`canvas`) | PARTIAL (route `photos`, not sidebar Photos) | Photos workspace | No | Now (placement) |
| Video grid | EXISTING | EXISTING | PARTIAL | EXISTING | Videos | No | Keep |
| Open one photo, hover, click | EXISTING | PARTIAL | MISSING | EXISTING | Photo stage | Yes | Keep |
| Drag a box, see stored hits | EXISTING | PARTIAL (`region_hits` is UI-side) | MISSING | EXISTING | Photo stage inspector | Yes | Keep |
| People list | EXISTING | EXISTING (`people`) | EXISTING (`search --people`) | PARTIAL (text list) | People workspace | No | Later (gallery) |
| People to name | EXISTING | EXISTING (`inbox`, `board`) | EXISTING | PARTIAL (unnamed clusters) | People to name | No | Keep; filters later |
| Name / assign / merge / split / ignore / rule out | EXISTING | EXISTING (`apply_*`) | EXISTING | EXISTING on inspector + Review | Inspector + context menu + palette | Yes | Now (one command, many surfaces) |
| Review note | EXISTING | EXISTING (`apply_note`) | EXISTING | PARTIAL (Review only) | Inspector + Review | Yes | Now |
| Compare faces in a group | EXISTING | PARTIAL | MISSING as a verb | PARTIAL (Review) | Context action on a group | Yes | Now |
| Search by person name | EXISTING | EXISTING | EXISTING | EXISTING | Top search | No | Keep |
| Search text in photos | EXISTING | MISSING on `Application` (`search_text` is a function) | EXISTING | PARTIAL (silent fallback) | Search results, labeled | No | Now (label the fallback) |
| Search this face against named people | EXISTING | MISSING on `Application` | EXISTING (`identify`, `search --face`) | MISSING | Face inspector, suggestion only | Yes | Later |
| Find similar (non-face) | EXISTING | PARTIAL (`remember_and_find_region`) | EXISTING | PARTIAL (Lens region uses histogram, not `search --similar`) | Region actions | Yes | Later |
| Ask capabilities about a photo | EXISTING | MISSING (`query_image` not on `Application`) | EXISTING (`lab query`) | PARTIAL (Lens whole-image button) | Lens | Yes | Keep honesty; region command later |
| Ask capabilities about a region | EXISTING | MISSING | EXISTING (`lab query` with x,y,w,h) | MISSING on the product mouse-up | Lens selection | Yes | Later |
| Capability unavailable state | EXISTING | EXISTING (`status_report`) | EXISTING (`lab providers`) | PARTIAL (landing + Lens rows) | Inline on the action, not only a list | Yes | Now, once actions exist |
| Activity together / moments | EXISTING | EXISTING (`activity_memory`) | EXISTING | EXISTING | Activity | No | Keep |
| One person history | EXISTING | MISSING on `Application` | EXISTING | MISSING | Person inspector | Yes | Now as first registry demo |
| Tracks | EXISTING | MISSING | EXISTING | PARTIAL (Review) | Video | Yes | Later |
| Live | EXISTING | MISSING | EXISTING | PARTIAL (More + dialogs) | Explicit sheet | No | Later |
| Watch folder | EXISTING | MISSING | EXISTING | MISSING | Activity or Settings | No | Later |
| Export HTML | EXISTING | PARTIAL (`review_document`) | EXISTING | PARTIAL (Advanced) | Settings export | No | Keep buried |
| Export person folders | EXISTING | MISSING | EXISTING | MISSING | People overflow | No | Later |
| Report file | EXISTING | MISSING | EXISTING | MISSING | Activity overflow | No | Later |
| Backup library | EXISTING | MISSING | EXISTING (`lab`) | MISSING | Settings, much later | No | Later |
| Diagnostics | EXISTING | PARTIAL | PARTIAL (`lab models/providers`) | PARTIAL | Settings | No | Keep |
| Theme | EXISTING | MISSING (prefs module) | MISSING | EXISTING | Settings | No | Shell |
| Command palette of actions | MISSING | MISSING | MISSING | PARTIAL (destinations only) | Ctrl+K | Yes | After registry |
| Context menu | MISSING | MISSING | MISSING | MISSING | Photo / person / region | Yes | After registry |
| Collections | MISSING | MISSING | MISSING | MISSING | — | — | Not in this research |
| User-installable plugins | MISSING | MISSING | MISSING | MISSING | — | — | Do not build |
| Lab eval / observatory / probes | EXISTING | MISSING | EXISTING | MISSING | Nowhere | No | Never in product chrome |

`UNKNOWN` was reserved for behavior this audit could not see in source. The Windows load of optional Lens models (SigLIP, SAM2, VLM, barcode) is **UNKNOWN** on a given machine until `status_report()` runs there. The code path treats missing files as MISSING or DISABLED (`runtime_contract.py:131-188`). That honesty path is EXISTING; whether a weight file is present on the owner PC is UNKNOWN from this repository alone.
