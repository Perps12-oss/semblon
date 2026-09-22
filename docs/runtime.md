# Runtime record (FACE-000)

One section per OS / process-arch / execution. x64 Python on ARM64 Windows is emulated, never native.

Required rows:
1. Windows x64 native — needs a genuine x64 Windows PC (not x64-on-ARM64, not a VM used as native evidence). **Unverified. Environment-dependent gap. Not an ARM64 implementation failure.**
2. Windows ARM64 native OpenCV **binary** — **closed 2026-09-16** (`cv2.cp314-win_arm64.pyd`, PE `0xaa64`). Semblon has **not** been switched onto that build. S1 correctness environment is unchanged.

Do not treat “ARM64 capable host” as native OpenCV. The binding itself must be `ARM64` (`0xaa64`).

## windows x64 emulated

```json
{
  "recorded_at": "2026-09-15T16:37:56.845860+00:00",
  "hostname": "SKY",
  "os": "windows",
  "os_version": "10.0.26200",
  "arch": "x64",
  "execution": "emulated",
  "python": "3.14.4",
  "python_arch": "64bit",
  "ort_package": "onnxruntime",
  "ort_version": "1.30.0",
  "insightface_version": "2.0",
  "pack_family": "insightface/buffalo_l",
  "pack_id": "insightface/buffalo_l@2.0/adapter-1/sha256:20a9264f823c3c3c",
  "weight_files": {
    "1k3d68.onnx": "df5c06b8a0c12e422b2ed8947b8869faa4105387f199c477af038aa01f9a45cc",
    "2d106det.onnx": "f001b856447c413801ef5c42091ed0cd516fcd21f2d6b79635b1e733a7109dbf",
    "det_10g.onnx": "5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",
    "genderage.onnx": "4fde69b1c810857b88c64a335084f1c3fe8f01246c9a191b48c7bb756d6652fb",
    "w600k_r50.onnx": "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43"
  },
  "det_size": [640, 640],
  "device": "cpu",
  "device_name": null,
  "workers": 1,
  "peak_rss_mb": 825.1,
  "model_load_s": 12.771,
  "software_version": "1.1.0",
  "one_image": {
    "path": "C:\\Users\\S8633\\OneDrive\\Desktop\\test\\20260427_183702.jpg",
    "decode_ms": 448.8,
    "detect_embed_ms": 9922.03,
    "faces": 2,
    "dims": [512, 512]
  },
  "notes": "FACE-000 probe. detect_ms/embed_ms not split; see detect_embed_ms. This host OS is ARM64; x64 CPython is emulated. Windows x64 native requires a different machine."
}
```

## windows arm64 opencv binary (proven; not consumed by Semblon)

```json
{
  "recorded_at": "2026-09-16",
  "hostname": "SKY",
  "os": "windows",
  "os_version": "10.0.26200",
  "arch": "arm64",
  "execution": "native",
  "claim": "OpenCV Python binding binary is ARM64. Semblon identity path was not re-run on this build.",
  "python": "3.14.7",
  "python_path": "C:\\Users\\S8633\\AppData\\Local\\Programs\\Python\\Python314-arm64\\python.exe",
  "python_arch": "ARM64",
  "python_version_tag": "MSC v.1944 64 bit (ARM64)",
  "opencv_source": "C:\\Users\\S8633\\.arm64-build\\opencv (OpenCV 5.0.0)",
  "opencv_pyd": "C:\\Users\\S8633\\.arm64-build\\build\\lib\\python3\\Release\\cv2.cp314-win_arm64.pyd",
  "opencv_pyd_pe_machine": "0xaa64",
  "opencv_pyd_bytes": 5408768,
  "opencv_dnn": "disabled (MLAS linker failures); acceptable because ONNX Runtime does inference",
  "numpy": "2.5.3 native ARM64",
  "vs": "Visual Studio 2026 Community, ARM64 MSVC",
  "cmake_python": "explicit ARM64 python.exe / python314.lib / include (x64 Python caused LNK4272)",
  "semblon_consumes_this_pyd": false,
  "arm64_python_import_cv2": "ModuleNotFoundError: no cv2 in Python314-arm64 site-packages (checked 2026-09-16; pyd not installed)",
  "current_semblon_cv2": {
    "python": "C:\\Users\\S8633\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe",
    "process_arch": "x64",
    "platform_machine": "ARM64",
    "cv2_version": "5.0.0",
    "cv2_pyd_pe_machine": "0x8664"
  },
  "notes": "Binary proof of native ARM64 OpenCV only. Do not treat Semblon as native-OpenCV until this pyd is explicitly adopted. Do not change the S1 correctness environment to consume it unless decided separately."
}
```

