# PERF P1 — native ARM64 measure

**Outcome (load path): still BLOCKED before folder timing** — `opencv_geometry500.dll` LoadLibrary hang (historical, unreproduced as fixed on this cloud VM). Emulation speedup vs P0 remains **unknown** (hypothesis only). Do **not** invent a ratio.

S1 / x64 correctness environment was **not** swapped and must not be silent-swapped.

| Field | Value |
|---|---|
| **Status 2026-09-22** | In-repo **lab/probe/docs COMPLETE**; native OpenCV **load still BLOCKED** pending owner Windows ARM64 evidence |
| Product `workers` default | **1** (unchanged until measured) |
| Identity | FaceKit only; `eps=0.40` frozen; no S1 cv2 swap |
| Cloud VM | Cannot LoadLibrary Windows ARM64 DLLs — PE inspect + fail-fast probes are portable |

## What this slice shipped in-repo (2026-09-22)

| Piece | Role |
|---|---|
| `semblon/pe_arch.py` | Portable PE COFF machine reader (`0xaa64` / `0x8664`) — no LoadLibrary |
| `semblon/opencv_probe.py` | Timed subprocess `import cv2` fail-fast; layout/PE inspect; identity firewall flags |
| `semblon lab opencv` | `--timeout`, `--pe PATH`, `--layout` `[--bin] [--pyd]` |
| `tools/_perf_p1_load_cv2.py` | Per-DLL timed LoadLibrary in child + `--pe-only` + JSON; env `SEMBLON_ARM64_OPENCV_*` |
| `tools/perf_p1_arm64_repro.ps1` | Owner Windows repro wrapper (isolated `.venv-arm64-perf`) |
| `tests/test_opencv_probe.py` | Portable tests (no ARM64 OpenCV required) |

## What worked before (isolated env — historical)

| Piece | Result |
|---|---|
| Venv | `.venv-arm64-perf/` (gitignored) from `Python314-arm64` |
| `process_arch` / `process_execution` | **arm64 / native** |
| numpy | `2.5.3` `win_arm64` |
| onnxruntime | `1.30.0` `cp314-win_arm64`; providers include `CPUExecutionProvider` |
| buffalo_l weights | unchanged on disk (same pack family as P0) |
| OpenCV pyd PE | `cv2.cp314-win_arm64.pyd` **0xaa64** (binary proven; not consumed by Semblon S1) |

## Blocker (unchanged until owner re-proves)

1. **Local OpenCV ARM64 build hangs on load**  
   - `cv2.cp314-win_arm64.pyd` PE `0xaa64` at `C:\Users\S8633\.arm64-build\build\lib\python3\Release\`.  
   - `ctypes.WinDLL(opencv_core500.dll)` succeeds (~0.01s).  
   - `ctypes.WinDLL(opencv_geometry500.dll)` **hangs** (kill after timeout).  
   - Therefore `import cv2` hangs; Semblon ingest cannot run natively.  

2. **No usable PyPI wheel for ARM64 OpenCV on this Python**  
   - `pip install opencv-python-headless` resolved to **sdist** and started a from-source wheel build.  
   - Aborted — not an authorized OpenCV rebuild / S1 path change.

## Not run (blocked on load)

- FACE-000 one-image native timing  
- Timed `process` of `E:\LIBRARY\Yandex.Disk\DCIMaw\me` to a **separate** store  
- P0/P1 ingest_s ratio  

## Must not (still)

- No silent S1 env swap  
- No eps / threshold retune  
- Do not fake native via x64 ORT  
- Do not mark **VERIFIED ON WINDOWS** without owner evidence  
- Do not invent native speedup numbers  

## Owner Windows ARM64 — exact commands

Repo root on the owner machine. Uses **isolated** `.venv-arm64-perf` only.

```text
REM 0) Optional: create lab venv once (not S1)
"C:\Users\S8633\AppData\Local\Programs\Python\Python314-arm64\python.exe" -m venv .venv-arm64-perf
.venv-arm64-perf\Scripts\python.exe -m pip install -U pip
.venv-arm64-perf\Scripts\python.exe -m pip install -e .

REM 1) PE layout only (safe; no LoadLibrary)
.venv-arm64-perf\Scripts\python.exe tools\_perf_p1_load_cv2.py --pe-only

REM or via lab:
.venv-arm64-perf\Scripts\python.exe -m semblon lab opencv --layout

REM 2) Timed per-DLL LoadLibrary (fail-fast; expect exit 2 if geometry still hangs)
.venv-arm64-perf\Scripts\python.exe tools\_perf_p1_load_cv2.py --timeout 20 --json

REM 3) Timed import probe (subprocess timeout; does not hang the parent forever)
.venv-arm64-perf\Scripts\python.exe -m semblon lab opencv --timeout 8

REM 4) One-shot wrapper
powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_p1_arm64_repro.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_p1_arm64_repro.ps1 -PeOnly
```

Env overrides if build paths differ:

```text
set SEMBLON_ARM64_OPENCV_BIN=C:\Users\S8633\.arm64-build\build\bin\Release
set SEMBLON_ARM64_OPENCV_PYD=C:\Users\S8633\.arm64-build\build\lib\python3\Release\cv2.cp314-win_arm64.pyd
```

### If load succeeds (only then)

Record to a **separate** store (never overwrite S1 golden). Compare wall-clock to `docs/PERF-P0-BASELINE.md` (`ingest_s=1299.3`, 221 files). Update this file + `docs/runtime.md` with measured numbers — do not invent them.

```text
.venv-arm64-perf\Scripts\python.exe -m semblon lab profile --image "<one.jpg>" --out docs\runtime-arm64-p1.md
.venv-arm64-perf\Scripts\python.exe -m semblon process --folder "E:\LIBRARY\Yandex.Disk\DCIMaw\me" --store "<separate-p1-store.sqlite>" --workers 1
```

### Recovery if geometry still hangs

1. Confirm PE still `0xaa64` via `--pe-only` / `lab opencv --layout`.  
2. Rebuild OpenCV geometry module / different OpenCV config, **or** obtain a real `win_arm64` wheel (do not accept x64 wheel).  
3. Re-run timed load; keep S1 x64 env untouched.  
4. Abort any `pip install opencv-python-headless` that falls back to sdist source build unless explicitly authorized as a lab rebuild.

## Related

- P0 baseline: `docs/PERF-P0-BASELINE.md`  
- Runtime record: `docs/runtime.md`  
- Completion matrix: `docs/COMPLETION-MATRIX.md`  
- SEM-ARCH G.4: `docs/SEM-ARCH-V1.4.md`  
