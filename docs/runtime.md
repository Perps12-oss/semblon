# Runtime record (FACE-000)

One section per OS / process-arch / execution. x64 Python on ARM64 Windows is emulated, never native.

Required rows:
1. Windows x64 native — needs an x64 host (not x64-on-ARM64). **Not this host.**
2. Windows ARM64 native, or native failed + emulated row with the failure in notes. **Native failed; emulated row below.**

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
  "embed_batch": 1,
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

## windows arm64 native-failed

```json
{
  "recorded_at": "2026-09-15T16:40:00+00:00",
  "hostname": "SKY",
  "os": "windows",
  "os_version": "10.0.26200",
  "arch": "arm64",
  "execution": "native-failed",
  "python": "3.14.7",
  "python_path": "C:\\Users\\S8633\\AppData\\Local\\Programs\\Python\\Python314-arm64\\python.exe",
  "python_arch": "ARM64",
  "ort_package": "onnxruntime",
  "ort_wheel": "onnxruntime-1.30.0-cp314-cp314-win_arm64.whl (available, not fully installed)",
  "opencv": "no cp314 win_arm64 wheel; 5.0.0.93 and 4.14.0.94 are sdists; CMake/VS missing so the sdist cannot build",
  "one_image": null,
  "notes": "ARM64 CPython is installed. Identity path did not run native: OpenCV has no wheel and cannot be built here. Do not label this host native until opencv+insightface import on this interpreter."
}
```

## windows x64 native

```json
{
  "arch": "x64",
  "execution": "native",
  "status": "not_this_host",
  "notes": "This OS is ARM64 Windows. x64-on-ARM64 is emulated (see windows x64 emulated). Fill this row on a real x64 machine with x64 Python + x64 ONNX Runtime."
}
```