## windows x64 native

```json
{
  "arch": "x64",
  "execution": "native",
  "status": "unverified",
  "notes": "No genuine x64 Windows PC in this environment. Do not use x64-on-ARM64 or a VM as native x64 evidence. This is an environment-dependent UNVERIFIED gap, not a failure of the ARM64 OpenCV work."
}
```

## folder timing P0 (x64 emulated — performance baseline)

Not FACE-000. Not an S1 correctness gate. Full table: `docs/PERF-P0-BASELINE.md`.

```json
{
  "recorded_at": "2026-09-17",
  "hostname": "SKY",
  "os": "windows",
  "os_version": "10.0.26200",
  "arch": "x64",
  "execution": "emulated",
  "run_id": "20260917T021045Z-48095f25",
  "folder": "E:\\\\LIBRARY\\\\Yandex.Disk\\\\DCIMaw\\\\me",
  "files": 221,
  "faces": 961,
  "ok": 393,
  "low_quality": 530,
  "rejected": 38,
  "pack_id": "insightface/buffalo_l@2.0/adapter-1/sha256:20a9264f823c3c3c",
  "device": "cpu",
  "workers": 1,
  "det_size": [640, 640],
  "model_load_s": 4.8,
  "ingest_s": 1299.3,
  "notes": "PERF P0 baseline. Model load is not the bottleneck. Do not retune eps from this run. Native ARM64 speedup is unmeasured (PERF P1 OpenCV hang — docs/PERF-P1-ARM64.md). P1 is a native-measure gap, not an ingest stop-work."
}
```

## windows arm64 native (PERF P1 — native measure gap)

Semblon identity path **not** timed natively. Isolated env proved ARM64 Python + ORT; OpenCV load hangs. Full write-up: `docs/PERF-P1-ARM64.md`. Does not block ingest pipeline engineering on the S1 (x64) path.

In-repo (2026-09-22): portable PE inspect + fail-fast import/DLL probes (`semblon lab opencv --layout` / `--pe`, `tools/_perf_p1_load_cv2.py`, `tools/perf_p1_arm64_repro.ps1`). **Not** VERIFIED ON WINDOWS; do not invent speedup.

```json
{
  "recorded_at": "2026-09-17",
  "hostname": "SKY",
  "os": "windows",
  "os_version": "10.0.26200",
  "arch": "arm64",
  "execution": "native",
  "status": "blocked",
  "venv": ".venv-arm64-perf",
  "python": "3.14.7",
  "onnxruntime": "1.30.0-cp314-win_arm64",
  "providers": ["AzureExecutionProvider", "CPUExecutionProvider"],
  "numpy": "2.5.3-win_arm64",
  "opencv_pyd_pe": "0xaa64",
  "blocker": "LoadLibrary opencv_geometry500.dll hangs after opencv_core500.dll loads; import cv2 unusable. No win_arm64 opencv-python-headless wheel (pip fell back to sdist build; aborted).",
  "folder_timing": null,
  "notes": "Do not claim native Semblon ingest. Do not swap S1. Emulation cost vs P0 remains unknown."
}
```
