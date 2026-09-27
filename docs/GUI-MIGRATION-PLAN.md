# GUI migration plan

**Date:** 2026-09-27  
**Constraint:** the Tk Home that `semblon home` opens stays usable after every step. No visual redesign is required for steps 1–3. No framework change. No plugin host. No schema change. No identity-threshold change.

Architecture this plan implements, when a later slice chooses to: `docs/GUI-TARGET-ARCHITECTURE.md`.  
Evidence for the current seams: `docs/GUI-ARCHITECTURE-FORENSIC-AUDIT.md`.  
Evidence for what to expose: `docs/GUI-CAPABILITY-EXPOSURE-MATRIX.md`.

Each step is a slice of its own. Do not do them in one change.

---

## Step 1 — Registry beside the shell, same pixels

Introduce a feature record and a `PRODUCT_FEATURES` tuple that **describes** today’s routes. `HomeApp._navigate` still runs. The sidebar is still built from `HOME_NAV` until step 3, **or** the sidebar is built from the tuple while the tuple is a literal copy of `HOME_NAV`.

Do not change labels, order, or which route `home` opens.

Records to seed, matching `home_ui.py:199-204` and the extra routes:

| id | Nav label | Route id | In the sidebar today? |
|---|---|---|---|
| `lens` | Lens | `lens` | Yes |
| `library` | Photos | `home` | Yes |
| `videos` | Videos | `videos` | Yes |
| `people` | People | `people` | Yes |
| `unknown` | People to name | `unknown` | Yes |
| `activity` | Recent activity | `activity` | Yes |
| `photos` | (no nav) | `photos` | No — command “Browse photos” |
| `explore` | (no nav) | `canvas` | No — More → Explore workspace |
| `review` | (no nav) | — | More → Open Review |
| `settings` | (no nav) | — | Settings button |

Also move the existing command **descriptions** (not the Tk construction) for the six inspector verbs into command records whose `enabled` calls `inspector_verb_states` (`inspector_verbs.py:77`). The buttons can still be the same widgets, reading `enabled` from the record, so behavior tests keep passing.

Palette “Go to” should read nav contributions. If it still looks like today’s list (`home_ui.py:3053-3057`), this step is done. Do not add action rows yet.

Tests: a pure test that the tuple’s nav labels and route ids equal today’s `HOME_NAV`, plus the known non-nav routes. No screenshot requirement.

**Leave in place:** `_show_library_home` (`home_ui.py:2644`). It is unused. Do not wire it in this step. Note the stale docstring on `landing_cta_plan` (`home_ui.py:300-304`) and correct the comment when touching that function, so the next reader does not “restore” a dead layout by accident.

**Out of step 1:** renaming sidebar Photos, Qt shell, context menus.

---

## Step 2 — First modular feature: Activity

Activity is the smallest page that is already a module.

- Read model: `activity_surface.load_activity_memory` and `activity_workspace_sections` (`activity_surface.py:258`, `401`).
- Tk builder today: `HomeApp._build_activity_workspace` / `_show_activity` (`home_ui.py:1721`, `3883`).

Move the Tk builder into the Activity feature’s `page(host)`. `host` supplies the parent frame, `set_inspector`, and `navigate`. The feature calls `activity_memory` (already on `Application`, `application.py:186-187`).

`_navigate("activity")` becomes `feature_for("activity").page(host)` with a fallback to the old method for one commit if needed. Delete the fallback in the same slice once tests cover the page.

Why Activity first, not Lens or Photos:

- Lens is split across `lens_home.py` (monkeypatch), `selection.py`, and `HomeApp` methods. Untangling that is step 5.
- Photos is the information-architecture bug (dashboard vs grid). Fixing it changes what the user sees. Step 2 should not.
- People/Unknown are tangled with the inspector list and verb selection (`home_ui.py:3733-3875`).

Visual result of step 2: Recent activity looks the same.

---

## Step 3 — Home consumes the registry

Replace the hand-written pieces with loops:

| Today | Becomes |
|---|---|
| Sidebar loop over `HOME_NAV` (`home_ui.py:1122-1150`) | Loop over nav contributions. `HOME_NAV` remains as a derived view or is deleted once tests read the tuple. |
| `_navigate` if-chain (`home_ui.py:3319-3375`) | Lookup route id → `page(host)`. Routes not yet migrated keep a temporary fallback table that calls the old methods. |
| More menu (`home_ui.py:1008-1015`) | Commands whose surface is `overflow`. Same four labels. |
| Ctrl+1…5 (`home_ui.py:975-979`) | Shortcuts on the nav records. Preserve the current mapping (Photos, Videos, People, People to name, Activity). Lens stays without a number unless product copy changes. |
| Ctrl+K (`home_ui.py:3035`) | “Go to” from nav contributions + Settings. Add type-to-filter here; the list contents stay destinations. |
| Settings body (`home_ui.py:4077-4218`) | Shell draws the frame and scrollbar. Sections are contributions: Library, Processing, Appearance, About, Advanced, Diagnostics. Appearance and the window theme stay shell-owned if that is cleaner; they can be a `ShellFeature`. |

`HomeApp` starts using one `Application` (or keeps its `JobEngine` and passes it into `Application`) so feature code stops constructing a second engine. Today Home builds `JobEngine` itself (`home_ui.py:875`) and `Application` builds another (`application.py:119`). Pick the Home engine as the one the façade wraps, so pause/cancel state cannot diverge.

Job chrome stays hand-written in the shell. It is not a feature page.

