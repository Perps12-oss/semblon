# Visual Memory Calendar — locked contract

**Status:** locked on `grok/visual-timeline`; photo column and density views updated 2026-10-20  
**Shell:** `semblon shell` → `Application` → `ShellBridge` / `Shell.qml`  
**Theme:** `semblon/native_shell/tokens.py` (no Quiet Studio hard-coded hex, no vault/padlock/blur)

## Product shape

```text
+-- LEFT NAV: Home · Library · People · Add folder · Settings · Browse (when Library) --+
+-- HOME launchpad (permanent) OR Library stage: ----------------------------------------+
|  CALENDAR COLUMN                         |  PHOTO FIELD                               |
|  Years · Months · Days                   |  sticky heading · day groups or flat grid  |
|  timeline (Months and Days)              |                                            |
|  year matrix OR month grid               |                                            |
+------------------------------------------+--------------------------------------------+
```

Home is a permanent editorial launchpad (`HomeLaunchpad.qml`); Library is this timeline contract. One density timeline only. The bottom year scrubber was removed (product design). Archive browse (media type, folders, Moments, Similar) lives in the left navigation column when Library is open — there is no right-hand “Explore your archive” panel. Primary / Advanced and Atmosphere live in Settings.

On a library stage at least 900 px wide, `archiveHeaderBand` is the left column (density segment, timeline, year matrix or `MemoryCalendar`) and `fieldViewport` is the photo column on its right (`archiveSplit` adjusts the ratio, remembered in appearance prefs). Narrower stages stack the field under the calendar. The field is the same grids as before. Focus, Home, People, and Settings still replace the whole stage. In Focus the photo uses the stage width. File details (`focusDetails`) stay closed until Details is opened, and Close hides that drawer. Matches sit in a tray along the bottom of the stage (`focusTray`).

Calendar day cells size to the left column. Month cells show at most six cropped thumbs. The overflow count is a `+N` mark. Days view keeps the same month grid with numbers only. Years view is twelve month cards of activity dots from real day buckets.

Elevation (Phase 1–2): cool-slate `bg0` canvas → `bg1` nav chrome → `bg2` content wells. Calendar empty days use ghost gradients + dashed borders; media days use bottom readability gradient, dark count pills, and soft under-shadows. Timeline month bars are accent-on-recessed with Jan–Dec ticks. Browse media kinds use a segmented control. Duotone icons + hover/selected accent bars stay on left nav. No right Explore panel.

## Two independent states

| State | Meaning | Changes when |
|---|---|---|
| **Calendar month** (`calendarMonth`) | Which month grid is displayed | Prev/next, Today/`calendarGoHome`, timeline year/month navigation |
| **Media scope** (`scopeKind` / `scopeLabel`) | Which media the Field shows | Day/month/year/range/folder selection, clear |

Browsing the calendar month must **not** silently change the media scope.

## Field sections (year / month / range)

When media scope is `year`, `month`, or `range`, the Field switches from the flat `GridView` to a day-grouped `ListView` (`fieldSections`). Sticky month heading updates while scrolling sections (disabled for single-day / unscoped flat grid). Unscoped, folder, and single-day scopes keep the flat grid.

## Left-nav archive browse

Under primary destinations, a **Browse** block (objectName `archiveSidebar`) provides: folder filter field, Everything / clear scope, Media (All/Photos/Videos), Folders, Moments, Similar. Folder filter is local label match only — not a full-archive content scan. Counts use compact labels (`1.3k`) with exact values in tooltips / accessible names.

## Selection / navigation

| Action | Behavior |
|---|---|
| Prev / next month / Today | Shift `calendarMonth` only |
| Click day number or empty card | `selectDay` (toggle → `clearScope`) |
| Double-click a day | Days density, then `focusDay` (stays selected) |
| Drag across day cards or year-month cards | Inclusive `selectRange` |
| Click a thumb in a day card | `openFocus` for that id |
| Go to date (`calendarJump`) | `revealDay` — calendar month and highlight only |
| No date chip | `showUndated` for the `Unknown day` bucket |
| Scrolling the photo column | `setStickyDay` also moves `calendarMonth`; scope stays |
| Years / Months / Days, or Ctrl+wheel / pinch | `calendarView` only. Bands use hysteresis. Default `months` |
| Click timeline year | Newest month with media in that year + `selectYear` |
| Click timeline month | `selectMonth` (not `selectDay`) |
| Drag timeline across months | Inclusive `selectRange` (month start → month end; either direction) |
| Escape during drag | Cancel incomplete range |
| Clear / Show everything | `clearScope`; calendar month unchanged |
| Hover day/month | Cancellable 150 ms preview; dismissed on leave and on editorial/scope change |
| Empty day / empty month | Honest empty; no fabricated thumbs |
| Zero-result scope | Message + Clear Filter |

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

Ctrl+wheel and a pinch on the archive pane move `calendarView` across Years (low scale), Months, and Days (high scale). The segment buttons follow. The gesture does not change `calendarMonth` or `scopeKind`. Focus keeps its own 1×–8× photo zoom.

## Library work

The calendar and the photo field stay on screen while a folder is added. A chip at the top right reads `Scanning · current / total` (or `?` until a total exists) and opens the same tray as the bottom pill. The pill is always there. While work is running it reads `1 task` or `N tasks`. While nothing is running it reads `Quiet` and the sheet says so, with one next action: check the last folder, or add a folder when none is remembered. Pause, resume, and cancel stay on that sheet. A search in progress is a second row in the same sheet. The sheet does not cover the grid and does not take wheel events.

## Deferred

- Vault / padlock / blurred “hidden” treatments (out of product)
- Day-resolution segments drawn on the density strip (calendar owns day pick)
- A shared-element morph from a month cell into the photo column (the density change is a short opacity fade)

## Object names

`navSidebar`, `homeButton`, `libraryButton`, `emptyState` (Home launchpad), `archiveBrowseFlick`, `archiveSidebar` (left-nav Browse block), `contextSidebarSearch`, `sidebarFolder_*`, `sidebarMoments`, `sidebarSimilar`, `sidebarKind_*`, `timelineHero`, `timelineYear_*`, `timelineMonth_*`, `archiveHeaderBand`, `archiveSplit`, `timelineDensitySegment`, `densityYears`, `densityMonths`, `densityDays`, `yearMatrix`, `yearMonth_*`, `memoryCalendar`, `calendarPrev`, `calendarNext`, `calendarGoHome`, `calendarTitle`, `calendarJump`, `calendarUndated`, `calendarDay_*`, `fieldSections`, `fieldSection_*`, `stickyHeader`, `zeroResultFilter`, `fieldGrid`, `focusDetails`, `focusDetailsClose`, `focusDetailsToggle`, `focusTray`, `focusSearchSpinner`, `focusSearchStatus`, `scanChip`, `taskTray`, `taskPill`, `taskSheet`, `taskSummary`, `closeTasks`
