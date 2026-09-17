# S8 toolkit spike

PySide6 + Qt Quick shell slice. Calls `review_ui` → `review.py`. **Not** full Canvas. Does **not** replace `semblon review-ui`.

```text
py -3 tools/s8_toolkit_spike/main.py
py -3 tools/s8_toolkit_spike/main.py --store %LOCALAPPDATA%\Semblon\store.sqlite
py -3 tools/s8_toolkit_spike/main.py --store %LOCALAPPDATA%\Semblon\store.sqlite --run <run_id>
```

Requires optional `PySide6` (`pip install .[gui]` or `pip install PySide6`). Core Semblon stays headless without it.

Review: board list, thumbs, Name / Merge / Split / Ignore / Note / Reload. Ctrl+click a second cluster as merge donor.
