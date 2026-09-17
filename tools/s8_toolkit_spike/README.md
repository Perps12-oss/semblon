# S8 toolkit spike

Throwaway presentation proof. **Not** product GUI. **Not** S7.

```text
py -3 tools/s8_toolkit_spike/main.py
py -3 tools/s8_toolkit_spike/main.py --store %LOCALAPPDATA%\Semblon\store.sqlite
```

Requires optional `PySide6` (`pip install PySide6`). Core Semblon stays headless without it.

Does not Name/Merge/Split. Read-only `run_id` / counts / image paths from SQLite.
