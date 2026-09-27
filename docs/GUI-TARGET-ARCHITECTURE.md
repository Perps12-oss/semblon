# Target GUI architecture

**Date:** 2026-09-27  
**Status:** proposal. Not implemented. Does not replace `docs/SEM-ARCH-V1.4.md` and does not open a new identity or schema queue.

---

## Executive summary

### Can Semblon gain a major new user-facing capability without modifying the fundamental shell?

**Not in the code that ships today.** After the migration proposed here, **yes**, for a capability that is a page, a command, or a contextual action.

Evidence that the current shell must be edited:

- Routes are a static tuple inside the widget module (`semblon/home_ui.py:199-204`) plus an `if` chain that names every route (`home_ui.py:3319-3375`).
- Overflow, shortcuts, and the Ctrl+K list are separate hard-coded copies (`home_ui.py:1008-1015`, `973-979`, `3053-3057`).
- Inspector actions are widgets constructed in `HomeApp.__init__` (`home_ui.py:1278-1310`).
- Lens and Activity are methods of `HomeApp` (`home_ui.py:1502`, `1721`).
- There is no feature registry. `product_exposure.GUI_PATHS` is a classification table (`product_exposure.py:25`). `runtime_contract.CapabilitySpec` is a model catalog (`runtime_contract.py:119`), not a page list.

A new sidebar destination, a new inspector verb, or a new Lens action is a change to `HomeApp`. That is the fundamental shell.

The proposed shape keeps one window and moves features into modules the shell only knows as records: navigation contribution, page factory, commands, availability. The first line of registration is the only shell edit. Scenarios A–E in the acceptance section below are written against that shape. They are not true of `main` at `142e36f`.

### What can Semblon already do that a normal user cannot discover?

The full table is `docs/GUI-CAPABILITY-EXPOSURE-MATRIX.md`. The highest-value gaps:

| Already implemented | How a new user would have to know |
|---|---|
| The photo grid | Sidebar **Photos** opens the library dashboard (route `home`). The grid is route `photos`, reached by a “Browse photos” button or More. `_show_library_home` would show a grid and is never called (`home_ui.py:2644`, `tests/test_home_ui.py:274`). |
| Compare every face in a group, and write a note | More → Open Review (`home_ui.py:1008`, `review_ui.py:1088`). The inspector tells you only after you select a cluster (`home_ui.py:1812-1822`). |
| One person’s history (when / where) | `semblon memory history`. Activity shows aggregate “People together” and “Moments” only (`activity_surface.py:25-27`, `memory.py:323`). |
| “Is this face someone I already named?” | `semblon identify`. The GUI never calls it. Naming is manual. That is safe; the capability is still invisible. |
| Search text that appears in a photo | The top search box tries it only after person search misses (`home_ui.py:3986-4004`), with no label that text search happened. |
| Ask the Lens catalog about a **region** | `lens.query_image` exists (`lens.py:589`). The product mouse-up persists the box and runs a color-histogram similar search (`lens_home.py:32-56`, `region_search.py:43-44`). “Ask about this photo” queries the **whole** frame (`home_ui.py:1572-1635`). |
| Name a saved region | `Application.name_region` (`application.py:229`). No control. |
| Keep a folder updated | `semblon watch` (`watch.py`). No GUI. |
| Export a folder per person without moving originals | `semblon export --views` (`export.py:640`). GUI export is the HTML page under Settings → Advanced. |
| A readable report file | `semblon report`. No GUI. `report` must not write the store. |
| Backup the library | `semblon lab backup`. No GUI. |
| Four inbox outcomes (known, unknown, needs review, rejected) | `semblon inbox`. The GUI shows unnamed groups. |
| Optional OCR / CLIP / pose during ingest | Automatic when probes succeed (`observers.resolve_product_observers`). No Settings row. |
| Ctrl+K | Works, and is listed under Settings → Advanced (`product_surface.py:50-58`). It only jumps to destinations (`home_ui.py:3035-3071`). |

Lab tools (eval, observatory, model install, screen capture, ANN rebuild) are implemented and should stay hidden.

---

## Architecture options

Three options that fit this repository. No numeric score.

### Option 1 — Explicit internal feature registry

Each product area is a Python object in a tuple `PRODUCT_FEATURES`. The shell loops the tuple to build the sidebar, the palette’s “Go to” group, and settings sections. Pages are factories. Commands are a field on the same object.

