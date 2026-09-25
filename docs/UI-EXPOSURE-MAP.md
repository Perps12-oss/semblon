# Semblon UI exposure map

**Date:** 2026-09-25  
**Rule:** Backend capability does not dictate navigation. Product intent dictates navigation.  
**Shell rule:** One production GUI (`semblon home`, tk) → multiple workspaces/routes. Not separate apps or GUI stacks.

**Forensic audit (consolidation):** every GUI path is classified in
`semblon/product_exposure.py` (`GUI_PATHS`). Actions taken in this branch:
remove `Open review.html` and job-bar Canvas from product chrome; Review /
Explore / Live stay under More; export review page lives under Settings →
Advanced; Diagnostics holds runtime/provider/model/schema/job chrome;
Lens soft-copies capability labels; Search tries text when people
miss; capability strip uses Available / Optional · component required.

Authority companions: `docs/COMPLETION-MATRIX.md`, `docs/APPLICATION_API.md`, `docs/PRODUCT.md`, `docs/SEM-ARCH-V1.4.md`.

## Vocabulary

| Class | Meaning |
|---|---|
| **CANONICAL** | Primary product route inside Home. Users should find it without knowing CLI. |
| **SECONDARY** | Same app, demoted entry (More / Toplevel / overflow). Real workflow, not Home chrome. |
| **CLI** | Automation, power users, scripting. Not required in Home nav. |
| **LAB** | Engineering only (`semblon lab …`). Must not leak into product nav. |
| **KEEP** | Shipped but not the product Home; do not promote to a second shell. |
| **SUPERSEDED** | Must not be the default UX; retain as export/engineering if useful. |
| **STALE?** | Candidate to simplify, hide, or delete after an explicit product decision. |

---

## Target product IA (intent)

```text
HOME  (one tk process — semblon home)
 ├── Photos
 ├── Videos
 ├── People
 ├── Unknown            (nav label today: People to name; route id: unknown)
 ├── Search             (top bar today; still CANONICAL intent)
 ├── Activity
 ├── Lens / Inspect     ← unify visual ask (not one button per model)
 └── Settings

SECONDARY (same app routes / Toplevels — not separate GUI technologies)
 ├── Review             (evidence / name / merge / split)
 ├── Canvas             (observation workspace; also embeds Photos grid)
 └── Live / Watch      (optional continuous ingest surfaces)

CLI     → automation / power / diagnostics doors
LAB     → engineering only
```

**Backend ≠ nav:** FaceKit, SigLIP, OCR, VLM, packs, ANN, `lab query` / `lab index` are capabilities. They do not each get a Home sidebar item.

---

## A. Canonical production UI (inside `semblon home`)

Nav source of truth: `HOME_NAV` in `semblon/home_ui.py` (ASK / LIBRARY / PEOPLE / ACTIVITY). CLI door: `semblon home` (`cli.py`).

| Route / control | Route id / entry | Implementation | Class / notes |
|---|---|---|---|
| Library Home shell | `home` (sidebar label **Photos**) | `home_ui`, `home_shell` | **CANONICAL** — stats + Ready / Not installed honesty |
| Photos browse | `photos` / canvas stills | `CanvasWorkspace` embed | **CANONICAL** |
| Videos | `videos` | Canvas `source_types=video` | **CANONICAL** |
| People | `people` | Home welcome + `search_people` | **CANONICAL** — named people |
| People to name | `unknown` | Inbox / board flatten | **CANONICAL** — human decisions; Unknown is valid |
| Search | top bar | `_search_person` / analysing gate | **CANONICAL** — people-first today; Lens absorbs broader visual ask |
| Activity | `activity` | `application.activity_memory` via Home Activity workspace | **CANONICAL** — soft history / Memory (people together, moments, recent processing) |
| Lens / Inspect | `lens` + brand **Lens** | `_open_lens`, Lens workspace, `_open_region_select` | **CANONICAL** — Home route/workspace; open photo → select → soft results; backends decide availability |
| Settings | Settings button | `_show_settings` | **CANONICAL** — Library / Appearance / Processing / About; Advanced = shortcuts + export; Diagnostics = runtime/provider/model/schema/jobs |
| Inspector verbs | right pane | merge / assign / split / name / rule-out / ignore | **CANONICAL** — soft labels via `product_surface` |
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
| Folder watch | *not in Home nav* | `semblon watch` | **CLI** today → product candidate as **SECONDARY** later |
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

| Implementation | Class | Action |
|---|---|---|
| tk `semblon home` | **CANONICAL** | Sole product shell |
| `semblon review-ui` | **SECONDARY** · **KEEP** | Do not make a second Home |
| Optional Qt `semblon shell` | **KEEP (optional)** | Application API client (`native_shell/`); **not** product Home; **not** a mapped blocker |
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
