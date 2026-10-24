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
