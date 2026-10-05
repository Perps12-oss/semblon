# S8 toolkit spike

**Research only. Not the production shell.** Production UI is `semblon shell` (PySide6 → Application). See `docs/ARCHITECTURE.md`. Do not promote this spike into the product.

PySide6 + Qt Quick research slice. Calls `review_ui` → `review.py`. **Not** full Canvas. Does **not** replace the legacy `semblon review-ui`, and it is not a second production architecture.

```text
py -3 tools/s8_toolkit_spike/main.py
py -3 tools/s8_toolkit_spike/main.py --store %LOCALAPPDATA%\Semblon\store.sqlite
py -3 tools/s8_toolkit_spike/main.py --store %LOCALAPPDATA%\Semblon\store.sqlite --run <run_id>
```

Requires optional `PySide6` (`pip install .[gui]` or `pip install PySide6`). Core Semblon stays headless without it.

Review: board list, thumbs, Name / Merge / Split / Ignore / Note / Reload. Ctrl+click a second cluster as merge donor.
