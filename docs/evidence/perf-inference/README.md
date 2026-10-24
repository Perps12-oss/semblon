# Evidence — face inference backend investigation

Generated 2026-10-25 (Europe/London) on Linux x64 native cloud agent.

| File | Content |
|---|---|
| `backend-bench.json` | Decode / detect / align / embed latencies for `opencv_dnn` vs `ort_yunet_sface` |
| `identity-safety.json` | Detection P/R, IoU, embedding cosine, retrieval proxy |
| `resolution-sweep.json` | YuNet long-side caps vs face-count recall |

Corpus: `../perf-inference-48still/` (lab stand-in). Models used via `SEMBLON_PERF_FACE_PACK` (BYO; not committed — `*.onnx` gitignored).

Re-run: see `docs/PERF-INFERENCE-BACKENDS.md`.
