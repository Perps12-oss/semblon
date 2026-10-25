# Evidence — face inference backend investigation

## Linux lab (2026-10-25 Europe/London)

| File | Content |
|---|---|
| `backend-bench.json` | Decode / detect / align / embed latencies for `opencv_dnn` vs `ort_yunet_sface` |
| `identity-safety.json` | Detection P/R, IoU, embedding cosine, retrieval proxy |
| `resolution-sweep.json` | YuNet long-side caps vs face-count recall |

Corpus: `../perf-inference-48still/` (**lab stand-in**). Not a PERF-6 PASS.

## PERF-6 owner ARM64 (PENDING measured files)

Run on SKY:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_inference_owner_arm64.ps1 -Corpus "<owner-photographic-48still>"
```

Expected outputs (not present until owner run):

- `owner-arm64-runtime-A.json` / `owner-arm64-runtime-B.json`
- `owner-arm64-bench-A.json` / `owner-arm64-bench-B.json`
- `owner-arm64-identity-safety.json`
- `owner-arm64-decision.json`

Models: BYO via `SEMBLON_PERF_FACE_PACK` (`*.onnx` gitignored).
