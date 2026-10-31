# Lens behaviour recovery matrix

**Date:** 2026-10-28
**Commit:** `549161c7866b63aaa6e2bb0014af67650252a87e` (wiring is uncommitted on `grok/lens-behaviour-recovery`)
**Method:** static comparison, then a wiring pass for the controls that already had slots. "Usable" means a control on the QML file `semblon shell` loads calls the behaviour. Offscreen Qt tests loaded `Table.qml` and activated the new controls. A person was not watched in a visible window.

Production window: `semblon/native_shell/host.py:26` loads `qml/Table.qml`. `tests/test_contact_sheet.py` asserts `Shell.qml` and `HomeLaunchpad.qml` are absent. `docs/TIMELINE-VIEW.md` and `docs/UI-EXPOSURE-MAP.md` still describe that deleted calendar shell. `docs/UX-CONTACT-SHEET.md` and `docs/BUILD-STATUS.md` describe the Roll that loads.

Historical Lens door: `semblon/lens_home.py` was deleted in `e418c22` (`Complete PySide6 production migration and retire review.html`). The last copy (`git show e418c22^:semblon/lens_home.py`) is a Tk mouse-up handler, not a shell of its own. `HomeApp` / `run_home_ui` are not in the tree. `product_features.py` still describes the old Lens route. `native_shell` does not import it.

The wiring pass calls existing slots from `Table.qml`. It does not import `DiscoverySession` or `CompareSession`, and it does not call `ArchiveSession.push_lens`.

## How to read a row

| Status | Meaning |
|---|---|
| Survived | Same job, and the loaded window exposes it |
| Replaced, usable | A different control does the job, and the loaded window exposes it |
| Replaced, partial | A control exists, but it is narrower, gated, or stops short of the old job |
| Present, not reachable | The function is still in Python or QML, and nothing on `Table.qml` calls it |
| Gone | Removed with Tk Home or `Shell.qml`, and no successor was found |
| Stale doc | A current document still describes a file the loader does not open |

## 1. lens_home and old Lens navigation

| Historical behaviour | Evidence | Current surface | Status | Usable from `semblon shell`? |
|---|---|---|---|---|
| Product launch installs the Lens mouse-up, then starts Tk Home | `lens_home.run_product_home` in the deleted file; `install` replaces `HomeApp._open_region_select` | `cli.py` has no `home` command. `host.py` builds `Table.qml` | Gone as a door | No. The production command is `semblon shell` |
| Lens as its own route: open a photo, then region tools, otherwise tell the person to open a photo | `product_features.py:77-92` `_page_lens` | No Lens item in `Table.qml`, `LightTable.qml`, or the Ctrl+K palette (`Table.qml:286-313`) | Gone as a route | No separate Lens page. Region tools live on the open photo |
| Sidebar Lens destination, Lens button in the brand row, Ctrl+K jumping to the Lens route | `docs/GUI-ARCHITECTURE-FORENSIC-AUDIT.md` (historical; cites deleted `home_ui.py`) | Light Table verbs and the picture More menu | Replaced, usable | Yes, as picture actions, not as a route |
| Region select off the Lens route in a Tk "Lens — select a region" window | Forensic audit cites `selection.py` `open_region_window` | Focus loupe on `Viewer.qml` (`findDetail`, label "Find this part again") | Replaced, usable | Yes. Draw on the open photo. No second Tk window in the shell |

## 2. Time / Moment scrubber and Field projection

