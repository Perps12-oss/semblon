# Semblon UI exposure map

**Current-source addendum — 2026-10-27.** This opening section describes the production shell at the branch tip. The September inventory below is retained as historical audit material; do not use its Tk Home, `Shell.qml`, HomeLaunchpad, or persistent-left-navigation descriptions as current implementation facts.

**Production entry:** `semblon shell` → `native_shell/run.py` → `native_shell/host.py` → `Application` / `ShellBridge` → `native_shell/qml/Table.qml`. The production QML root is **Table.qml**, not Shell.qml. The host exposes one `ArchiveModel`, one `PeopleModel`, and the existing Similar model from the same Application/session.

**Current primary surfaces:**
- **Roll / archive:** `Roll.qml` is the photo roll; the time scrubber is the adjacent navigation edge.
- **Light Table:** `LightTable.qml` provides date, People, description search, Tidy, and More actions.
- **People:** `People.qml` is the face-group review desk. A group is not a person; explicit review/name decisions remain the only person-creation path.
- **Focus:** `Viewer.qml` opens a still, supports region selection and similar-region search, and shows matches in the bottom strip. Whole-photo, face, duplicate, naming and Ask actions remain contextual/overflow actions.
- **Discover (branch PR #200):** `DiscoverSheet.qml` offers People, Objects, Regions and Words in photos as category entry points. It routes into existing People, Focus, and text/object search paths; it does not create four galleries or separate archives.
- **Settings:** `SettingsBody.qml` includes Add a folder, **Check for new photos**, library health and activity. Check for new photos is the existing broad `reprocess=True` ingest route, not a category-specific backfill.

**Scanning status must not be inferred from a menu item.** Opening People, Objects, Regions, or Words does not start a scan. Discover has separate Check controls (`ShellBridge.startCategoryScan`) that run `category_backfill` for that category only. `rescanFolder()` remains the broad `reprocess=True` ingest route and is not a category scan. See `docs/decisions/2026-10-27-category-backfill.md`.

Product contract: `docs/PRODUCT.md`. Verified implementation status: `docs/BUILD-STATUS.md`. Architecture: `docs/ARCHITECTURE.md`.

---

**Historical inventory — 2026-09-25 onward.** The sections below record prior shells and audits. They are retained for traceability, not as current UI instructions.
**Date:** 2026-09-25  
**Rule:** Backend capability does not dictate navigation. Product intent dictates navigation.  
**Historical shell rule (2026-09-25):** One production GUI (`semblon home`, tk) → multiple workspaces/routes. Not separate apps or GUI stacks.

**Forensic audit (consolidation):** every GUI path is classified in
`semblon/product_exposure.py` (`GUI_PATHS`). Actions taken in this branch:
remove `Open review.html` and job-bar Canvas from product chrome; Review /
Explore / Live stay under More; export review page lives under Settings →
Advanced; Diagnostics holds runtime/provider/model/schema/job chrome;
Lens soft-copies capability labels; Search tries text when people
miss; capability strip uses Available / Optional · component required.

Authority companions: `docs/COMPLETION-MATRIX.md`, `docs/APPLICATION_API.md`, `docs/PRODUCT.md`, `docs/SEM-ARCH-V1.4.md`, **`docs/SHELL-IA.md` (LOCKED Model D)**.

## Vocabulary

| Class | Meaning |
|---|---|
| **CANONICAL** | Primary product surface inside Home. Users should find it without knowing CLI. |
| **SECONDARY** | Same app, demoted entry (More / Toplevel / overflow). Real workflow, not Home chrome. |
| **CLI** | Automation, power users, scripting. Not required in Home nav. |
| **LAB** | Engineering only (`semblon lab …`). Must not leak into product nav. |
| **KEEP** | Shipped but not the product Home; do not promote to a second shell. |
| **SUPERSEDED** | Must not be the default UX; retain as export/engineering if useful. |
| **STALE?** | Candidate to simplify, hide, or delete after an explicit product decision. |

---

## Target product IA (intent) — LOCKED Model D

**Authority:** `docs/SHELL-IA.md` (2026-10-02). Persistent MAIN sidebar is **not** the product model.

```text
HOME  (one tk process — semblon home)

  EMPTY / FIRST-RUN
    └── Home Stage     ← capability introduction (Explore · Discover · People)
                         Add folder = enabling CTA (not product definition)
                         Activity = operational pulse when relevant, not Stage peer

  MEDIA EXISTS
    └── Memory Canvas  ← Stage dissolves; media full-bleed
         ├── Explore filters in-canvas (All / Photos / Videos)
         ├── Discover   ← compact + contextual (media → region → action → result)
         ├── People     ← secondary mode + review badge (not face-app identity)
         ├── Activity   ← operational sheet / pulse
         └── Search     ← top compact field (memory search; not a Search app)

  UTILITY
    └── Settings       ← header utility; first-class when opened; not capability hierarchy

SECONDARY (same app routes / Toplevels — not separate GUI technologies)
 ├── Review             (evidence / name / merge / split)
 ├── Canvas             (observation workspace; also embeds media grid)
 └── Live / Watch      (optional continuous ingest surfaces)

CLI     → automation / power / diagnostics doors
LAB     → engineering only
```

**Backend ≠ nav:** FaceKit, SigLIP, OCR, VLM, packs, ANN, `lab query` / `lab index`, and the engineering name **Lens** are capabilities. They do not each get a permanent Home destination. Discover is the product word; Lens is not a MAIN chrome label.

**Chrome rule:** No permanent left-hand MAIN list (Library / People / Activity as peer destinations). Internal route ids may remain; product chrome follows SHELL-IA.

---

## A. Canonical production UI (inside `semblon home`)

**Historical heading (2026-09-25 inventory).** Not the 2026-10-05 production UI. Production UI is PySide6 `semblon shell` → `Application` (`docs/ARCHITECTURE.md`). Do not treat the table below as the current shell.

**IA (LOCKED for the legacy Tk client):** `docs/SHELL-IA.md` — Stage / Memory Canvas / contextual modes.  
**Code at 2026-09-25:** still carries historical MAIN sidebar chrome in `home_ui` / registry nav contributions. That chrome is **not** the locked Tk model; do not extend it. “Next shell slice must dissolve Stage → Memory” was that Tk step. It is not current product work.

Nav/registry source: `product_features.py` / `gui_registry` (internal route ids). CLI door: `semblon home` (`cli.py`).

| Route / control | Route id / entry | Implementation | Class / notes |
|---|---|---|---|
| Home Stage | empty / brand return | TBD shell slice; onboarding lives in `home_ui` / `fluid_shell` today | **CANONICAL** — capability introduction |
| Memory Canvas / Library | `library` / `photos` / `videos` / `canvas` | `home_ui`, `CanvasWorkspace` | **CANONICAL** — default after media exists |
| People | `people` | Home people surface | **CANONICAL** — secondary weight; not face-app identity |
| People to name | `unknown` | Inbox / board flatten | **CANONICAL** — review queue; badge entry preferred over MAIN row |
| Search | top compact field | `_search_person` / text fallthrough | **CANONICAL** — search memory |
| Activity | `activity` | `application.activity_memory` | **CANONICAL** — operational pulse/sheet, not MAIN peer |
| Discover (was Lens) | verbs + optional `lens` route id | region select / find similar / ask | **CANONICAL** — capability; **not** MAIN “Lens” destination |
| Settings | Settings button | `_show_settings` | **CANONICAL** — header utility |
| Settings → Advanced → Recovery → Reset app | On-demand under Advanced | `app_reset.reset_app_to_defaults` | **CANONICAL** — clears Semblon-owned rebuildable state only; never original media. Not everyday Settings. |
| Settings → Appearance defaults | Grid density / search mode / theme | `ui_prefs` keys | **CANONICAL** — everyday presentation prefs; same keys as chrome chips |
| Inspector verbs | right pane | merge / assign / split / name / rule-out / ignore | **CANONICAL** — soft labels via `product_surface`; on demand |
| Ingest / Pause / Cancel | Home job client | `JobEngine` via Application façade | **CANONICAL** — job controls, not nav |

**Canonical stack:** tk only. No Electron / Tauri / CustomTkinter / FastAPI product shell.

### Audit anchors (canonical)

- `HOME_NAV`: `semblon/home_ui.py:199-204`
- Brand Lens + Search + Settings chrome: `semblon/home_ui.py` (top bar Lens + `_open_lens` / `_build_lens_workspace`)
- `semblon home` help: `semblon/cli.py:449-451`

---

## B. Secondary workspaces (same app, demoted)

| Surface | Entry today | Code | Class |
|---|---|---|---|
| Review UI | More → Open Review / `semblon review-ui` | `review_ui.py`; optional `review_chrome/` | **SECONDARY** · **KEEP** evidence vertical (Toplevel on Home) |
| Canvas (standalone / Explore) | More → Explore / `semblon canvas` | `canvas.py` | **SECONDARY** (also embedded under Photos) |
| Live overlay | More → Live… | `live_overlay.py` | **SECONDARY** · experimental continuous surface |
| Folder watch (continuous) | CLI only — Home More “Add or update…” is **one-shot ingest**, not `watch.watch_folder` | `semblon watch` | **CLI** · deferred product SECONDARY (requires explicit continuous UI, not silent Add Folder) |
| `review.html` | Settings → Advanced → Open export review page | `export.py` / `_open_html` | **SUPERSEDED as UX** · export artifact only |

### Audit anchors (secondary)

- More menu: `semblon/home_ui.py:994-1005`
- Review Toplevel: `semblon/home_ui.py:3267-3278`
- `semblon review-ui` / `canvas` / `watch` / `live`: `semblon/cli.py:433-527`

---

## C. CLI (automation / power / scripting)

Not Home navigation. Doors for scripts and power users. Defined in `semblon/cli.py`.

| Command family | Purpose | Exposure class |
|---|---|---|
| `process` / `ingest` / `cluster` / `export` | Headless pipeline | **CLI** |
| `name` / `merge` / `split` / `review *` | Corrections without GUI | **CLI** |
| `identify` / `inbox` / `stats` / `report` | Identity ops + read-only reports | **CLI** (`report` must not write the store) |
| `memory history\|together\|events` | S6 memory — not identity | **CLI** · product soft surface under Home **Activity** (`application.activity_memory`); CLI remains the power door |
| `tracks` | Video track lanes | **CLI** / Canvas data |
| `search` | Broader than Home people search | **CLI** · Lens should absorb product visual-search intent |
| `watch` | Incremental folder poll | **CLI** → optional **SECONDARY** later |
| `live` | Camera / RTSP pipeline | **CLI** · Live overlay is the thin GUI |
| `home` / `review-ui` / `canvas` / `shell` | GUI launchers | See A / B / F — not “more CLI features” |

---

## D. LAB (engineering only)

`semblon lab …` — must stay out of product nav (`cli.py` lab subparsers).

| Lab command | Purpose |
|---|---|
| `profile` | FACE-000 runtime probe |
| `observatory *` | Golden snapshot / freeze / compare / enter |
| `backup` / `restore` / `integrity` | Store ops |
| `models` / `providers` | Weight / provider honesty |
| `install` / `index` / `query` / `capture` | Model file install + Lens backends without product chrome |
| `opencv` / `ipc-probe` / `r3-bakeoff` | Probes / bake-off |
| `eval *` | Confirmatory eval harness |
| `live-overlay` | Lab live harness (Home already has Live…) |

---

## E. Backend capabilities vs product intent (Lens)

Users must not learn provider names (`embed_siglip`, `translate_text`, `ground_selection`, `describe_vlm`, OCR observers, knowledge packs, ANN). Product verb: **ask about this picture**.

```text
Open photo → Lens → select region → Semblon runs available capabilities
→ honest result (SUCCESS / NO_RESULT / UNAVAILABLE)
```

| Capability id | Backend | Product exposure today | Target |
|---|---|---|---|
| `library_query` | search / library | Home search + Ready list | Stay under Search / Lens |
| `face` | FaceKit / InsightFace | Photos / People / Review | Identity firewall unchanged |
| `visual_embedding` | SigLIP ONNX | Listed Not installed; `lab query` | **Lens** when AVAILABLE |
| `ocr` | tesseract observers / lens | Ingest optional; lab | **Lens** / Search text |
| `translation` | dict / Argos | lab | **Lens** result action |
| `grounding` | SAM2 or rect | region select → query | **Lens** selection |
| `barcode` | symbology | lab | **Lens** |
| `vlm` | local describer (often Off) | listed Off | **Lens** if AVAILABLE |
| `lkg` / landmark / logo / product | JSON packs | lab | **Lens** / knowledge |
| `screen_capture` | privacy + grab | `lab capture` | Optional Lens source — not Home chrome |
| `ann_index` | `.semblon-index.npz` | `lab index` | Invisible accelerator under Lens/Search |

**Circuit breaker** (`circuits.py`): backend only — do not invent a Home toggle per circuit.  
**Do not** add one sidebar item per `CapabilitySpec` / `LENS_CAPABILITIES` (`lens.py`).

---

## F. KEEP / SUPERSEDED / STALE? GUI implementations

**Historical classification (2026-09-25).** Rows that call Tk Home canonical, or Qt `semblon shell` optional, are superseded. Production UI is PySide6 → Application. `review.html` is retired.

| Implementation | Class | Action |
|---|---|---|
| PySide6 `semblon shell` | **CANONICAL** | Sole product shell |
| tk `semblon home` | **SUPERSEDED** | Removed 2026-10-15 |
| `semblon review-ui` / `canvas` | **SUPERSEDED** | Removed 2026-10-15 |
| `review_chrome/` (HTML host) | KEEP / engineering chrome for Review | Not a second app |
| `review.html` as primary UX | **SUPERSEDED as UX** | Export only — Settings → Advanced |
| Job-bar **Canvas** as equal primary chrome | **STALE → removed** | Photos embed + More → Explore |
| Job-bar / More **Open review.html** | **STALE → removed** | Prefer Review workspace; export under Advanced |
| Marketing three-step brochure on populated Home | **SUPERSEDED** by library shell (#93) | Do not revive |
| Advanced diagnostics (Settings → Diagnostics) | Settings-adjacent · not nav | Engineering honesty; do not promote to sidebar |
| Permanent Tk AppShell / Electron / Tauri / CustomTkinter / FastAPI shell | **Forbidden** | Refuse |

---

## G. Product gap notes (Lens)

**Lens / Inspect** is a Home route/workspace (not a thin button that only opens a Toplevel):

- Unify mechanism: open photo → Lens → select something → Semblon understands/searches it.
- Backend decides which capabilities are available; missing models say so honestly.
- Home nav stays intent-shaped (Photos / People / Search / Lens…), not model-shaped.

Remaining honesty: optional model install / Windows verification of every Lens backend stays PARTIAL in COMPLETION-MATRIX — not a second GUI.

---

## H. What this map is not

- Not a FACE / clustering retune queue  
- Not permission to invent Electron or a second Home  
- Not a claim that every CLI command needs a button  
- Not Windows verification of Lens backends (see COMPLETION-MATRIX schema list = PARTIAL)

When adding UI, update this file’s class for the surface in the same PR.

---

## I. Five-repo product synthesis (2026-10-03) — historical

**Historical.** The landed/deferred table below describes a Tk Home pass. It is not the 2026-10-16 build status. Use `docs/BUILD-STATUS.md`.

**Final state claim:** Product synthesis complete; some capabilities deliberately deferred.

**CLOSED AS DEFERRED criterion:** A product gap is not unresolved merely because backend capability is absent. If missing capability is explicitly identified, documented, and intentionally outside this pass, it is **CLOSED AS DEFERRED**.

Status vocabulary: **LANDED** (end-to-end) · **WIRED** (existing capability correctly exposed) · **PARTIAL** (useful + bounded limitation) · **DEFERRED** (deliberately not implemented; dependency/contract absent).

Locked similarity taxonomy (do not collapse):

| Class | Meaning | Product surface |
|---|---|---|
| **A** | Integrity similarity — Exact (SHA-256) + Near (aHash/dHash) | Find Duplicates |
| **B** | Whole-image similarity — `search.search_similar` | Search mode Whole image |
| **C** | Region similarity — Find Similar / `region_search` | Discover Find Similar · Search mode Region |

Find Similar must **not** call `search_similar`.

### Landed / wired in this pass

| Item | Status | Evidence | Remaining dependency |
|---|---|---|---|
| Timeline browse | **LANDED** | `library_browse.timeline_buckets` → Canvas `media_ids` | — |
| Folders browse | **LANDED** | `library_browse.folder_buckets` | — |
| Moments (named-person events) | **LANDED** | `memory.events` publishes `media_ids`; Moments facet | — |
| A exact duplicates | **LANDED** (kept) | `find_exact_duplicate_groups` | — |
| A near duplicates | **LANDED** | `find_near_duplicate_groups` OpenCV aHash/dHash + Hamming; Home Exact/Near | — |
| B whole-image search | **WIRED** / **PARTIAL** | Search mode Whole image → `search_similar_media` | Non-face embeddings for seed media |
| C region Find Similar | **LANDED** + relabel | Region basis in chrome; firewall vs `search_similar` | — |
| Unified Search modes | **LANDED** | People \| Text in photos \| Whole image \| Region | — |
| Saved Regions | **WIRED** | `list_user_regions` Home surface | — |
| Inspector depth (wireable) | **LANDED** | `inspector_present` File / When·where / Observations | — |
| Grid ViewModel + density + virtualization | **LANDED** | `media_grid` + Canvas viewport overscan | — |
| Context menu Button-3 | **WIRED** | `context_menu` over `surfaces=context` | — |

### CLOSED AS DEFERRED (exact dependency)

| Finding | Status | Prerequisite / dependency |
|---|---|---|
| User Collections / Albums | **DEFERRED** | Persistent album/collection schema + product contract; Moments is not albums. Honest empty copy only. |
| Durable Keep/Reject | **DEFERRED** | Designed persistence/domain contract (no cull `decisions` kind); Compare session-only remains valid. Identity `reject` is the wrong table. |
| Continuous folder watch | **DEFERRED** | Explicit SECONDARY continuous UI calling `watch.watch_folder`; must **not** silently change Add Folder. |
| Related (library graph) UI | **DEFERRED** | Dedicated Related backend; do not promote spatial `related_labels` or ANN lab as Related. |
| Maps | **DEFERRED** | Map presentation surface; GPS may already appear in Inspector when present. |
| Tags / ratings | **DEFERRED** | No schema columns; omit from Inspector (no fake rows). |
| Semantic identity hypotheses | **DEFERRED** | Explicit SEM-ARCH authorization; identity firewall unchanged. |

### Audit anchors (this pass)

- Browse facets: `semblon/library_browse.py`, Home `_open_browse_facet`
- Near-dup: `semblon/duplicates.py` (`find_near_duplicate_groups`)
- Search modes: Home `_run_unified_search` / `SEARCH_MODES`
- Inspector: `semblon/inspector_present.py`
- Grid: `semblon/media_grid.py` consumed by `CanvasWorkspace`
- Context: `semblon/context_menu.py` Button-3 on grid/preview
