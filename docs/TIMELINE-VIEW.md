# Visual Memory Calendar — locked contract

**Status:** locked on `grok/visual-timeline`; one library workspace updated 2026-10-23  
**Shell:** `semblon shell` → `Application` → `ShellBridge` / `Shell.qml`  
**Theme:** `semblon/native_shell/tokens.py` (no Quiet Studio hard-coded hex, no vault/padlock/blur)

## Product shape

```text
+-- LEFT NAV: Home · Library · People · Add folder · Settings · Browse (when Library) --+
+-- HOME launchpad (permanent) OR one library workspace: -------------------------------+
|  1. CALENDAR fills the pane     Years · Months · Days · timeline · year or month grid |
|  2. GRID fills the pane         one day, or a folder / moment / everything selection  |
|  3. FOCUS fills the pane        the photo, a slim Back, file details on the rail      |
+---------------------------------------------------------------------------------------+
```

Home is a permanent editorial launchpad (`HomeLaunchpad.qml`); Library is this timeline contract. One density timeline only. The bottom year scrubber was removed (product design). Archive browse (media type, folders, Moments, Similar) lives in the left navigation column when Library is open — there is no right-hand “Explore your archive” panel. Primary / Advanced and Atmosphere live in Settings.

The library has one workspace and three depths. `libraryWorkspace` is `calendar` or `grid`. While it is `calendar`, `archiveHeaderBand` fills the pane (density segment, timeline, year matrix or `MemoryCalendar`). A date click, the no-date chip, a folder, a moment, Everything, or a search that replaces the field sets `grid`: the calendar hides and `fieldViewport` fills the same pane. Focus is the third depth. The photo fills that pane, with a slim Back control. Home, People, and Settings still replace the whole stage. File details (`focusDetails`) stay closed until Details is opened, and Close hides that drawer. Matches sit in a tray along the bottom of Focus (`focusTray`). `archiveSplit` stays in appearance prefs. The divider is not shown.

Calendar day cells size to the pane. Month cells show at most six cropped thumbs. The overflow count is a `+N` mark. Days view keeps the same month grid with numbers only. Years view is twelve month cards of activity dots from real day buckets.

Elevation (Phase 1–2): cool-slate `bg0` canvas → `bg1` nav chrome → `bg2` content wells. Calendar empty days use ghost gradients + dashed borders; media days use bottom readability gradient, dark count pills, and soft under-shadows. Timeline month bars are accent-on-recessed with Jan–Dec ticks. Browse media kinds use a segmented control. Duotone icons + hover/selected accent bars stay on left nav. No right Explore panel.

## Two independent states

| State | Meaning | Changes when |
|---|---|---|
| **Library workspace** (`libraryWorkspace`) | `calendar` fills the pane, or `grid` replaces it | `openDay`, folder / moment / everything, `showCalendar` |
| **Calendar month** (`calendarMonth`) | Which month grid is displayed | Prev/next, Today/`calendarGoHome`, timeline year/month navigation |
| **Media scope** (`scopeKind` / `scopeLabel`) | Which media the grid shows when it is open | Day/folder selection, clear. Year and month do not open the grid |

Browsing the calendar month must **not** silently change the media scope.

## Field sections (year / month / range)

Year, month, and range scopes still build day-grouped rows (`fieldSections`) for the model. They do not open the photo grid. The calendar stays the library. A day, folder, moment, or everything grid uses the flat `GridView`, with a sticky heading only when sections are the visible grid.

## Left-nav archive browse

Under primary destinations, a **Browse** block (objectName `archiveSidebar`) provides: folder filter field, Everything / clear scope, Media (All/Photos/Videos), Folders, Moments, Similar. Folder filter is local label match only — not a full-archive content scan. Counts use compact labels (`1.3k`) with exact values in tooltips / accessible names.

## Selection / navigation

| Action | Behavior |
|---|---|
| Prev / next month / Today | Shift `calendarMonth` only |
| Click day number or empty card | `openDay` — always enters that day's grid. `selectDay` remains the toggle used by the bridge API |
| Double-click a day | Days density, then `openDay` (stays on that day) |
| Drag across day cards or year-month cards | Inclusive `selectRange`. Stays on the calendar |
| Click a thumb in a day card | `openDay` for that cell, then `openFocus`. First Back lands on the day's grid |
| Go to date (`calendarJump`) | `revealDay` — calendar month and highlight only |
| No date chip | `showUndated` opens the `Unknown day` grid |
| Back from the grid / Escape on the grid | `showCalendar` — same month, that day highlighted, scope cleared |
| Back from Focus / Escape on Focus | Closes Focus. The grid is still there when a day or other scope is open |
| Scrolling the photo grid | `setStickyDay` also moves `calendarMonth`; scope stays |
| Years / Months / Days, or Ctrl+wheel / pinch | `calendarView` only, and only while the calendar is showing. Bands use hysteresis. Default `months` |
| Click timeline year | Newest month with media in that year + `selectYear` |
| Click timeline month | `selectMonth` (not `selectDay`) |
| Drag timeline across months | Inclusive `selectRange` (month start → month end; either direction) |
| Escape during drag | Cancel incomplete range |
| Clear / Show everything | `showEverything` opens the full grid. `clearScope` still clears a filter without opening the grid. Calendar month unchanged |
| Hover day/month | Cancellable 150 ms preview; dismissed on leave and on editorial/scope change |
| Empty day / empty month | Honest empty grid or empty month. No fabricated thumbs. Back leaves the empty day |
| Zero-result scope | Honest empty line on the grid. Back clears the scope |