| | |
|---|---|
| Complexity | Low. One dataclass, one tuple, one loop. Matches `HOME_NAV` and `GUI_PATHS`, which are already tuples. |
| Runtime cost | Import the tuple at startup. No scan, no entry points. |
| Development cost | Move code out of `HomeApp` into modules. The first feature is the expensive one; later features are a module plus a line. |
| Testability | `when` and `enabled` are pure and can be tested like `inspector_verb_states` (already tested without a full window). |
| Discoverability | Sidebar from nav contributions. Palette from command titles. |
| Extensibility | New in-repo feature: yes. Third-party install: no. |
| Failure isolation | Shell catches `page()` errors per feature. A bad feature does not remove other nav items if the tuple still loads. Import errors still fail startup, which is acceptable for in-repo code. |
| Python | Natural. Dataclasses, no framework. |
| PySide6 | The same tuple can drive `native_shell` labels later. Widgets stay in each client. |
| Future WinUI / native | The tuple is language-neutral if `page()` stays behind the client. A C++ client would re-read a generated list or call the same Application API. Do not design that client now. |
| Migration | Incremental. Sidebar can be generated while `_navigate` still has branches. |
| Risks | A “feature” object that imports `HomeApp` recreates the coupling. The host protocol has to stay small. |

### Option 2 — User-installable plugins

Setuptools entry points or a plugins directory, loaded beside Semblon.

| | |
|---|---|
| Complexity | High. Discovery, enablement, bad-plugin crashes, identity firewall. |
| Runtime cost | Import arbitrary modules at startup. |
| Development cost | A host, a compatibility story, and tests for hostile or missing plugins. |
| Testability | Need a fake plugin and a broken plugin. |
| Discoverability | Same as option 1 if the host is the same, plus a plugins screen. |
| Extensibility | Highest, and unneeded. |
| Failure isolation | Better only with a process boundary. In-process plugins can write the SQLite store. |
| Python | Entry points work. They are the wrong tool. |
| PySide6 / WinUI | A plugin that builds Tk widgets cannot run in a Qt or WinUI shell. |
| Migration | Harder than option 1, and it blocks the actual goal on a distribution system. |
| Risks | A plugin that embeds faces or writes `person_id`. Local photo libraries should not load unsigned code. |

**Not recommended.** Section “Not a plugin system” in `docs/GUI-EXTENSIBILITY-RESEARCH.md`.

### Option 3 — Route, command, and context registries plus a service object

Separate registries: routes, commands, context menus, settings. Services passed in. This is option 1 split into several lists, with `Application` as the only service object.

| | |
|---|---|
| Complexity | Medium. More types, easier to avoid a god `Feature` class. |
| Runtime cost | Same as option 1. |
| Development cost | Slightly more boilerplate per feature (register in three lists). |
| Testability | Excellent. Commands tested without pages. |
| Discoverability | Same, if one host queries all three lists. |
| Extensibility | Same as option 1 for in-repo work. |
| Failure isolation | A command can fail without a page failing. |
| Python | Fine. |
| PySide6 | Commands are widget-free, so the Qt shell can bind them without copying enablement. This is the main advantage over stuffing Tk factories into the only registry. |
| Future native | Commands and availability are the portable part. Pages are not. |
| Migration | Fits the code: `inspector_verb_states` is already a command policy with no widgets. |
| Risks | Three registries drift (a command with no feature, a page with no commands). A single `Feature` that *contains* commands and an optional page avoids drift. |

### Direction

Use **option 1’s single feature object**, and put **option 3’s commands and availability inside it**. Pass **`Application`** (extended only when a real caller needs a method) as the service object. Do not build option 2.

`page()` for Tk can live in the feature module that already imports Tk. A future client ignores `page()` and uses command ids plus `Application`. That is how `native_shell` should eventually catch up, without becoming a second product Home in this slice.

---

## Proposed structure

```text
                    ┌──────────────────────────────────────────┐
                    │ Home shell (Tk today)                    │
                    │                                          │
                    │ Window, theme, condensed rail            │
                    │ Nav host ← feature.nav                   │
                    │ Workspace slot ← feature.page            │
                    │ Inspector slot ← commands for selection  │
                    │ Search field (library query)             │
                    │ Command palette host (Ctrl+K)            │
                    │ Job chrome: folder, pause, cancel        │
                    │ Status line (not a messagebox)           │
                    │ Settings host ← feature.settings         │
                    └────────────────────┬─────────────────────┘
                                         │
                              PRODUCT_FEATURES tuple
                                         │
        ┌──────────────┬──────────────┬──┴───────────┬──────────────┐
        │ Library      │ People       │ Lens         │ Activity     │
        │ photos/videos│ people/      │ one route    │ one route    │
        │ grid pages   │ unknown      │              │              │
        └──────┬───────┴──────┬───────┴──────┬───────┴──────┬───────┘
               │              │              │              │
            commands       commands       commands      commands
         (open, browse)  (name, note,   (ask photo,   (open person
                          assign, …)     find similar)  history)
               │              │              │              │
               └──────────────┴──────┬───────┴──────────────┘
                                     │
                             Host.session()
                                     │
                              Application
                         (extend; Home uses it)
                                     │
                    JobEngine   review.py   search   memory
                    canvas      lens        region_search
                    observers   identify    export   watch
                                     │
                              SQLite store
                         FaceKit remains the only
                         identity engine
```

