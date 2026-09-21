# S8 toolkit investigation

**Status:** dump-gate vertical wired (`tools/s8_toolkit_spike/`). Presentation + Name/Merge/Split/Ignore/Note via `review_ui` → `review.py`. **Not** full AppShell / Intelligence Canvas. Does **not** replace tkinter `review-ui`.  
**Planned work:** `docs/SEM-ARCH.md`. This spike is not the plan.

## Recon (what already exists)

| Piece | Location | Notes |
|---|---|---|
| CLI / bootstrap | `semblon/cli.py` | `semblon = semblon.cli:main` |
| Process events | `semblon/progress.py` `on_event` | ingest/process; GUI must not own this |
| Review mutations | `semblon/review.py` | Name/Merge/Split/Ignore/Note |
| Shipping review GUI | `semblon/review_ui.py` | **stdlib tkinter** over `review.py` + RO `load_board()` |
| Store | `%LOCALAPPDATA%\Semblon\store.sqlite` | `process.default_store_path()` |
| Stats | `semblon/stats.py` | read-only; pulls observatory |
| CustomTkinter / Electron / FastAPI / web | — | already **REJECT** |
| Full AppShell | design only | blueprint §S8 |

`review-ui` stays the shipping vertical. This spike proves the PySide6 path can call the same domain ops.

Attachment point: presentation process reads SQLite RO via `load_board`, mutations only through `apply_*`. No FaceKit in the GUI process.

## Spike (now: review vertical)

```text
Python core (unchanged)
        │  load_board / apply_* (review_ui → review.py)
        v
tools/s8_toolkit_spike  (PySide6 + Qt Quick)
        │
   WindowsBackdropAdapter  (DWM only here)
        v
HWND → DWM → Mica / Acrylic / solid
```

Run:

```text
py -3 tools/s8_toolkit_spike/main.py
py -3 tools/s8_toolkit_spike/main.py --store %LOCALAPPDATA%\Semblon\store.sqlite --run <run_id>
```

Optional extra: `pip install .[gui]` → PySide6. Core install remains headless.

Review workspace: board list + thumbs. Inspector: Name / Note / Ignore / Merge (Ctrl+click donor) / Split first face / Reload. Other nav sections are stubs.

## KEEP / DEFER / REJECT

| Option | Verb | Why |
|---|---|---|
| Tk **review-ui** vertical | **KEEP** | Shipped; proves GUI → `review.py` → store |
| Tk as **full AppShell** / glass / Mica | **DEFER / likely REJECT** | No DWM composition, weak animation, fights the visual language |
| **PySide6 + Qt Quick/QML** as S8 shell foundation | **KEEP (candidate → dump-gate path)** | Review actions wired; full Canvas / Library / Search still deferred |
| WinUI 3 / .NET | **DEFER** | Max Windows 11 fidelity, but Python↔WinRT boundary; no blocker found that forces it |
| Electron / Tauri / web | **REJECT** | Already rejected; still rejected |
| CustomTkinter | **REJECT** | Already rejected |

Owner dump-gate: open the shell on Windows 11, confirm Mica-or-fallback, Name one cluster, reopen / Reload, decision still there. Full product shell (Canvas, search, identify inbox) waits for roadmap Phase 3.

## Machine notes (2026-09-17)

- Interpreter used: CPython 3.14.4 **AMD64** (`pythoncore-3.14-64`) — x64 on ARM64 SKY.
- PySide6 **6.11.1** already installed on that interpreter.
- Native ARM64 Python + PySide6 **not** measured in this spike (PERF P1 OpenCV hang is a different env). Record separately if native GUI matters.
- Backdrop: Win11 build ≥ 22621 → `DWMWA_SYSTEMBACKDROP_TYPE` Mica; ≥ 22000 Mica effect; else solid. QML never calls DWM.

## License

Qt / PySide6 is **LGPL**. Local-only Semblon can dynamically link. Recorded in `docs/licenses.md`. Do not statically link Qt into a closed binary without a licence pass.

## Must not

- Import this package from ingest / cluster / identify / review.
- Copy Name/Merge/Split into QML.
- Grow this spike into Intelligence Canvas or S7 UI.
- Retune `eps`.
- Replace `semblon review-ui` until dump-gate + product decision say so.
- Revive a second product shell beside tk Home. Product Home is `semblon home` (tk). User-facing progress copy lives in `semblon.ui_copy`.
