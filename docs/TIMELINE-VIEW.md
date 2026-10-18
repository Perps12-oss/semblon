# Visual Memory Calendar — locked contract

**Status:** locked on `grok/visual-timeline`  
**Shell:** `semblon shell` → `Application` → `ShellBridge` / `Shell.qml`  
**Theme:** `semblon/native_shell/tokens.py` (no Quiet Studio hard-coded hex, no vault/padlock/blur)

## Product shape

```text
+-- LEFT NAV: Home · Library · People · Add folder · Settings · Browse (when Library) -----+
+-- HOME launchpad (permanent) OR Library stage: -----------------------------------------+
|     HERO DENSITY TIMELINE · MEMORY CALENDAR · FIELD                                    |
```

Home is a permanent editorial launchpad (`HomeLaunchpad.qml`); Library is this timeline contract. One density timeline only. The bottom year scrubber was removed (product design). Archive browse (media type, folders, Moments, Similar) lives in the left navigation column when Library is open — there is no right-hand “Explore your archive” panel. Primary / Advanced and Atmosphere live in Settings.

Archive uses a single column: `archiveHeaderBand` (timeline + clipped `MemoryCalendar` + sticky/zero) then `fieldViewport` below it. Calendar day cells size to fit inside the calendar height (including the empty-month line) so they cannot overflow into the Field.

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
| Click day | `selectDay` (toggle → `clearScope`) |
| Click timeline year | Newest month with media in that year + `selectYear` |
| Click timeline month | `selectMonth` (not `selectDay`) |
| Drag timeline across months | Inclusive `selectRange` (month start → month end; either direction) |
| Escape during drag | Cancel incomplete range |
| Clear / Show everything | `clearScope`; calendar month unchanged |
| Hover day/month | Cancellable 150 ms preview; dismissed on leave and on editorial/scope change |
| Empty day / empty month | Honest empty; no fabricated thumbs |
| Zero-result scope | Message + Clear Filter |

## Day cells

- Clear thumbnails via `image://archive/`; one representative id per day
- Compact count (`1.3k`) + exact accessible name (`1,282 photos`)
- Outside-month days subdued; today outlined; keyboard focus ≠ selected
- Preview capped at three thumbs; full day opens via scope / Field

## Keyboard

- Timeline: Left/Right years; Up/Down months; Enter activates; Escape cancels drag or clears scope
- Calendar: arrows (cross month boundaries); Enter/Space selects; Escape clears
- Sidebar: search focusable; section headers toggle expand/collapse

## Performance notes

Measured 2026-10-15 (offscreen Qt): high-volume day (1,282 ids) cell build **2.8 ms**, preview ids capped at **3**, label `1.3k`; synthetic **1,372** media → shell open **731 ms**; `selectDay` **279 ms**; year `selectRange` **1140 ms** / 10 sections; 12× `calendarNextMonth` **573 ms**. High-volume day cells keep one thumb + ≤3 preview ids regardless of count (structural bound).

## Deferred

- Pinch/zoom Years ↔ Months ↔ Days morph
- Vault / padlock / blurred “hidden” treatments (out of product)
- Day-resolution segments drawn on the density strip (calendar owns day pick)

## Object names

`navSidebar`, `homeButton`, `libraryButton`, `emptyState` (Home launchpad), `archiveBrowseFlick`, `archiveSidebar` (left-nav Browse block), `contextSidebarSearch`, `sidebarFolder_*`, `sidebarMoments`, `sidebarSimilar`, `sidebarKind_*`, `timelineHero`, `timelineYear_*`, `timelineMonth_*`, `archiveHeaderBand`, `memoryCalendar`, `calendarPrev`, `calendarNext`, `calendarGoHome`, `calendarTitle`, `calendarDay_*`, `fieldSections`, `fieldSection_*`, `stickyHeader`, `zeroResultFilter`, `fieldGrid`