| Historical behaviour | Evidence | Current surface | Status | Usable from `semblon shell`? |
|---|---|---|---|---|
| Bottom year scrubber on the calendar shell | `docs/TIMELINE-VIEW.md:18` says it was removed. That doc's `Shell.qml` is not loaded | Right-edge month scrubber | Replaced, usable | Yes. `Scrubber.qml:3-26`, mounted at `Table.qml:69-81`. Click, drag, Up/Down move month by month. Hidden while the photo, People, or Tidy is open (`Table.qml:79`) |
| Calendar densities (Years / Months / Days), day grid, left-nav Browse | `docs/TIMELINE-VIEW.md`. Object names such as `memoryCalendar`, `sidebarMoments` are not in the loaded QML | One Roll, newest first, month and day rows | Replaced, partial | The Roll is usable (`Roll.qml`, `docs/UX-CONTACT-SHEET.md`). The calendar workspace is not. `ShellBridge` still defaults `_library_workspace` to `"calendar"` (`bridge.py:433`) and `escape` still calls `showCalendar` (`bridge.py:3554-3555`), but `Table.qml` never shows that workspace |
| Field as a lens projection (time, person, search) with Back restoring the previous lens | `archive_session.py:32-48` `Lens`; `push_lens` `285-292`; `lens_history` `164-165`; `back` `294-298` | Roll order is the time list. Filters replace `ArchiveModel` ids | Present, not reachable | `push_lens` has no caller outside `archive_session.py`. `test_archive_session.py` exercises it. The shell never pushes a person or search lens |
| Moments as named-person bursts in the library browse | `library_browse.moment_buckets` `120`; `ArchiveAdapter.browse("moments")` `adapter.py:78-80`; `ShellBridge.setFacet` / `selectBucket` `bridge.py:4292-4327` | Light Table "Moments" and the moments sheet. "Find by date" is unchanged | Replaced, usable | Yes. "Moments" (`LightTable.qml` `momentsButton`) and Ctrl+K call `setFacet("moments")` and open `momentsSheet`. A row calls `selectBucket`. "Find by date" still jumps on `YYYY` or `YYYY-MM` and does not open that list. "Show everything again" calls `setFacet("memory")` when a facet is active |
| Person-scoped Field ("only this person's photos") | `showSelectedPersonOnly` `bridge.py:3118-3176` sets `_person_field_filter` and `set_media_ids` | People "Only their photos", plus "See their photos by date" | Replaced, usable | Yes, for the narrower grid. "Only their photos" (`People.qml` `onlyTheirPhotos`) calls `showSelectedPersonOnly` when `selectedPersonId` is set, and returns to the Roll only if the filter turned on. "See their photos by date" still calls `browseSelectedPersonInTime` and opens one dated photo. "Show everything again" calls `clearPersonFieldFilter` while that filter is on |
| Year / month / range Field sections | `editorial.field_sections` `editorial.py:411`; filled in `_apply_scope_view` (`bridge.py:1010-1014`) | Not bound by the loaded QML | Present, not reachable | The Roll does not render `fieldSections` |

## 3. Lens history and restoration

| Historical behaviour | Evidence | Current surface | Status | Usable from `semblon shell`? |
|---|---|---|---|---|
| Lens stack: push a view, Back restores scroll, selection, focus, and desk | `archive_session.py:285-298`, `345-359`. `test_lens_history_restores_scroll_selection_and_focus` | Bridge `escape` clears Focus, then may call `showCalendar` | Present, not reachable | Session `back()` is only called from session `wordmark()` (`archive_session.py:300-306`). Bridge `wordmark` (`bridge.py:3619-3621`) opens the library stage and does not call the session method. No QML calls `wordmark` |
| Last Lens result kept on the Tk home object | Deleted `lens_home.py` sets `home._last_lens_result` | In-memory discovery trail, max 8 (`bridge.py:1891-1906`) | Replaced, usable | A new Similar search pushes the previous result. More… "Back to the previous find" (`Viewer.qml` `backDiscovery`) calls `backToDiscovery` when `canBackDiscovery` is true, and clears a preview first. It does not call `ArchiveSession.back` |
| Preview Back that returns to the previous discovery frame | Discovery trail above | Viewer "Return to original", and the new Back when a preview is up | Replaced, partial | "Return to original" still only clears `previewId` (`Viewer.qml:30`). "Back to the previous find" pops the trail. They are different controls |
| Persist the last visual search and restore it next launch | `_persist_discovery` writes `<store stem>.visual-discovery.json` (`bridge.py:1866-1888`, called from `_publish_similar`) | Settings "Open the last find" | Replaced, usable | The file is still written when a search finishes ready or empty. Settings calls `reopenLastVisualSearch` (`Table.qml` `onLastFindRequested`) and closes Settings first. Startup does not open the file on its own. A missing or unreadable file is said on the notice. Wiping the library deletes the file |
| Person history (when / where), not a Lens stack | `memory.history`; Tk inspector path still described in `product_features.py:280-300` | "Only their photos" uses `history()`. Activity lines come from `showActivity` | Replaced, usable | "Only their photos" is the person grid above. Settings → "Recent activity" calls `showActivity`. The sheet opens in Everyday and in More detail when there are rows (`bridge.py:4724-4730`). An empty activity stays a result message and leaves the sheet closed |

## 4. Focus filmstrip and contextual actions