After this step a new **page** is a feature module plus registration. Old routes still work through the fallback table until step 6.

---

## Step 4 — Expose one hidden capability through commands

**Command:** `people.show_history`  
**Engine:** `memory.history` (`memory.py:323`)  
**CLI today:** `semblon memory history --person` (`cli.py:380-383`)  
**GUI today:** none. Activity will not grow a per-person list in this step.

Behavior:

- `when`: exactly one selected item with `kind == "person"`.
- Surfaces: inspector, command palette. Not the sidebar.
- `run`: call `history` for that person id or display name and render soft lines in the inspector (dates and places already produced for memory; do not print `person_id`).
- If there is no EXIF and no filename time, show the empty line the memory function already implies. Do not invent a place.
- Time and place do not affect identity scores (existing memory rule).

This is the proof of scenario C. No `HomeApp` branch for “history”. No new nav item.

Add `Application.person_history(...)` only if the command would otherwise import `memory` from a widget. Prefer the feature calling `memory.history` directly if `Application` is being kept thin. Either is acceptable; do not duplicate the query.

Secondary, still in this step if it stays small: `review.note` on the inspector, calling `apply_note` (`review.py:978`), shown when a cluster or face is selected. Review’s Note button should call the same command. If that doubles the slice, leave note for the next slice and ship history alone.

---

## Step 5 — Lens contextual actions

Remove `lens_home.install`’s monkeypatch (`lens_home.py:97-99`) by making region mouse-up call `lens.find_similar` explicitly. Product launch (`run_product_home`) stays the door; it should not patch a class.

Register the three commands from the target architecture:

1. `canvas.inspect_hits` — current drag release (`canvas.py:1016`).
2. `lens.find_similar` — current product mouse-up (`lens_release.remember_selection`).
3. `lens.ask` — current “Ask about this photo” (`home_ui.py:1572`). Add an optional rectangle argument so a later change can ask about the selection without a new shell branch. Do not switch the mouse-up to `query_image` in this step. That would change results users already see (histogram similar vs full catalog).

Inspector and palette list these when a photo or region is current. The always-packed “Select a region” / “Ask with Lens” buttons (`home_ui.py:1303-1310`) become the rendered command list for that selection, so they disappear on People if `when` is false.

Availability: Lens feature reads `status_report()` and uses `home_shell._state_label` (`home_shell.py:46`). A missing model disables `lens.ask` sub-results inside the feature, not inside `HomeApp`.

Canvas hover remains a viewer behavior. Hover can set `Selection.hover` so a command with `when=hover.kind=="face"` can appear. Do not add a new page.

Identity: `find_similar` stays on the non-face path (`region_search.py:58-59`). `lens.ask` must keep the Lens rule that providers do not write `faces.person_id`.

---

## Step 6 — Remaining routes leave the fallback table

Order, one route per slice:

1. **Videos** — already a thin `CanvasWorkspace` filter (`home_ui.py:3345`). Easy page.
2. **Photos grid** (`photos`) — same canvas, `source_types=("folder",)`.
3. **Library dashboard** (route `home`, label Photos) — landing / processing / result card stay shell states **or** become the library feature’s page that delegates processing chrome to the shell. Processing must keep working during ingest (`_show_home_landing` PROCESSING branch, `home_ui.py:2558-2569`).
4. **People and People to name** — move list population out of `HomeApp`. Verb buttons stay the shared command renderer from step 3.
5. **Review** — remains a Toplevel. Its buttons call the same command ids. Do not merge Review into the sidebar.
6. **Settings sections** — already split in step 3; delete the inline builder.
7. **Qt `ShellWindow` nav** (`native_shell/window.py:134-136`) — optional follow-up. Point labels at the same nav contributions so it stops drifting. Do not add a second product workflow there. Skip if the slice budget is the Tk shell only.

Information architecture fix, **its own slice after the registry works**, because it changes the sidebar meaning:

- Either the item labeled Photos opens route `photos` (the grid), and the dashboard becomes “Library” or the empty/first-run state,
- or the dashboard keeps the Photos label and the grid CTA stays, but the inspector sentence “Browse Photos when you want the grid” (`home_ui.py:2599`) is rewritten so it does not tell the user to click the button they already clicked.

Do not do both. Prefer: **Photos opens the grid** once the dashboard has another honest name, because Videos already opens a grid and Photos should match. The dashboard remains the first-run and processing state. That slice updates `tests/test_home_ui.py:264-278`, which currently locks the populated home to the shell.

`_show_library_home`: delete it in the IA slice, or call it only if product intent returns to “strip + grid”. Do not leave it as a secret third layout.

---

## What stays true at every step

- `python -m semblon home` still opens Tk Home (`cli.py:1126-1129`).
- FaceKit remains the only identity engine. Commands do not compare embeddings in widgets.
- Unknown stays a valid end state. Rule out and Ignore stay distinct.
- `semblon lab` is not registered as product commands.
- Job pause/cancel remains between files (`jobs.py` module docstring).
- Optional Qt shell is not required for the Tk migration.
- No new DDL.

## Suggested slice sequence

| Slice | User-visible change |
|---|---|
| 1. Registry shadow | None |
| 2. Activity module | None |
| 3. Shell reads the registry | None, plus Ctrl+K filters typed text |
| 4. Person history command | New inspector / palette action |
| 5. Lens commands, drop monkeypatch | Inspector actions follow selection |
| 6a–6f. Move remaining pages | None until the Photos label slice |
| Photos label | Sidebar Photos opens the grid |

Stop after any slice. The app is still the product.
