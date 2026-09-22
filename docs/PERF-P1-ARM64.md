# PERF P1 — native ARM64 measure (2026-09-17)

**Outcome: BLOCKED before folder timing** (OpenCV ARM64 load hang). Emulation speedup vs P0 remains **unknown** (hypothesis only).  
S1 / x64 correctness environment was **not** swapped.

**Status 2026-09-20:** This file is **historical evidence** of the native ARM64 measurement gap. It is **not** a stop-work order on ingest pipeline work (bounded hash workers, skip-before-embed, streamed video, batched SQLite commits, EP recording). Do not silently swap S1's x64 `cv2`.

**Status 2026-09-21 (shakedown slice 5):** ARM64 OpenCV ingest is **still BLOCKED**. No new native load proof. Do not invent an emulation speedup. Product `workers` default remains **1**. Provider/workers harnesses are usable as dry-run / listing tools (`docs/PERF-WORKERS-HARNESS.md`, `docs/PERF-PROVIDER-HARNESS.md`).

## What worked (isolated env)

| Piece | Result |
|---|---|
| Venv | `.venv-arm64-perf/` (gitignored) from `Python314-arm64` |
| `process_arch` / `process_execution` | **arm64 / native** |
| numpy | `2.5.3` `win_arm64` |
| onnxruntime | `1.30.0` `cp314-win_arm64`; providers include `CPUExecutionProvider` |
| buffalo_l weights | unchanged on disk (same pack family as P0) |

## Blocker

1. **Local OpenCV ARM64 build hangs on load**  
   - `cv2.cp314-win_arm64.pyd` PE `0xaa64` still present (`C:\Users\S8633\.arm64-build\build\lib\python3\Release\`).  
   - `ctypes.WinDLL(opencv_core500.dll)` succeeds (~0.01s).  
   - `ctypes.WinDLL(opencv_geometry500.dll)` **hangs** (killed after 20–45s).  
   - Therefore `import cv2` hangs; Semblon ingest cannot run.  
   - Repro: `tools/_perf_p1_load_cv2.py` under `.venv-arm64-perf\Scripts\python.exe`.

2. **No usable PyPI wheel for ARM64 OpenCV on this Python**  
   - `pip install opencv-python-headless` resolved to **sdist** `opencv_python_headless-5.0.0.93.tar.gz` and started a from-source wheel build.  
   - Aborted — not an authorized OpenCV rebuild / S1 path change.

## Not run (blocked)

- FACE-000 one-image native timing  
- Timed `process` of `E:\LIBRARY\Yandex.Disk\DCIMaw\me` to a separate store  
- P0/P1 ingest_s ratio  

## Must not (still)

- No silent S1 env swap  
- No eps / threshold retune  
- Did not fake native via x64 ORT  

## Next for the native measure

Fix or replace ARM64 `opencv_geometry` load path (rebuild geometry module, different OpenCV config, or a real `win_arm64` wheel), then re-run one-image + same 221-file folder to a **separate** store and record ratio vs `docs/PERF-P0-BASELINE.md`.