| Historical behaviour | Evidence | Current surface | Status | Usable from `semblon shell`? |
|---|---|---|---|---|
| Open photo fills the workspace; previous / next move along the archive | Canvas workspace in the forensic audit. Contact-sheet contract: Left/Right in the picture view | `Viewer.qml` Previous / Next call `shell.focusPrev` / `shell.focusNext` (`264-265`). `openFocus` `bridge.py:2761` | Replaced, usable | Yes. Back calls `shell.escape` and closes the viewer (`Viewer.qml:261`) |
| Filmstrip of neighbouring photos under the open photo | Not found as a loaded QML strip of the day | Similar-match strip, plus "See this day" | Replaced, partial | `similarStrip` still shows Similar hits, not the day's neighbours. More… "See this day" (`Viewer.qml` `seeThisDay`) calls `showDayAroundFocus`. When the photo has a day, it leaves the photo so the Roll is that day. A second Escape can still call `showCalendar`, which clears that scope. There is no day filmstrip |
| Click a match to open it, keeping the result set | `openDiscoveryHit` `bridge.py:1938-1944` | Preview, then "Open this photo" | Replaced, usable | A strip click sets `previewId` only (`Viewer.qml:457-461`). "Open this photo" calls `openDiscoveryHit` (`Viewer.qml:31-35`). Preview does not change focus by itself (`Viewer.qml:15-16`) |
| Contextual actions on the open photo | Tk inspector verbs plus Lens buttons (forensic audit) | Top bar plus More… | Replaced, usable | Always visible: Back, Previous, Next, Find this part again, More…. More… also holds "Back to the previous find" when a find is on the trail, and "See this day". Ctrl+K includes "See this day" while a photo is open |
| "Show matches on the Roll" | `showMatchesOnRoll` | Strip button | Replaced, usable | Yes. It replaces the Roll ids and closes Focus. "Show everything again" (`LightTable.qml` `showEverything`) calls `clearMatches` when matches are on the Roll. It also clears a person filter or a moment facet when one of those is active. A match-only clear still restores the previous Roll |

## 5. Similar, Region, Grounding, Review queue

| Historical behaviour | Evidence | Current surface | Status | Usable from `semblon shell`? |
|---|---|---|---|---|
| Mouse-up persists the rectangle and finds similar appearance. Face modality refused on that path | Deleted `lens_home.open_region_select` → `lens_release.remember_selection`. Forensic audit: histogram similar, not the capability catalog | `findSimilar` `bridge.py:5344-5407` → `Application.remember_and_find_region` | Replaced, usable | Yes, after a drawn region: loupe release path described on the slot, More… "Find the picked area elsewhere", shortcut S. Basis label is "Similar look" |
| Whole-photo similar, separate from the rectangle | Tk "Ask" was the catalog; similar-of-whole is a later door | `findSimilarWhole` `bridge.py:5183` | Replaced, usable | Yes. More… and palette id `v-like`. The first label in that slot is "Colour only" (`5214`) |
| Same-face similar, not a name | `findSimilarFaces` `bridge.py:5218-5232` ("no auto-name") | More… "Find faces like these" | Replaced, usable | Yes, shortcut F. It requires a selected face id. It does not stamp `person_id` |
| Ask about this photo (whole frame, capability catalog) | Forensic audit: `selection.run_lens_query` → `lens.query_image` with no crop. `product_features.py:164-166` | `askPhoto` `bridge.py:3746-3758` → `Application.query_media` | Replaced, usable | Yes, from More…. `query_media` passes no capability filter (`application.py:166-183`). `query_image` then uses `LENS_CAPABILITIES` (`lens.py:738`) |
| Ask about this selection (catalog on the crop) | `product_features.py:168-170` `_cmd_ask_selection` | Describe-this-area is `nameSelection` (`bridge.py:5299`), not `query_image` on the crop | Replaced, partial | "Describe this area" is usable when a region is drawn (`Viewer.qml:317`). It calls `jobs.name_selection`. It is not the old catalog-on-crop command |
| Grounding as its own gesture (SAM2 outline, else the rectangle) | `lens.ground_selection` `lens.py:341-346`. `native_shell` has no `grounding` string | Included only because Ask runs every Lens capability | Replaced, partial | No Grounding button. A whole-frame Ask can run `ground_selection` as one catalog row. Region Similar does not call it |
| Screen region as another similar door | `startScreenQuery` `bridge.py:3761` | More… "Pick on screen" | Replaced, partial | The control is on the More menu (`Viewer.qml:320`) and is visible only when `shell.screenQueryAvailable` is true. This pass did not execute a screen selection |
| Review queue / Open Review / Unknown route | Tk "Open Review" and route `unknown` (`product_features.py:143-144`). `openUnresolvedInbox` opens People on the first REVIEW_REQUIRED or UNKNOWN face | Light Table "Review overlooked faces", and People for naming | Replaced, usable | Yes. "Review overlooked faces" (`LightTable.qml` `reviewOverlooked`) and Ctrl+K call `openUnresolvedInbox`. People stays the naming surface. "Find a person" still opens the whole People desk. `reviewCountText` and `unresolvedText` are still not bound in `qml/` |
| "Who is this?" from the open photo | `reviewFaceGroup` `bridge.py:3004-3046` | More… | Replaced, usable | Yes (`Viewer.qml:319`), when `selectedObservationId` is non-empty. It leaves Focus and selects the People row. It does not auto-name |

