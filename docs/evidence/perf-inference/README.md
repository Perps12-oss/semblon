# Evidence — face inference backend investigation

## Linux lab (2026-10-25 Europe/London)

| File | Content |
|---|---|
| `backend-bench.json` | Decode / detect / align / embed latencies for `opencv_dnn` vs `ort_yunet_sface` |
| `identity-safety.json` | Detection P/R, IoU, embedding cosine, retrieval proxy |
| `resolution-sweep.json` | YuNet long-side caps vs face-count recall |

Corpus: `../perf-inference-48still/` (**lab stand-in**). Not a PERF-6 PASS.

## PERF-6 owner ARM64 — **BLOCKED** / **PENDING** measured files

| Field | Value |
|---|---|
| Harness tip | `2db9af1` on `cursor/native-face-inference-perf-9497` (PR #188) |
| Lab numerical agreement | PASS (not a throughput win) |
| Measured owner A/B | **Absent** — do not invent native timings |
| SKY worker (2026-10-25) | Connected / idle / approved; cloud→SKY agent placement **ERROR** (`bc-78cc5d10`, `bc-3fa853a6`) |
| Cutover | **NOT authorised** |

### Exact owner command (repo root on SKY)

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_inference_owner_arm64.ps1 `
  -Corpus "<owner-photographic-48still>"
```

Defaults expect ARM64 Python at  
`C:\Users\S8633\AppData\Local\Programs\Python\Python314-arm64\python.exe`,  
venv `.venv-arm64-perf` (role B), and x64 venv `.venv-312` (role A).  
Face pack: `%USERPROFILE%\.semblon\models\yunet_sface` (BYO).  
Refuses the lab stand-in unless `-AllowLabStandIn` (dry-run only — not PASS).

### Expected outputs (not present until owner run)

- `owner-arm64-runtime-A.json` / `owner-arm64-runtime-B.json`
- `owner-arm64-bench-A.json` / `owner-arm64-bench-B.json` (+ optional C)
- `owner-arm64-identity-safety.json`
- `owner-arm64-decision.json`

Then update `docs/BUILD-STATUS.md` and `docs/PERF-INFERENCE-IMPLEMENTATION-PLAN.md` from the decision JSON.  
Do not run 1K/5K/10K. Do not swap production `embed_bgr`.

Models: BYO via `SEMBLON_PERF_FACE_PACK` (`*.onnx` gitignored).
