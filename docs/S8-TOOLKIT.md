# S8 toolkit investigation

**Status:** spike only (`tools/s8_toolkit_spike/`). Not product GUI. Not S7.  
**Branch intent:** `grok/S8-toolkit` — do not mix with S7a (PR #22) or review-ui/PERF (PR #23).

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

`review-ui` stays the shipping vertical. This spike does **not** replace it.

Attachment point: a presentation process that reads SQLite RO and later will call `review.py`. No FaceKit in the GUI process required for this spike.

## Spike

```text
Python core (unchanged)
        │  RO snapshot (run_id, counts, image URIs)
        v
tools/s8_toolkit_spike  (PySide6 + Qt Quick)
        │
   WindowsBackdropAdapter  (DWM only here)
        v
HWND → DWM → Mica / Acrylic / solid
```

Run: `py -3 tools/s8_toolkit_spike/main.py`

Optional extra: `pip install .[gui]` → PySide6. Core install remains headless.

## KEEP / DEFER / REJECT

| Option | Verb | Why |
|---|---|---|
| Tk **review-ui** vertical | **KEEP** | Shipped; proves GUI → `review.py` → store |
| Tk as **full AppShell** / glass / Mica | **DEFER / likely REJECT** | No DWM composition, weak animation, fights the visual language |
| **PySide6 + Qt Quick/QML** as S8 shell foundation | **KEEP (candidate)** | In-process Python, ARM64/x64 wheels exist on this SKY x64-emulated 3.14, HWND + DWM adapter isolated, GPU scene graph, image-heavy ListView, custom chrome |
| WinUI 3 / .NET | **DEFER** | Max Windows 11 fidelity, but Python↔WinRT boundary; no blocker found that forces it |
| Electron / Tauri / web | **REJECT** | Already rejected; still rejected |
| CustomTkinter | **REJECT** | Already rejected |

PySide6 is **not locked as product code** until a dump-gate: owner opens the spike on Windows 11, confirms Mica-or-fallback, and agrees the surfaces feel capable. Then a later ticket hosts review actions through `review.py`.

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
