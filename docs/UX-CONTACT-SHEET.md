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
