# Contact Sheet / Light Table

The Semblon desktop shell (PySide6 + QML, `semblon shell`) is one zoomable **Roll** of every photo.

- **Roll**: all photos on one canvas, newest first. Pinch, Ctrl+scroll or Ctrl +/- to zoom from months to single frames.
- **Film edge**: the strip on the right is a chronological navigation instrument. Calendar years keep uniform time (including empty years as gaps). Populated years are the only navigable detents. Click or drag to travel through time; the content Roll owns scrolling and animation.
- **Light Table**: the bar at the bottom has four verbs: Find by date, Find a person, Find by description, Tidy up copies. Ctrl+K opens everything else.
- **Picture view**: opens over the Roll. Left/Right move between photos; Esc returns.
- **Find this part again**: point at part of a picture and Semblon finds it again elsewhere. Matches can be shown on the Roll.
- **People**: faces are laid out as prints on a table. A group is not a person until you name it. "Not sure" is always allowed.
- **First run**: one drop canvas, one "Add a folder" action, real progress, and "Pick up where it left off".

Fonts (Fraunces, Inter; OFL) are bundled in `semblon/native_shell/fonts/`. Colours live only in `qml/Theme.qml`. Daylight and reduced-motion follow the system.

Screenshots: `docs/evidence/contact-sheet/`.

## Polish pass

- First run: the whole canvas is the drop zone (dashed amber edge, lights up while a folder is dragged over). One primary action, "Choose a folder"; the top-right "Add a folder" appears only once photos exist. The four verbs are dimmed with "Add photos first" but stay focusable. Ctrl+K lists only actions that work now.
- Roll: month header is its own sticky band (title, count on its own line, soft fade). Day breaks carry a frame-number tag (e.g. SAT 14 SEP) with small gutters between thumbnails. The time strip shows a passive viewport segment (amber rail, soft range wash, end whiskers; readable minimum height in dense years) and a destination year pill while dragging; the grid fills the width beside it.
- Bottom bar: the Roll reserves bar height plus a margin at the end of a scroll; the bar shrinks and fades while scrolling and returns when scrolling stops or the pointer nears it. "Everything" is now "More... Ctrl+K" (Cmd+K on macOS).
- Language: install and download dialogs describe what becomes possible ("Get finding-by-look ready"). A test scans user-visible strings for banned engine words.
- Keyboard: loupe (L, arrows move, Shift+arrows resize, Enter finds) and People (S same as the next group, X send away, Tab to a "Same as" stack then Enter).

## Fix-up pass

