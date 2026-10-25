# Contact Sheet / Light Table

The Semblon desktop shell (PySide6 + QML, `semblon shell`) is one zoomable **Roll** of every photo.

- **Roll**: all photos on one canvas, newest first. Pinch, Ctrl+scroll or Ctrl +/- to zoom from months to single frames.
- **Film edge**: the strip on the right shows years sized by how many photos each holds. Click or drag to travel through time.
- **Light Table**: the bar at the bottom has four verbs: Find a moment, Find a person, Find a detail, Tidy up. Ctrl+K opens everything else.
- **Picture view**: opens over the Roll. Left/Right move between photos; Esc returns.
- **Find a detail**: point at part of a picture and Semblon finds it again elsewhere. Matches can be shown on the Roll.
- **People**: faces are laid out as prints on a table. A group is not a person until you name it. "Not sure" is always allowed.
- **First run**: one drop canvas, one "Add a folder" action, real progress, and "Pick up where it left off".

Fonts (Fraunces, Inter; OFL) are bundled in `semblon/native_shell/fonts/`. Colours live only in `qml/Theme.qml`. Daylight and reduced-motion follow the system.

Screenshots: `docs/evidence/contact-sheet/`.

## Polish pass

- First run: the whole canvas is the drop zone (dashed amber edge, lights up while a folder is dragged over). One primary action, "Choose a folder"; the top-right "Add a folder" appears only once photos exist. The four verbs are dimmed with "Add photos first" but stay focusable. Ctrl+K lists only actions that work now.
- Roll: month header is its own sticky band (title, count on its own line, soft fade). Day breaks carry a frame-number tag (e.g. SAT 14 SEP) with small gutters between thumbnails. The scrubber is higher-contrast, shows the current year and month, and gives hover and drag feedback; the grid fills the width beside it.
- Bottom bar: the Roll reserves bar height plus a margin at the end of a scroll; the bar shrinks and fades while scrolling and returns when scrolling stops or the pointer nears it. "Everything" is now "More... Ctrl+K" (Cmd+K on macOS).
- Language: install and download dialogs describe what becomes possible ("Get finding-by-look ready"). A test scans user-visible strings for banned engine words.
- Keyboard: loupe (L, arrows move, Shift+arrows resize, Enter finds) and People (S same as the next group, X send away, Tab to a "Same as" stack then Enter).

## Fix-up pass

- The Roll is a sectioned list: a month row, then one row per day (frame tag such as "SAT 8 FEB" and that day's count), then that day's photos. Every photo sits under its own month and day. Counts are per month and per day.
- The sticky band names the month under it. A scrubber landing is only honoured while that month's header is still at the band.
- The scrubber has even month slots, density as a small bar, a marker on the left rail, and lands exactly on the month header.
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
- Photo view: Back, Previous, Next, Find a detail, plus a More menu. No debug text.
- Tidy up is a real review view (Keep this one, plain confirm, Recycle Bin).
- Plain wording for the preflight confirm; both add-on sheets show their size.

