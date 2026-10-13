# GUI architecture forensic audit

**Superseded 2026-10-05 by the completed PySide6 production migration.**

**Historical audit.** Anatomy below is the tree as examined on 2026-09-27 / 2026-09-28. It is not the current architecture.

**Current architecture (2026-10-05):**

```
PySide6 shell → Application → ArchiveSession / JobEngine / Lens → domain / storage → providers
```

`lens_home.py` and the widget `native_shell/window.py` are deleted. `review.html` and `review_chrome/` are retired. Production UI is `semblon shell`. Tk Home remains a legacy client. Do not read the tables below as a description of the live product shell.

**Date of the audit:** 2026-09-27. **Retest:** 2026-09-28.  
**Source of the anatomy below:** `main` at `142e36f`, then rechecked on `origin/main` `646d44b` and `origin/cursor/gui-feature-registry-c466` `1c40dd0` (PR #112, not merged).  
**Method:** production launch path and Python sources, then a fetch of every remote branch.  
**Scope:** research. This file does not authorize a GUI rewrite, a second product shell, schema changes, or identity-threshold changes.

### Retest delta

`main` since `142e36f` (PR #109) adds open-vocabulary hover on the photo canvas. It does not add a feature registry.

- `CanvasWorkspace` keeps a `VisualSegment` under the pointer (`canvas.py` `_hover_seg`) and schedules `JobEngine.submit_visual_analyze`.
- Masks live in `visual_cache` sidecars, not new SQLite columns (`docs/VISUAL-UNDERSTANDING.md`).
- Home’s only edit is passing `job_engine=self.engine` into `CanvasWorkspace`.
- `tests/test_visual_understanding.py` on `646d44b`: **10 passed** (this environment, 2026-09-28).

PR #112 (`cursor/gui-feature-registry-c466`) is the registry this audit said did not exist. It is not on `main`. `tests/test_gui_registry.py` on `1c40dd0`: **12 passed**. Details and the corrected shell answer are in `docs/GUI-TARGET-ARCHITECTURE.md` (Retest). The anatomy in the rest of this file describes `main`, not #112.

This audit did not launch the Windows Tk process and did not re-run pytest. Claims below are source evidence (`path:line`). Windows live status for ingest remains the owner record in `docs/COMPLETION-MATRIX.md`; that record was not re-executed here.

Document set:

- `docs/GUI-ARCHITECTURE-FORENSIC-AUDIT.md` — this file
- `docs/GUI-CAPABILITY-EXPOSURE-MATRIX.md` — engine vs CLI vs GUI
- `docs/GUI-EXTENSIBILITY-RESEARCH.md` — patterns and UX principles
- `docs/GUI-TARGET-ARCHITECTURE.md` — proposal and executive answer
- `docs/GUI-MIGRATION-PLAN.md` — incremental steps

`docs/UI-EXPOSURE-MAP.md` matches the current `HOME_NAV` labels. This audit adds seams that map does not: the Photos-versus-grid split, the two region behaviors, the destination-only command palette, and the unused library-home method.

---

## Production launch path

Interactive double-click and the CLI door are the same GUI.

| Step | Evidence |
|---|---|
| Double-click script | `tools/semblon-interactive.ps1:117` runs `python -m semblon home` |
| Module entry | `semblon/__main__.py:5-8` calls `semblon.cli.main` |
| Console script | `pyproject.toml:19` `semblon = "semblon.cli:main"` |
| Subcommand | `semblon/cli.py:449-458` parser `home`; dispatch `semblon/cli.py:1126-1129` |
| Product launcher | `semblon/lens_home.py:102-107` `run_product_home` installs the Lens mouse-up handler, then `run_home_ui` |
| Window | `semblon/home_ui.py:4338-4339` `HomeApp(store).run()` → `Tk.mainloop` (`home_ui.py:4334-4335`) |

`semblon shell` (`cli.py:460-470`, `cli.py:1131-1134`) opens the optional PySide6 client `semblon/native_shell/run.py:8-29`. It is not the product Home. `semblon review-ui` and `semblon canvas` are separate process doors (`cli.py:433-447`, `cli.py:522-527`).

Default store path is `process.default_store_path` (`home_ui.py:874`), documented on the CLI as `%LOCALAPPDATA%\Semblon\store.sqlite` (`cli.py:453-457`).

---

## A. GUI anatomy map

There is one production process. There is no router object, no page factory, and no feature registry. `HomeApp` constructs the window, the chrome, every workspace, and the inspector, then switches visibility with `_navigate`.

```text
python -m semblon home
  └─ lens_home.run_product_home
       ├─ lens_home.install(HomeApp)     # replaces HomeApp._open_region_select
       └─ HomeApp
            ├─ Tk root "Semblon"          home_ui.py:900-907
            ├─ JobEngine(store)           home_ui.py:875   (not Application)
            ├─ Watchdog                   home_ui.py:877
            ├─ theme from ui_prefs        home_ui.py:898, 2967+
            │
            ├─ Shell frame                home_ui.py:918-921
            │    ├─ Top brand + Lens button + search + Settings
            │    ├─ Job strip + More menu
            │    ├─ Progress / Pause / Cancel
            │    ├─ Sidebar from HOME_NAV
            │    ├─ Workspace slot
            │    └─ Inspector column
            │
            ├─ Workspaces (all built up front, shown one at a time)
            │    ├─ route home     → landing / processing / result card
            │    ├─ route photos   → CanvasWorkspace source_types=folder
            │    ├─ route videos   → CanvasWorkspace source_types=video
            │    ├─ route canvas   → CanvasWorkspace all types
            │    ├─ route lens     → Lens pane + region stage
            │    ├─ route people   → welcome title + inspector list
            │    ├─ route unknown  → welcome title + inspector list
            │    └─ route activity → activity pane
            │
            └─ Data
                 JobEngine → process_folder          jobs.py:125
                 reads: search, inbox, load_board, activity_memory, canvas.load_canvas
                 writes: review_ui.apply_* via inspector_verbs
                 Lens region: lens_release.remember_selection → region_search
                 Lens whole photo: selection.run_lens_query → lens.query_image
```

### Route table (production Tk)

`HOME_NAV` is the only nav table (`home_ui.py:199-204`):

| Section | Route id | Sidebar label | What `_navigate` actually shows |
|---|---|---|---|
| ASK | `lens` | Lens | `_open_lens` → Lens workspace (`home_ui.py:3353-3356`, `1495-1500`) |
| LIBRARY | `home` | Photos | `_show_home_landing` (`home_ui.py:3323-3327`, `2554-2603`) |
| LIBRARY | `videos` | Videos | Canvas grid, `source_types=("video",)` (`home_ui.py:3345-3351`) |
| PEOPLE | `people` | People | Welcome + `search_people` list in the inspector (`home_ui.py:3357-3362`, `3733-3792`) |
| PEOPLE | `unknown` | People to name | Welcome + unnamed clusters from inbox/board (`home_ui.py:3364-3369`, `3806-3875`) |
| ACTIVITY | `activity` | Recent activity | Activity workspace (`home_ui.py:3371-3374`, `3883-3921`) |

Routes that exist and are **not** in `HOME_NAV`:

| Route id | Entry | Workspace |
|---|---|---|
| `photos` | Landing CTA “Browse photos” (`home_ui.py:2177-2182`); More menu (`home_ui.py:1010-1012`) | Canvas stills (`home_ui.py:3334-3343`) |
| `canvas` | More → “Explore workspace” (`home_ui.py:1013-1014`) | Canvas, no source filter (`home_ui.py:3328-3332`) |
| settings | Settings button; Ctrl+K item | `Toplevel` (`home_ui.py:4007-4224`) |

`_show_library_home` used to pack the photo grid under a review strip. The 2026-10-11 audit fix deleted that method. Do not restore it.

Populated “Photos” therefore shows the library shell (headline, stat tiles, Available / Optional capability rows, last Lens result) plus CTAs. The photo grid is a second route. Inspector copy on that shell says “Browse Photos when you want the grid” (`home_ui.py:2597-2599`) while the sidebar item is already labeled Photos.

### Window chrome

| Region | Built in | Notes |
|---|---|---|
| Brand row | `home_ui.py:923-941` | “Semblon”, subtitle, Lens button, “to name” counter |
| Search row | `home_ui.py:943-979` | Entry, Search button, Ctrl+F, Ctrl+K, Ctrl+1…5 |
| Job / More | `home_ui.py:981-1016` | Folder, hidden Review button, More menu |
| Progress | `home_ui.py:1023-1061` | Status, clock, bar, Pause, Cancel |
| Sidebar | `home_ui.py:1080-1156` | Loop over `HOME_NAV` |
| Narrow rail | `home_ui.py:3181-3219` | Same items, horizontal, below width 1100 (`home_ui.py:206-212`) |
| Status bar | `home_ui.py:1063-1073` | Library status string |
| Inspector | `home_ui.py:1201-1322` | Selection list, detail list, six verbs + two Lens buttons |

`_sync_chrome_for_route` (`home_ui.py:3232-3284`) packs or hides the job strip and progress bar from the current route and job state. On route `home` the job strip is hidden except after a completed job, when Open Review is packed (`home_ui.py:3248-3254`).

### Dialogs, overlays, viewers

| Surface | Kind | Entry |
|---|---|---|
| Settings | `Toplevel` | `_show_settings` `home_ui.py:4007` |
| Go to (Ctrl+K) | `Toplevel` + `Listbox` | `_open_command_palette` `home_ui.py:3035` |
| Review | `Toplevel` on the Home root, no nested mainloop | `_open_review_ui` `home_ui.py:3680-3697`; host prefers WebView chrome (`review_ui.py:2020-2062`) |
| Live | `simpledialog` prompts, then a worker thread | `_open_live_overlay` `home_ui.py:4256-4313` |
| Diagnostics | `Toplevel` from `advanced_diagnostics.open_advanced_diagnostics` | `home_ui.py:4248-4254` |
| Failure | `messagebox` / `show_failure_dialog` | `_show_failure` `home_ui.py:3674`; verb errors `home_ui.py:1891-2044` |
| review.html | OS browser | `_open_html` `home_ui.py:3716-3727`, button only under Settings → Advanced |
| Region select off the Lens route | `Toplevel` “Lens — select a region” | `selection.open_region_window` `selection.py:388-425` |
| Region select on the Lens route | Embedded canvas in `_lens_stage` | `lens_home.py:70-85` |
| Photo / video viewer | `CanvasWorkspace` inside the workspace slot | `canvas.py:378-517` |
| Qt shell | Separate `QMainWindow` | `native_shell/window.py:58-107` |

No right-click menu exists. The only `tk.Menu` is the More menubutton (`home_ui.py:1005-1016`). Canvas uses hover, click, and drag (`canvas.py:505-510`), not a context menu.

### Optional Qt shell (not product Home)

```text
semblon shell
  └─ Application(store)          application.py:116-120
       ├─ own JobEngine
       └─ _install_lens_home()   patches HomeApp even though this window is Qt
  └─ ShellWindow
       ├─ job bar: Choose folder, Pause, Resume, Cancel
       ├─ nav list: Home, Photos, Videos, People, Unknown, Activity
       │    native_shell/window.py:134-136
       ├─ workspace: one QListWidget
       └─ inspector verbs: Merge, Name, Split, Ignore, Rule out
            native_shell/window.py:162-171
```

That nav list is a second hard-coded table. It has no Lens, Search, or Settings. Activity copy includes engineering counts (`native_shell/window.py:311-319`). Unknown rows print `face_id` (`native_shell/window.py:307-309`).

### State, events, jobs

| Mechanism | Where | Role |
|---|---|---|
| `HomeApp` fields | `home_ui.py:871-897`, `1315-1322` | Route, job, inspector selection, theme, last Lens result |
| `queue.Queue` + `root.after(100, _drain_queue)` | `home_ui.py:883`, `1325`, `3538` | Worker thread → Tk thread for progress |
| `JobEngine` | `jobs.py:54-136` | One ingest at a time; pause/cancel between files; calls `process_folder` |
| `Watchdog` | `home_ui.py:877` | Stall detection (120s); not a feature bus |
| Canvas `on_select` | `home_ui.py:1197`, `canvas.py:614-625` | Media / face / region hits → `_on_canvas_select` |
| Inspector verb policy | `inspector_verbs.py:77-200` | Enablement dict; widgets still live on `HomeApp` |
| `gates.enabled` | `gates.py:73-79` | Env opt-out for ruled-out, live, modality product |
| `runtime_contract` catalog | `runtime_contract.py:119-240` | Backend capability honesty, not UI routes |
| `product_exposure.GUI_PATHS` | `product_exposure.py:25-180` | Static classification tuples; nothing imports them to build widgets |

`Application` (`application.py:116-258`) is the language-neutral façade (board, inbox, people, canvas, jobs, region persist). Production `HomeApp` constructs its **own** `JobEngine` (`home_ui.py:875`) and calls `search`, `inbox`, `load_board`, and `review_ui` directly. The façade is what the Qt shell uses. Two clients, two engines, no shared UI session.

There is no message bus. Feature code reaches the shell by being methods on `HomeApp`, or by the one monkeypatch in `lens_home.install` (`lens_home.py:97-99`).

---

## B. Shell coupling audit

Classification:

- **Shell** — window, navigation host, job chrome, theme, close/cancel. Belongs on the shell even after a registry.
- **Accidental** — the shell names a feature it does not need to understand.
- **Feature** — behavior that can live in a feature module and be discovered.
- **Debt** — two implementations, a dead path, or a comment that no longer matches the code.

| Coupling | Evidence | Class |
|---|---|---|
| `HOME_NAV` tuple of route ids and labels | `home_ui.py:199-204` | Accidental. A data table is the right shape; it lives inside the widget module and is not the only nav list. |
| Sidebar built by iterating `HOME_NAV` | `home_ui.py:1122-1150` | Shell host. The loop is already generic. The data is not. |
| Section titles hard-coded beside the tuple | `home_ui.py:1116-1121` | Accidental. ASK is blanked so Lens has no section title. |
| `_navigate` if-chain names every route | `home_ui.py:3319-3375` | Accidental. This is the router. A new page requires a new branch. |
| Route `photos` and `canvas` omitted from the sidebar | `home_ui.py:199-204` vs `3334`, `3328` | Feature placement that the shell special-cases. Photos-the-label and photos-the-grid are different ids. |
| `_show_library_home` unused | Deleted in the 2026-10-11 audit fix. The old definition was `home_ui.py:2644`. | Debt, now removed. Do not restore the photos-plus-review-strip layout. |
| More menu items | `home_ui.py:1008-1015` Open Review, Live, Browse photos, Explore | Accidental. Overflow is a shell slot; the four commands are features. |
| Lens button in the brand row | `home_ui.py:927` | Accidental duplicate of the sidebar Lens item. |
| Search calls `_search_person` only | `home_ui.py:969-972`, `3928-4005` | Feature. People search, then OCR text fallback, is a feature pipeline inside the shell. |
| Ctrl+1…5 bound to fixed route ids | `home_ui.py:975-979` | Accidental. Shortcuts are not derived from `HOME_NAV` order (Lens is first in the tuple and has no Ctrl key). |
| Ctrl+K palette copies `HOME_NAV` + Settings | `home_ui.py:3035-3071` | Accidental. It is a destination jumper. It does not list actions. It does not filter as the user types. |
| Settings sections written inline | `home_ui.py:4077-4218` Library, Processing/GPU, Appearance, About, Advanced shortcuts, export HTML, Diagnostics | Shell may own Appearance and About. Library path, GPU, export, and diagnostics are features pasted into one method. |
| Inspector verb buttons constructed in `HomeApp.__init__` | `home_ui.py:1278-1310` | Feature widgets. Policy is already separate (`inspector_verbs.py:77`). The six buttons and their handlers (`home_ui.py:1891-2047`) are not. |
| “Select a region” and “Ask with Lens” always packed in the inspector | `home_ui.py:1303-1310` | Accidental. They are Lens commands shown on every route. |
| Lens workspace methods on `HomeApp` | `_build_lens_workspace` `home_ui.py:1502`, `_lens_ask_whole` `1572`, `_refresh_lens_workspace` `1637` | Feature. |
| Activity workspace methods on `HomeApp` | `home_ui.py:1721-1805`, `3883-3921` | Feature. Formatting already lives in `activity_surface.py`. |
| People and Unknown render into the inspector list | `home_ui.py:3733-3875` | Feature. The workspace pane is only a title (`_welcome`). |
| Live prompts and thread inside `HomeApp` | `home_ui.py:4256-4313` | Feature, plus a gate check that surfaces an env-var sentence (`gates.py:41-43`). |
| Review Toplevel launched from Home | `home_ui.py:3680-3697` | Feature. Sharing the Tk root is a shell responsibility; building Review is not. |
| Job control map lists feature buttons | `HOME_CONTROLS_ALWAYS_ON` `home_ui.py:216-224`; button dict `home_ui.py:3402-3411` | Shell for pause/cancel/folder. Accidental for people/unknown/activity/live/search keys. |
| Chrome packing branches on route id | `home_ui.py:3246-3263` (`home`, `photos`, `videos`, `lens`) | Accidental conditionals. |
| Capability honesty cards drawn on the landing | `home_ui.py:2320-2356` via `home_shell.capability_sections` | Feature content hosted by the Photos landing. The shell should host a slot; it currently knows the two columns. |
| `lens_home.install` monkeypatch | `lens_home.py:97-99`; called from product launch `lens_home.py:106` and from `Application.__init__` `application.py:108-120` | Debt. The production region behavior is not the method written on `HomeApp` (`home_ui.py:1405`). |
| `Application` unused by `HomeApp` | `HomeApp` builds `JobEngine` itself `home_ui.py:875` | Debt. The façade exists for a future client and for Qt; the shipping UI does not go through it. |
| Second nav list in Qt | `native_shell/window.py:134-136` | Debt. Divergent labels (Home, Unknown) and no Lens. |
| `GUI_PATHS` registry | `product_exposure.py:25-180` | Not wired to widgets. Classification only. |
| `format_activity_lines` advanced schema dump | `home_ui.py:491-549` | Debt as a UI path. Activity route uses `activity_surface` (`home_ui.py:3883`). The advanced formatter is test-only (`tests/test_home_ui.py`, `tests/test_empty_states.py`). |
| Aliases `btn_people = btn_canvas` then rebound | `home_ui.py:1019-1021`, `1153-1156` | Debt. Control-state map depends on sidebar buttons existing. |

### What is already a seam (reusable without a new framework)

| Piece | Why it matters |
|---|---|
| `HOME_NAV` as data | Sidebar construction is already a loop (`home_ui.py:1122-1150`). |
| `inspector_verb_states` | Enablement and reasons are pure (`inspector_verbs.py:77-200`). Widgets call it (`home_ui.py:1825-1832`). |
| `Application` | Read/write names a non-Tk client can call (`application.py:44-75`, `116-258`). |
| `JobEngine` | One job door (`jobs.py:54-125`). UI must not own `process_folder`. |
| `empty_states` | Empty copy is not inline strings scattered only in widgets. |
| `product_surface` verb labels | `VERB_LABEL_*` `product_surface.py:16-21`. |
| `runtime_contract.CapabilitySpec` | Availability vocabulary: AVAILABLE / MISSING / DISABLED / fallback (`runtime_contract.py:119-240`). This is a **backend** catalog, not a page registry. |
| `CanvasWorkspace` | Embeddable viewer with hover, click, drag (`canvas.py:378-388`). It does not write the store. |
| `activity_surface.load_activity_memory` | Read model separated from the Tk builder. |
| `product_exposure.GUI_PATHS` | Human classification. Safe to keep as policy; wrong thing to pretend is a plugin host. |

### Necessary shell responsibilities (keep)

- One window, title, minimum size, theme, condensed rail (`home_ui.py:900-907`, `3181-3219`).
- A navigation host that can show and highlight a route.
- A single workspace slot and a single inspector slot.
- Ingest job chrome: folder, pause, resume, cancel, progress (`jobs.py` contract: between-file pause).
- Close-while-busy confirmation (`home_ui.py:4323-4331`).
- Thread → UI queue drain.
- A command-palette **host** and a settings **host**.

### Two region behaviors (do not collapse them)

Production mouse-up on a Lens box does **not** run the capability catalog.

1. **Canvas drag** hit-tests observations already stored on the board (`canvas.py:1016-1057`, `product_surface.region_hits`). Read-only. No new embedding.
2. **Lens “Select a region”** persists the user rectangle and searches similar appearance (`lens_home.py:32-56` → `lens_release.remember_selection` → `region_search.remember_and_find`). `appearance_vector` is a color histogram (`region_search.py:43-44`). Face modality is refused (`region_search.py:58-59`).
3. **“Ask about this photo”** calls `selection.run_lens_query` → `lens.query_image` with no crop (`home_ui.py:1572-1635`, `selection.py:219`). That walks `LENS_CAPABILITIES` (`lens.py:25-36`).

`mount_region_select` only calls `run_lens_query` when `on_rect` is absent (`selection.py:351-380`). Product install always passes `on_rect` (`lens_home.py:81`). So the shipping region gesture is path 2, not path 3.

---

## Event and callback map

```text
User
  ├─ sidebar button ──► HomeApp._navigate(nav_id)
  ├─ search Return ──► HomeApp._search_person
  ├─ Ctrl+K ──► palette ──► _navigate or _show_settings
  ├─ inspector button ──► _inspector_* ──► inspector_verbs ──► review_ui.apply_* ──► review.py
  ├─ canvas hover/click/drag ──► on_select ──► _on_canvas_select ──► inspector
  ├─ Lens mouse-up ──► on_rect ──► remember_selection ──► inspector lines
  └─ Choose folder ──► JobEngine.submit_ingest
                         worker thread
                           on_event ──► queue ──► _drain_queue ──► progress widgets
                           on_done  ──► queue ──► completion card
```

Identity writes stay in `review.py` (`name_cluster`, `name_face`, `merge_clusters`, `split_cluster`, `ignore_subject`, `note_subject`, `rule_out_subject`). The GUI does not call FaceKit. That split should survive any registry: commands invoke the façade, widgets do not embed compare logic.

---

## Bottom line of the audit

The production shell is one class, `HomeApp`, in `semblon/home_ui.py`. Navigation looks data-driven because `HOME_NAV` is a tuple, and the sidebar is a loop. Routing, overflow, shortcuts, settings, inspector actions, Lens, and Activity are still methods and branches on that class. A new user-facing capability today is a edit to `HomeApp`.

The optional Qt window repeats a smaller, older slice of the same coupling and is not a second product Home.
