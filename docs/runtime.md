# Runtime record (FACE-000 output)

Fill one document (or one section) per machine/execution mode.
Never write execution: native for an x64 process on ARM64 Windows.

```yaml
recorded_at:
hostname:
os: windows
os_version:
arch: x64          # or arm64
execution: native  # or emulated
python:
python_arch:
ort_package: onnxruntime
ort_version:
insightface_version:
pack_family: insightface/buffalo_l
pack_id:           # family + versions + weight sha256 — required
det_size: [640, 640]
device: cpu
device_name:
workers: 1
embed_batch: 1
peak_rss_mb:
model_load_s:
one_image:
  path:
  decode_ms:
  detect_ms:
  embed_ms:
  faces:
notes:
```

Required FACE-000 rows:
1. Windows x64 native
2. Windows ARM64 native, or ARM64 native failed + emulated row with the failure in notes