### Shell owns

- The Tk root, tokens, theme, minimum size, condensed layout.
- Hosts: nav, workspace, inspector, palette, settings, job progress, status.
- Mapping a route id to “call that feature’s `page`”.
- Building buttons from command records. It does not contain `if command_id == "review.name"`.
- Job lifecycle and close-while-busy.
- The search **field**. The search **behavior** is the library feature’s command.

### Feature owns

- Copy, empty state, page layout, command `when` / `enabled` / `run`.
- Calls into `Application` or existing modules (`review.py`, `memory.py`, `lens.py`).
- No `faces.person_id` writes except through `review.py`, same as today.

### Selection context

A small frozen object, built by the shell from canvas and lists:

```text
Selection
  route_id
  media_id | None
  items: list of {kind, ids...}     # kinds already used: cluster, face, person, region, track
  hover: one item | None
  job: idle | running | paused | cancelling
```

`kind` values already appear in inspector items and canvas hits. New kinds are a feature concern, not a shell `if` chain, as long as commands declare `when` against `kind`.

### Lens, specifically

Three commands, because the code has three behaviors (forensic audit):

| Command | Calls | Identity |
|---|---|---|
| `canvas.inspect_hits` | `region_hits` on stored boxes | Read-only |
| `lens.find_similar` | `remember_and_find` (color histogram) | Refuses `modality == "face"` (`region_search.py:58-59`) |
| `lens.ask` | `query_image` on the whole frame or the current rectangle | Writes observation items only through `persist_successes` paths that are not face identity (`lens.py` docstring) |

The shell paints the current command’s result in the inspector. It does not know about SigLIP or SAM2. Availability comes from `status_report()` / `CapabilitySpec`, which the Lens feature reads.

### Global destinations versus commands

| Global (nav contribution) | Command-only (no nav) |
|---|---|
| Photos, Videos, People, People to name, Recent activity, Lens | Note, history, find similar, ask selection, export views, compare faces, watch folder |
| Settings (shell footer, not a library section) | Diagnostics, export HTML (settings contributions) |

Search stays a field. It may also be a palette action that focuses the field.

### Data path (unchanged)

```text
Media → observation → (face embed | other observation) → cluster
      → human decision in review.py → person → name
```

Hypothesis stays a suggestion (`identify`) until a decision is written. The GUI must not call `identify_*` and then stamp `person_id` itself.

Tracks stay “not a person” (`tracks.py` CLI help, Review track actions).

---

## Acceptance scenarios

These are the bar for a later implementation slice. They are not met on `main`.

### Scenario A — new page

A developer adds `semblon/features/example.py` with a nav contribution and a `page()` and appends it to `PRODUCT_FEATURES`.

The sidebar shows it. They do not edit `_navigate`, `HOME_NAV`, the More menu, or Ctrl+1…5 by hand. Shortcuts and the palette “Go to” group are generated from the same contribution.

Allowed shell edit: the one-line append, if registration is not import-time inside the feature package. Prefer the feature package’s `__init__` tuple so `home_ui.py` does not gain a line per feature.

### Scenario B — contextual action

A developer adds a `Command` on an existing feature (`surfaces={"inspector","context","palette"}`, `when` checks selection kind).

The inspector, the context menu, and Ctrl+K show it when `when` is true. No edits to those three widgets beyond the generic “render these commands” loop, which exists once.

### Scenario C — hidden capability

`memory.history` is registered as a command on People. No new table, no change to clustering, no sidebar item. The user selects a person and sees “Show history”, implemented by the existing function (`memory.py:323`).

### Scenario D — future Lens capability

“Search everything related to this hovered region” is a new command on the Lens feature whose `when` is “hover or selection is a region”. `run` calls whatever engine function exists at that time. `HomeApp._navigate` and `HOME_NAV` do not gain a branch. If the provider is missing, `enabled` returns the catalog reason (`home_shell._state_label`).

### Scenario E — feature unavailable

`enabled` is false and carries a reason. The control is disabled or replaced by the honest line. It does not call the provider, does not show an empty success, and does not traceback. This matches `StructuredResult` rules (`runtime_contract.assert_honest`) and Lens copy (`lens_release.py:45-49`).

---

## What this proposal refuses

- A second product Home.
- Electron, Tauri, FastAPI, CustomTkinter, a permanent Tk AppShell.
- One sidebar item per model or observer.
- Plugins.
- New schema columns. Commands call existing functions.
- Retuning `eps`, `min_samples`, or identify thresholds.
- Moving FaceKit or DBSCAN into widgets.
- Treating `review.html` as the product UI.
- Auto-assigning a person from a suggestion or a Lens description.
