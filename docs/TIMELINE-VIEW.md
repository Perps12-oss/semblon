# Visual Memory Calendar — locked contract

**Status:** locked on `grok/visual-timeline`  
**Shell:** `semblon shell` → `Application` → `ShellBridge` / `Shell.qml`  
**Theme:** `semblon/native_shell/tokens.py` (no Quiet Studio hard-coded hex, no vault/padlock/blur)

## Product shape

Horizontal density timeline above a Monday–Sunday month calendar. Clear photo thumbnails on days that have media. Selecting a day filters the archive and uses the existing Field / Focus path. Not a separate product or security vault.

```text
+-- Search & global filters --------------------------------------------------+
+-- HERO DENSITY TIMELINE ----------------------------------------------------+
+-- MEMORY CALENDAR (month title · prev/next · Mon…Sun day tiles) ------------+
+-- FIELD (scoped media for the active filter) · Focus on open --------------+
+-- SIDEBAR: All/Photos/Videos · Folders · Similar · Moments -----------------+
+-- SLIM TIME RAIL -----------------------------------------------------------+
```

## Two independent states

| State | Meaning | Changes when |
|---|---|---|
| **Calendar month** (`calendarMonth`) | Which month grid is displayed | Prev/next, timeline year/month navigation |
| **Media scope** (`scopeKind` / `scopeLabel`) | Which media the Field shows | Day/month/year/range selection, clear |

Browsing the calendar month must **not** silently change the media scope.

## Selection / navigation

| Action | Behavior |
|---|---|
| Prev / next month | Shift `calendarMonth` only |
| Click day | `selectDay` (toggle: same day again → `clearScope`) |
| Click timeline year | Set calendar to that year’s newest month with media + `selectYear` |
| Click timeline month | Set calendar to that month + `selectMonth` |
| Drag timeline range | `selectRange` inclusive; calendar follows the range start month |
| Clear / Show everything | `clearScope`; calendar month unchanged |
| Hover day | After cancellable 150 ms: date, count, ≤3 thumbs |
| Empty day | Date only; no fabricated image or count |
| Empty library | Existing empty Stage |
| Zero-result scope | Message + Clear Filter |

## Day cells

- Clear thumbnails via `image://archive/`; deterministic first media id for the day
- Count = real `len(media_ids)`
- Outside-month days subdued (`inMonth=false`)
- Keyboard focus distinct from selected day
- Responsive cell size from available width (no fixed ultrawide-only layout)

## Keyboard

- Calendar: arrows move day focus; Enter selects; Escape clears scope or dismisses hover
- Timeline: Left/Right years; Enter selects; Escape clears

## Performance

- `timelineLoading` / calendar rebuild must not freeze the UI on large day maps
- Hover fetches cancel on leave/drag/scroll
- Measured on Windows (offscreen Qt, 2026-10-15 local): synthetic archive **360** dated media across **10** years → `calendar_month_cells` **1.4 ms**; `scope_ids` + `timeline_density` **51 ms**; shell open + first processEvents **605 ms**; calendar grid **42** cells for the active month. Re-run before merge if the data path changes.

## Deferred

- Pinch/zoom Years ↔ Months ↔ Days morph
- Vault / padlock / blurred “hidden” treatments (out of product)

## Object names

`timelineHero`, `timelineYear_*`, `timelineMonth_*`, `timelineRail`, `timelineRailYear_*`, `memoryCalendar`, `calendarPrev`, `calendarNext`, `calendarTitle`, `calendarDay_*`, `stickyHeader`, `zeroResultFilter`, `fieldGrid`, `archiveSidebar`