## Day cells

- Clear thumbnails via `image://archive/`; one representative id per day, plus up to six `previewIds`
- A colored block stands in until that thumb's image is ready, including tiles in the flat photo field. Decode stays on `ArchiveImageProvider`
- The first view of a photo writes one 384 px JPEG beside the store (`<store stem>.thumbs/`). Later grid cells read that file. Focus frames are not written there. Clearing the library deletes the folder. Originals stay put.
- Compact count (`1.3k`) + exact accessible name (`1,282 photos`)
- Outside-month days have no numeral; today and keyboard focus stay distinct from the scope selection
- `emphasized` dots days that intersect the active person filter or folder scope
- A video representative is labelled Video
- `revealDay` highlights a cell without changing scope. People in Time and a kept find call it

## Keyboard

- Timeline: Left/Right years; Up/Down months; Enter activates; Escape cancels drag or clears scope
- Calendar: arrows (cross month boundaries); Enter/Space selects; Escape clears
- Sidebar: search focusable; section headers toggle expand/collapse

## Performance notes

Measured 2026-10-15 (offscreen Qt): high-volume day (1,282 ids) cell build **2.8 ms**, preview ids were capped at **3**, label `1.3k`; synthetic **1,372** media → shell open **731 ms**; `selectDay` **279 ms**; year `selectRange` **1140 ms** / 10 sections; 12× `calendarNextMonth` **573 ms**. The cap is now **6** preview ids plus `overflow`. The structural bound remains: a cell never requests one image per file.

Ctrl+wheel and a pinch move `calendarView` across Years (low scale), Months, and Days (high scale) while the calendar is the workspace. The segment buttons follow. The gesture does not change `calendarMonth` or `scopeKind`, and it does not run over the photo grid. Focus keeps its own 1×–8× photo zoom.

Back is one step: fullscreen photo, then that day's grid (or the folder / moment / everything grid), then the calendar. Escape uses the same stack and closes the task tray first when that sheet is open. An empty day is an empty grid with Back. No fabricated thumbs. A folder, a moment, Everything, and a search that replaces the field open that same grid, titled with the scope. Year, month, and density changes stay on the calendar.

## Library work

The task tray and the scan chip stay on top of the calendar, the day grid, and Focus. A chip at the top right reads `Scanning · current / total` (or `?` until a total exists) and opens the same tray as the bottom pill. The pill is always there. While work is running it reads `1 task` or `N tasks`. While nothing is running it reads `Quiet` and the sheet says so, with one next action: check the last folder, or add a folder when none is remembered. Pause, resume, and cancel stay on that sheet. A search in progress is a second row in the same sheet. The sheet does not take wheel events.

## Deferred

- Vault / padlock / blurred “hidden” treatments (out of product)
- Day-resolution segments drawn on the density strip (calendar owns day pick)
- A shared-element morph from a month cell into the photo column (the density change is a short opacity fade)

## Object names

`navSidebar`, `homeButton`, `libraryButton`, `emptyState` (Home launchpad), `archiveBrowseFlick`, `archiveSidebar` (left-nav Browse block), `contextSidebarSearch`, `sidebarFolder_*`, `sidebarMoments`, `sidebarSimilar`, `sidebarKind_*`, `timelineHero`, `timelineYear_*`, `timelineMonth_*`, `archiveHeaderBand`, `archiveSplit` (stored, not shown), `timelineDensitySegment`, `densityYears`, `densityMonths`, `densityDays`, `yearMatrix`, `yearMonth_*`, `memoryCalendar`, `calendarPrev`, `calendarNext`, `calendarGoHome`, `calendarTitle`, `calendarJump`, `calendarUndated`, `calendarDay_*`, `gridBack`, `gridWorkspaceTitle`, `fieldSections`, `fieldSection_*`, `stickyHeader`, `zeroResultFilter`, `fieldGrid`, `focusBack`, `focusDetails`, `focusDetailsClose`, `focusDetailsToggle`, `focusTray`, `focusSearchSpinner`, `focusSearchStatus`, `scanChip`, `taskTray`, `taskPill`, `taskSheet`, `taskSummary`, `closeTasks`