## 6. DiscoverySession and CompareSession

| Historical behaviour | Evidence | Current surface | Status | Usable from `semblon shell`? |
|---|---|---|---|---|
| `DiscoverySession`: stack of discovery frames, query rect, Back / Clear | `discovery_loop.py:145-175`. Docstring: Memory Canvas path | Bridge `_discovery_trail` is a different object | Present, not reachable | Nothing imports `discovery_loop` or `DiscoverySession`. The shell trail in section 3 is the one the More… Back control uses |
| `CompareSession`: pick 2–4 Similar hits, keep or reject inside the session, never delete files | `culling_compare.py:1-28`, `108-109` | Tidy-up-copies | Present, not reachable as this class | Nothing imports `culling_compare` or `CompareSession`. Tidy is a different review: it can move copies to the Recycle Bin (`bridge.py` tidy path around `4668-4688`). That is not session-only keep/reject |
| Leave Compare as a Tk command | Commit `941edc4` message registers it. The class remains unused | No Leave Compare control in `qml/` | Gone as a command | No |

## 7. What is still not on the loaded window

These still exist as Python or a stale doc. The wiring pass did not give them a control.

| Behaviour | Where it still is | Why it is not usable |
|---|---|---|
| Tk Lens route, inspector Lens buttons, `run_product_home` | `product_features.py` only. `HomeApp` is gone | `native_shell` does not import `product_features` |
| `Shell.qml` calendar, Home launchpad, left-nav Browse | `docs/TIMELINE-VIEW.md`, `docs/UI-EXPOSURE-MAP.md` | `host.py` loads `Table.qml`. The test asserts `Shell.qml` is absent |
| `ArchiveSession.push_lens` / `lens_history` / `back` | `archive_session.py`, `tests/test_archive_session.py` | No shell caller. Discovery Back is the other stack, and it is the one on the photo |
| `openVisualDiscovery` | `bridge.py` `openVisualDiscovery` | No `qml/` caller. The picture actions are already on the open photo |
| `setFacet("folders")` and `setFacet("timeline")` | `bridge.py` `setFacet` | Moments is the facet the shell calls. Folders and timeline are not |
| `DiscoverySession`, `CompareSession` | `discovery_loop.py`, `culling_compare.py` | No importers |
| Year / month / range Field sections | `editorial.field_sections` | The Roll does not render `fieldSections` |
| Grounding as its own gesture | `lens.py` `ground_selection` | No shell control. Whole-frame Ask can include it inside the catalog |

## What this wiring pass did

1. More… "Back to the previous find" calls `backToDiscovery` when `canBackDiscovery` is true. Settings "Open the last find" calls `reopenLastVisualSearch` and closes Settings. `ArchiveSession.push_lens` stays unwired.
2. People "Only their photos" calls `showSelectedPersonOnly`. "See their photos by date" is unchanged.
3. Light Table "Moments" calls `setFacet("moments")` and lists `selectBucket`. "Find by date" is unchanged.
4. Light Table "Review overlooked faces" calls `openUnresolvedInbox`. People stays the naming surface.
5. More… "See this day" calls `showDayAroundFocus`, then leaves the photo when that photo has a day.
6. "Recent activity" opens the sheet whenever there are rows, in Everyday and in More detail.
7. `DiscoverySession` and `CompareSession` stay unused.

Do not resurrect `lens_home`, `Shell.qml`, or Tk Home to close a row.