- The Roll is a sectioned list: a month row, then one row per day (frame tag such as "SAT 8 FEB" and that day's count), then that day's photos. Every photo sits under its own month and day. Counts are per month and per day.
- The sticky band names the month under it. A scrubber landing is only honoured while that month's header is still at the band.
- The time strip uses a uniform calendar-year scale (empty years keep chronological space but are not destinations). Landings resolve to populated years via content geometry (`offset_for_year`), never by inventing photos in empty years.
- Gutter between pictures is `Theme.gutter` (5px) at every size.
- Add a folder and Settings live in the sticky band, never over pictures.
- Pictures: lift and amber hairline on hover, date and time chip, selected state (Ctrl/Shift click, keyboard). Grid centre-crops; the photo view shows the whole picture.
- Every question and install runs in one in-theme sheet (verb buttons, size and privacy lines, inline progress, search re-runs on its own). No native pop-ups remain; only the system folder picker is native.
- Bottom bar: the active verb shows a pressed state; every verb has a visible focus ring. The edge scrubber hides in the picture and People views.
- Evidence: `docs/evidence/contact-sheet/fx-*.png` (after) and `before-fixup/` (before).
## Fix-up pass 2

- Roll uses exact row geometry; header and scrubber always name the month at the top (one header only).
- Days use the local time zone (DST-aware) via semblon/clock.py.
- People: fanned face stacks, one searchable Same as... picker, same-name prompt, no joining two named people.
- Photo view: Back, Previous, Next, Find this part again, plus a More menu. No debug text.
- Tidy up copies is a real review view (Keep this one, plain confirm, Recycle Bin).
- Plain wording for the preflight confirm; both add-on sheets show their size.


## Temporal navigation (Phase 1)

Calendar time and Roll `contentY` are different metric spaces. They meet only through:

- `time_for_offset(content_offset)` — maps dated content position to chronological time (monotonic over dated content; empty years keep duration on the strip; undated is an explicit result).
- `offset_for_year(year)` — maps a populated year to its content destination, or `None` for empty years (never silent clamp).

Implementation: `semblon/native_shell/temporal_geometry.py`, Roll `navigateToOffset` / `redirectNavigation` / `cancelNavigation`, and `qml/Scrubber.qml` (Idle → Armed → Tracking → Settling). Undated occupies a terminal zone **below** the dated calendar track so it cannot rescale year positions. Phase 1 navigation stays as landed.

## Phase 2 — Intelligent photographic ribbon & hybrid temporal magnification

Phase 2 makes the timeline useful for **understanding** the archive, not only navigating it. The user can recognise periods with photographs, dense vs sparse stretches, and gaps; get a visual impression of a period; magnify year → month → populated days; inspect a few representative actual photographs; and navigate to a selected period deliberately.

The ribbon must remain understandable with 10,000 photographs in two months, and with archives of hundreds of thousands of photographs. It must never become an overcrowded miniature photo gallery.

### Founding principles

1. **The timeline's chronological scale remains independent of photograph density.** Density changes the visual representation, not the calendar geometry.
2. **Hovering changes inspection detail, not archive position.** Hover must never move `contentY` or invoke navigate / redirect / cancel.
3. Magnification is a **local temporal lens** (hybrid year → month → day), not a global rescaling of the strip.

Phase 1 navigation (Idle → Armed → Tracking → Settling, destination pill, content-owned scrub) stays unchanged.

### Acceptance criterion (required)

**10,000 photographs taken in July and August must produce a visually coherent representation of those two months, not 10,000 competing visual marks.**

Visual mark budget:

| Scale | Idle / overview | Under hover magnification |
|---|---|---|
| Years | One coherent cell per populated year (`O(years)`) | — |
| Months | — | One coherent cell per populated month in the expanded year (`≤ 12`) |
| Days | — | One coherent cell per populated day in the expanded month (never one mark per photo) |
| Preview panel | — | At most four representative photographs for the focused period |

A month or day with thousands of photographs is still **one** cell (aggregated colour from a capped deterministic sample). Empty calendar years remain gaps with no fill. A naive mosaic that draws one thumb (or mark) per photograph is out of Phase 2.

### Contextual photographic preview

While hovering a magnified period, a contextual panel beside the strip shows up to four deterministic representative thumbnails for that period (day if resolved, else month, else year). Sources are existing thumb caches only (`thumb_on_disk` / `read_cached_thumb`, then `image://archive/s/…`). Cold originals are skipped — missing cache → colour/placeholder fallback; no synchronous full-archive decode, no new indexing or identity work.

This preview panel is Phase 2. Phase 3's advanced loupe (richer inspection chrome) is not this slice.

### Interaction (three actions)

| Action | Behaviour |
|---|---|
| **Hover** | Inspect a finer temporal scale (year → month → day) and the contextual photo preview. **Never moves the archive.** |
| **Click** | Navigate to that period via existing content-owned navigate. |
| **Click and drag** | Scrub through populated periods using **unchanged Phase 1** Idle → Armed → Tracking → Settling. |

### Implementation

- Sampling / cells: `semblon/native_shell/temporal_ribbon.py` (`year_cells`, `month_cells_for_year`, `day_cells_for_month`).
- Cache gate: `thumb_on_disk` / `read_cached_thumb` in `images.py` — ribbon colour and preview ids never decode originals.
- Bridge: `ribbonYearCells` / `ribbonMonthCells` / `ribbonDayCells` (cached thumbs only; `hasTiny` + filtered `sampleIds`).
- Strip: `qml/Scrubber.qml` — year colour washes; local lens + preview panel (`image://archive/s/…`); hover subdivides the hovered year slot without rescaling neighbours; click uses the captured period; drag is unchanged Phase 1.

## Capture dates and the Recycle Bin

- Day and month use the camera's capture date (DateTimeOriginal, with its offset when present) read from the file; the file's saved time is the fallback. Nothing is stored: the schema has no capture-date column, so it is read at browse time and cached in memory. A persisted date would need a new media column plus a one-time backfill at ingest; not built.
- Binning copies in Tidy up copies removes them from the library at once (semblon/forget.py). Restoring from the Bin and rescanning the folder adds them back.

