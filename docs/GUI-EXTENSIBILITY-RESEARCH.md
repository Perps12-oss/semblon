# Extensibility research

**Date:** 2026-09-27. **Retest:** 2026-09-28. The pattern in this file is what PR #112 (`cursor/gui-feature-registry-c466`, not on `main`) implemented as `semblon/gui_registry.py`. That branch is an internal tuple, not a plugin host. It does not bind a context menu even though commands declare a `"context"` surface. See `docs/GUI-TARGET-ARCHITECTURE.md` (Retest) for the test results.  
**Question this file answers:** how mature desktop apps add a feature without editing the shell, which of those ideas fit Semblon, and which UX principles apply whether the widgets stay Tk or move later.

This is not a framework selection. Production GUI remains Tk Home (`semblon home`). Optional Qt `semblon shell` stays optional. Electron, Tauri, a permanent Tk AppShell, CustomTkinter, and FastAPI are out of scope.

---

## 1. Stable shell, features added beside it

The pattern that shows up in production tools is the same shape under different names: the shell owns **slots**, features own **contributions**, a command is **one function** placed on several surfaces.

### What was looked at

| Product or API | Mechanism | What Semblon can copy | What to leave |
|---|---|---|---|
| Visual Studio Code contribution points | `contributes.commands`, `menus`, `keybindings`, `views`, `viewsWelcome`. A command id is separate from where it appears. `when` hides a menu item; `enablement` disables it everywhere. Default palette is Ctrl+Shift+P. Sources: [Contribution Points](https://code.visualstudio.com/api/references/contribution-points), [Commands](https://code.visualstudio.com/api/extension-guides/command), [when clause contexts](https://code.visualstudio.com/api/references/when-clause-contexts). | One action id, many surfaces. Visibility separate from enabled-with-a-reason. Palette is a second path, not the navigation. | Extension marketplace, `package.json` contributions, arbitrary third-party code. |
| Windows commanding | Put a command on the canvas when it is part of the core task. Put rare commands on a command bar, menu, or `CommandBarFlyout` (context menu + primary shortcuts). Source: [Commanding basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/commanding-basics). | Semblon’s Name action belongs near the selection. Backup does not belong on the canvas. | WinUI control classes. |
| Windows NavigationView | Left pane for a **small** set of top-level destinations. Footer for Settings. Compact pane when the window is narrow. Source: [NavigationView](https://learn.microsoft.com/en-us/windows/apps/design/controls/navigationview). | Semblon already has this shape (sidebar, Settings on the top bar, condensed rail under 1100px, `home_ui.py:206-212`). | Rebuilding it in WinUI. |
| Windows app shell guidance | NavigationView as the shell, InfoBar for non-modal status above the page, Mica as a material. Source: [Windows App SDK app structure](https://learn.microsoft.com/en-us/windows/apps/develop/ui/windows-app-sdk-app-structure). | One status channel that is not a `messagebox`. Material is optional. | Treating Mica as a requirement. Tk Home is explicitly opaque (`home_ui.py:3`). |
| Qt `QAction` | One action object feeds a menu, a toolbar, and a shortcut. Enablement is a property. | The same idea in Python: one `Command`, several widgets subscribe. | Rewriting Home in Qt so that `QAction` exists. |
| Eclipse / OSGi extension points | XML extension points, separate classloaders. | The word “extension point” for a slot (nav, inspector, palette). | OSGi, version ranges, third-party classloaders. |
| Blender addons, OBS plugins | User-installed plugins with their own enablement and failure modes. | Nothing for the current requirement. | Plugin host, addon preferences, binary plugins. |

Semblon already has three incomplete versions of this idea:

1. `HOME_NAV` — a table the sidebar loops over (`home_ui.py:199-204`, `1122-1150`). Routing is not in the table.
2. `product_exposure.GUI_PATHS` — a classification table nothing builds UI from (`product_exposure.py:25`).
3. `runtime_contract.CapabilitySpec` — a **backend** catalog (`runtime_contract.py:119-240`). It answers “is this model available?”. It does not answer “which page is this?”.

Those should stay three different lists. A UI feature is not a model provider. A model provider is not a sidebar item. The exposure map already says this (`docs/UI-EXPOSURE-MAP.md` “Backend ≠ nav”), and the code agrees: `LENS_CAPABILITIES` is nine ids (`lens.py:25-36`) and the sidebar has one Lens item.

---

## 2. What a feature module needs to declare

For Semblon the declaration should be a Python object, imported by a single list. Not entry points. Not a JSON manifest on disk. Not a service locator.

Fields that match capabilities the code already has:

| Field | Semblon evidence it is needed | Example |
|---|---|---|
| `id` | Route ids are already strings (`home`, `lens`, `unknown`) | `activity` |
| Display name | Labels already diverge from ids (“People to name” vs `unknown`) | People to name |
| Icon | `NAV_ICONS` / `ui_icons.py` | existing icon name |
| Nav section + order | Sections ASK / LIBRARY / PEOPLE / ACTIVITY (`home_ui.py:199-204`) | PEOPLE, order 20 |
| Page factory | Today each branch of `_navigate` is an implicit factory (`home_ui.py:3319`) | `build_activity_page(host)` |
| Commands | Inspector handlers are commands trapped in methods (`home_ui.py:1891-2047`) | `review.note` |
| Shortcut | Hard-coded binds (`home_ui.py:973-979`) | Ctrl+5 |
| Contextual placement | Canvas selection kinds: media, face, cluster, region (`canvas.py`, inspector items) | show when `selection.kind == person` |
| Required services | `Application` methods, or a plain function | `activity_memory` |
| Availability | `runtime_contract` model state; `gates.enabled` | Lens row “Optional · install needed” (`home_shell.py:46-57`) |
| Empty state | `empty_states.py` | `activity_empty()` |
| Help / one line | `SHELL_SUBCOPY`, Lens subcopy | one sentence, no schema words |

Permissions are a single local user. There is no account system. “Permission” here means **availability** (model missing, job running, nothing selected), which `inspector_verb_states` already computes as `{enabled, reason}` (`inspector_verbs.py:98-99`).

---

## 3. Contextual UI

Windows commanding guidance: a command that is constant for the core task goes on the canvas; a command that is rare goes on another surface; a command that depends on the object goes on a context menu or flyout.

Semblon’s core loop is `cluster → review → person → name`. The future loop in the same product is:

```text
Media → Frame → Observation → Track → Hypothesis → Decision → Entity
```

and, on a picture:

```text
Image → hover or select a region → identify or describe → inspect → search or connect → act
```

The shell should not grow a destination per step. The **selection** is the destination.

Today the selection is already a dict (`kind` of cluster, face, person, region) held on `HomeApp` (`home_ui.py:1315-1322`) and produced by canvas (`canvas.py:1057`). The inspector always shows the same six buttons (`home_ui.py:1278-1310`). Enablement changes; the set does not. There is no context menu.

A contextual host asks the registry:

```text
commands where surface contains "inspector" or "context"
        and command.when(selection) is true
```

Hover on a face and click on a face can share a command and differ only in `when` (`hover` vs `selected`). That is the VS Code split between menu `when` and command `enablement`, reduced to two callables.

Permanent sidebar destinations that match the product, not the engine:

| Destination | Why it stays global |
|---|---|
| Photos | The library. The thing the user came to look at. |
| Videos | Same, different media. Already a route. |
| People | Named persons. A person is not a cluster. |
| People to name | The human decision queue. Unknown stays valid. |
| Recent activity | Memory and job history, read-only. |
| Lens | One place to ask about a picture. Not one item per model. |
| Search | A field, not necessarily a page. Already a top-bar field. |
| Settings | Footer or top-bar. Not a library section. |

Workspaces (pages those destinations open):

| Workspace | Exists today? |
|---|---|
| Photo grid + opened photo | Route `photos` + `CanvasWorkspace`. Sidebar does not open it. |
| Video grid | Route `videos`. |
| Person gallery | No. People is an inspector list (`home_ui.py:3773-3792`). |
| Unknown review | Partial. List of groups in the inspector; full compare is Review. |
| Visual search / Lens | Route `lens`. |
| Memory | Activity sections (`activity_surface.py:401`). No per-person page. |
| Jobs | Processing pane on route `home` while `JobEngine.busy`. Not a job center. |

Contextual capabilities that should be commands, not pages:

| Action | Selection | Already implemented? |
|---|---|---|
| Name this person | cluster or face | Yes, inspector |
| Add to person | cluster or face, and a person target | Yes |
| Combine groups | two clusters | Yes |
| Split | cluster + faces | Yes |
| Not this person | cluster or face | Yes |
| Ignore | cluster or face | Yes |
| Note | cluster or face | Review only |
| Compare faces | cluster | Review only |
| Find similar | region | Yes, histogram path |
| Ask about this selection | region | Engine yes (`query_image` with a rect); product mouse-up does not call it |
| Inspect person | person | List only |
| Show history | person | `memory.history` CLI |
| Show who they appear with | person | Activity aggregate, not filtered |
| Inspect track | track | Review |
| Zoom / open photo | media | Canvas open |
| Explain this box | observation | Inspector soft lines (`product_surface`) |

Zoom, crop-as-edit, and segmentation-as-a-tool are not product features in the tree. Grounding can outline a selection when SAM2 is present (`runtime_contract.py:163-172`, fallback `RECTANGULAR_CROP`). The rectangle is kept when the model is missing. That is an availability state, not a new editor.

---

## 4. Commands as a first-class capability

Yes. Semblon should have one command list. The reason is duplication that already exists, not a theoretical bus.

The same mutation is reachable from:

- Home inspector buttons (`home_ui.py:1278-1302`)
- Review UI buttons (`review_ui.py` actions)
- Qt shell buttons (`native_shell/window.py:162-171`)
- CLI `semblon review` / `name` / `merge` / `split` (`cli.py:326-432`)

Each UI builds its own widgets and calls `review_ui.apply_*` or `review.py`. A command registry does not move that logic into widgets. It points every surface at the same callable:

```text
Command id: review.name
run:        Application / review_ui.apply_name
when:       one cluster or one face selected, run id present
enabled:    inspector_verb_states()["name"]
surfaces:   inspector, context menu, command palette, shortcut
```

`inspector_verb_states` is already the enablement function (`inspector_verbs.py:77`). The missing piece is a host that asks for “verbs for this selection” instead of packing six fixed buttons.

Same operation, several surfaces, one implementation:

| Surface | Host responsibility | Feature responsibility |
|---|---|---|
| Toolbar / inspector | Ask registry, build buttons | Provide command |
| Context menu | Ask registry on right-click or Shift+F10 | Declare `when` |
| Command palette | List commands whose palette `when` is true, filter by title | Declare title |
| Shortcut | Bind from the command record | Declare keys |
| Automation / CLI | Call `run` with an explicit context | No widget code |
| Future native client | Same records, different widgets | No second copy of enablement |

CLI can stay argparse. It does not have to be generated. The win is that a new GUI surface does not reimplement `apply_name`.

Do not put lab commands in the palette. Visibility `when` is how VS Code keeps the palette from listing every internal command. Semblon’s equivalent is: product commands opt in; `semblon lab` never registers a product command.

---

## 5. Command palette

Ctrl+K already exists (`home_ui.py:974`, `3035-3079`). It is titled “Go to”. It lists sidebar labels plus Settings. It does not filter keystrokes. It does not run “Find similar” or “Review unknown people”.

That is the right host and the wrong contents.

A palette worth having:

- Opens with Ctrl+K, closes with Escape (already).
- Type-to-filter on the title.
- Two groups inside one list: **Go to** (nav contributions) and **Actions** (commands).
- Does not replace the sidebar. Windows and VS Code both keep primary navigation visible.
- Hides actions that do not apply (`when` false) so the list is not a dump of disabled buttons.
- Shows a disabled row with the reason only when the user is clearly in that context (a face is selected and identify is unavailable). `inspector_verb_states` already has those reason strings.

Examples that should resolve to commands, not new pages:

| Typed | Resolves to |
|---|---|
| Find similar | `lens.find_similar` if a region or photo is current; otherwise explain that a photo must be open |
| People to name | navigate `unknown` |
| Show history | `memory.history` if a person is selected |
| Settings | open settings host |
| Videos of this person | future command; engine support is PARTIAL (person’s faces have media). Do not invent it in the palette until the query exists |

Ctrl+F should keep focusing the search field (`home_ui.py:973`). Search-the-library and the command palette are different questions: “who is Ada?” versus “what can I do?”.

---

## 6. Feature registration, concrete and small

Adding a feature should be:

```text
create feature module
        ↓
append it to the product feature tuple
        ↓
shell builds nav, commands, and settings from that tuple
```

The shell file that changes is the tuple, one line. Not Home, sidebar, router, toolbar, settings, and a chain of `if nav_id ==`.

Sketch (not an implementation, and not a public plugin API):

```text
Feature
  id, title
  availability() -> available | unavailable(reason) | hidden
  nav: (section, route_id, label, icon, order) or none
  page(host) -> widget
  commands: (id, title, when, enabled, run, surfaces, shortcut)
  settings: (title, build) or none
  services: names it reads from the host session
```

`host` is a narrow protocol the shell implements:

```text
navigate(route_id)
set_inspector(title, lines)
selection() -> current selection
session() -> Application (or the same functions)
notify(level, text)          # replaces ad-hoc messagebox for status
open_dialog(build)           # settings and confirmations
```

Features do not import `HomeApp`. `HomeApp` does not import feature internals except through the tuple. Today `lens_home.install` patches `HomeApp` (`lens_home.py:97-99`), which is the opposite dependency.

Registration site: one module, for example a tuple `PRODUCT_FEATURES`, imported by `run_home_ui`. Explicit. Grep-able. Testable without Tk by reading the tuple and calling `when` / `enabled` with a fake selection.

Failure isolation: one feature’s `page()` raising should show that page’s empty/error state, not kill the process. The shell already does this ad hoc for canvas reload (`home_ui.py:3306-3312`). A registry makes it the default around `page()`.

Availability: if SigLIP is missing, `lens.find_similar` stays visible in the Lens context and disabled with “Similar search needs photos that have already been looked at” (copy already in `lens_release.py:46-49`) or the catalog line from `home_shell._state_label`. It must not raise, and it must not look like a successful empty match. That rule is already in `lens.py` and `runtime_contract.assert_honest`.

---

## 7. This is not a plugin system

The requirement is: a Semblon feature can be added without restructuring the shell.

That is an internal module boundary. It is satisfied by a tuple of feature objects in the Semblon package.

A user-installable plugin system would add:

- discovery outside the repo (entry points, a plugins folder)
- untrusted code in-process with the photo library and FaceKit
- versioning, disablement, and crash isolation
- a second support surface
- a way for a plugin to vote on identity by writing the store

Semblon is one user, local-first, one identity engine. Nothing in the product docs or the CLI asks for third-party installation. `product_exposure.py` even forbids a list of shell technologies; it does not define a plugin slot.

**Internal feature modules are enough.** Revisit plugins only if a later product decision says other people ship Semblon extensions. That decision is not implied by this research.

Dynamic menus and a command palette are not plugins. They are views over the internal tuple.

---

## 8. UX principles to adopt (independent of WinUI)

Sources: [NavigationView](https://learn.microsoft.com/en-us/windows/apps/design/controls/navigationview), [Commanding basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/commanding-basics), [Windows App SDK app structure](https://learn.microsoft.com/en-us/windows/apps/develop/ui/windows-app-sdk-app-structure) (InfoBar, shell layout). Mica is described there as a WinUI material. Semblon can adopt the layout principles and keep opaque Tk (`home_ui.py:3`).

| Principle | Current Semblon | Adopt |
|---|---|---|
| Few top-level destinations | Six sidebar items plus a Lens button that repeats one of them. Photo grid is not one of the six. | One destination per user place. Name the dashboard something other than Photos, or make Photos open the grid. |
| Settings in the footer or a stable corner | Settings button on the top bar (`home_ui.py:946`). | Keep one Settings entry. Do not add feature settings as sidebar items. |
| Narrow window keeps navigation | Condensed horizontal rail (`home_ui.py:3181-3205`). | Keep. Lens stays on it (`shell_is_condensed` docstring). |
| Commands near the object | Inspector is a column of always-on verbs. | Show verbs that match the selection. Primary verb is Name when a group is selected. |
| Rare commands off the canvas | More menu and Settings → Advanced exist. | Keep Review, Live, export, diagnostics off the sidebar. |
| Non-modal status | Progress text is good (`home_ui.py:1026`). Errors often use `messagebox` (`home_ui.py:1898`, `3654`, `3936`). | Reserve modal dialogs for destructive confirm (Ignore, Rule out, exit while busy). Status and “unavailable” go inline. |
| Empty, not blank | `empty_states.py` is used on People, Photos, Videos, Activity, Search. | Keep. A missing model is an empty/unavailable state, not a crash and not a fake “no matches”. |
| Long jobs | Processing pane, pause between files, cancel, result card (`home_ui.py:2363`, `2742`, `3081`). | Keep this as shell chrome. It is application-level, not a feature page. |
| First run | Landing CTA “Add a photo folder”, privacy line (`landing_cta_plan`, `home_ui.py:300-314`). | Keep. Do not lead with capability ids. |
| Language | Product copy is often soft (`product_surface.py`). Leaks remain: Live asks for “Camera index or RTSP URL” (`home_ui.py:4271`); change-library asks for `store.sqlite` (`home_ui.py:4236`); landing tile “Observations” (`home_shell.py:124`); Lens catalog labels include “Visual embedding” and “Grounding” (`runtime_contract.py:142-167`) shown on the landing (`home_ui.py:2320`); Qt shell prints `face_id` and “Cluster ≠ person” (`native_shell/window.py:290-309`). | User vocabulary: photo, person, group, name, unknown. Engineering vocabulary stays in Diagnostics. |
| Keyboard | Ctrl+F, Ctrl+K, Ctrl+1…5, Enter to search, Escape on palette and name field. No documented context-menu key. Listboxes are the People UI. | Keep shortcuts. Add Shift+F10 / context menu only when commands exist. Search entry sets `takefocus` (`home_ui.py:956-957`); extend names to icon-only buttons if any appear. |
| Density and resize | Min size from tokens (`WINDOW_MIN`), inspector collapses on the cold home (`home_ui.py:3164-3174`). | Keep one inspector. Do not add a second column per feature. |
| Consistency | Tk tokens (`ui_tokens.py`) and `Button` kinds. Review is a different chrome (WebView when present, `review_ui.py:2050`). | Review can stay a workspace. It should use the same verbs and the same command ids. |
| Progressive disclosure | More, Advanced, Diagnostics are the right layers. | Do not undo that by promoting Live, HTML, or lab tools. |
| Accessibility | No full keyboard map of the canvas. Hover-only discovery of boxes (`canvas.py:381-385` hover outline). | Selection must also work from the keyboard once a photo is open: arrows between faces, Enter to inspect. Hover can stay as extra. |
| Honesty | Available vs optional rows (`home_shell.py:60-105`). Last result distinguishes failure from no match (`home_shell.py:132-149`). | Keep. Wire the same states to buttons so a dead action is disabled with a reason. |

Hierarchy the UI should teach, in order:

1. Your photos are here.
2. People you have named are people. Groups are not people yet.
3. Unknown is an acceptable outcome.
4. You can ask about a picture when you have one open.
5. Everything else is a command on the thing you selected, or a setting.

---

## 9. What not to copy

- A page per `CapabilitySpec` id.
- A plugin directory.
- A dependency-injection container. `Application` is already the service boundary (`application.py:1-8`). Pass that object into commands.
- Generating the CLI from the GUI registry. The CLI is the automation door and includes lab commands the GUI must not list.
- Replacing `messagebox` confirmations for destructive identity actions with a toast. Ignore and Rule out should stay explicit (`home_ui.py:2008`, `2035`).
