# Implementation plan — ORT YuNet/SFace backend (lab → optional → production)

**Status:** Phase 0 **COMPLETE** (Linux lab). Phase 1 / **PERF-6** owner native ARM64 measurement **READY TO RUN** — harness shipped; measured verdict **PENDING** owner photographic execution on SKY.  
**Winning candidate (lab numerical only):** `ort_yunet_sface` for hosts where OpenCV DNN cannot load natively (Windows ARM64).  
**Evidence:** `docs/PERF-INFERENCE-BACKENDS.md`, `docs/evidence/perf-inference/`.  
**Do not** treat Linux identity-agreement PASS as a performance win.

## Invariants (never reopen in this plan)

- Same model filenames; no weight substitution  
- No eps / min_samples / `DET_SCORE_MIN` / `CLUSTER_MIN_SIDE` edits  
- No automatic `faces.person_id` assignment  
- Identity firewall unchanged  
- `pack_id` continues to hash the ONNX bytes  
- `report` does not write the store  
- Production `embed_bgr` / PySide6 shell untouched until Phase 3 gates PASS  

## Phase 0 — Done (lab isolation)

1. Experimental package `semblon/experimental/inference/` (OpenCV DNN wrapper + ORT adapter).  
2. Harnesses: bench, identity-safety, resolution sweep, 48-still lab corpus builder.  
3. Linux x64 proxy: numerical agreement PASS; resolution keep 1280.  
4. Docs + `BUILD-STATUS.md` note. Production `engine.embed_bgr` untouched.

## Phase 1 / PERF-6 — Owner native ARM64 measurement (required)

**Objective:** establish whether native ARM64 ORT improves face-processing throughput vs emulated x64 OpenCV on the owner photographic 48-still set, with unchanged identity guarantees.

### Environment

| Item | Requirement |
|---|---|
| Native venv | `.venv-arm64-perf` (ARM64 Python) — do not silent-swap S1 |
| Emulated baseline | Production x64 venv (e.g. `.venv-312`) on the same ARM64 Windows host |
| ORT | 1.30.0 pin; `CPUExecutionProvider`; PE arch of loaded DLLs recorded |
| Models | Same BYO pack (`%USERPROFILE%\.semblon\models\yunet_sface`); SHA-256 vs `IDENTITY-PACK.md` |
| Corpus | **Owner photographic 48-still** — refuse lab stand-in |

### Runner

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_inference_owner_arm64.ps1 `
  -Corpus "<owner-photographic-48still-folder>"
```

Orchestrator: `tools/perf_inference_owner_arm64.py` (`verify` / `bench` / `identity` / `decide`).

### Roles

| Role | Interpreter | Backend | Label |
|---|---|---|---|
| **A** | x64 venv | `opencv_dnn` | Emulated x64 OpenCV (production path) |
| **B** | `.venv-arm64-perf` | `ort_yunet_sface` | Native ARM64 ORT (experimental) |
| **C** | `.venv-arm64-perf` | `opencv_dnn` | Native ARM64 OpenCV — only if load works |

### Metrics (steady-state; init separated)

Decode · YuNet detect · align · SFace embed · total; p50/p95/mean; images/s; faces/s; CPU util; peak working set; memory growth.

### Identity safety (owner set)

Cross-process embedding dump compare (A reference vs B candidate). Require detection P/R, small/distant recall proxies, bbox IoU, embedding cosine, retrieval top-1 same-file. No unauthorized identity assignment. Linux lab is **not** a substitute.

### Decision gate (`owner-arm64-decision.json`)

| Verdict | When |
|---|---|
| `RECOMMEND_CONTROLLED_EXPERIMENTAL_INTEGRATION` | B native + faster than A (≥5%) + identity PASS |
| `INVESTIGATE_SETTINGS` | B slower + identity PASS → tune ORT threads/memory, re-measure |
| `INCONCLUSIVE` / `NO_CUTOVER` | Missing native label, identity fail, or inconclusive delta |

**Production cutover remains false** for every PERF-6 verdict. No 1K/5K/10K.

### Evidence outputs

Under `docs/evidence/perf-inference/`:

- `owner-arm64-runtime-A.json` / `owner-arm64-runtime-B.json`
- `owner-arm64-bench-A.json` / `owner-arm64-bench-B.json` (+ optional C)
- `owner-arm64-identity-safety.json`
- `owner-arm64-decision.json`

Then update this plan’s Phase 1 status row and `docs/BUILD-STATUS.md` from the decision JSON.

## Phase 2 — Optional lab CLI (still not production ingest)

Only after PERF-6 recommends controlled integration:

1. Add `semblon lab infer-backend` (or extend `lab profile`) to select `opencv_dnn` | `ort_yunet_sface` for **read-only** profiling.  
2. Env `SEMBLON_EXPERIMENTAL_FACE_BACKEND=ort_yunet_sface` rejected by ingest/identify unless an explicit second flag is set later.  
3. Tests: pack missing fail-closed; backend enum; agreement smoke when pack present.

## Phase 3 — Gated production wire (separate PR)

Only after Phase 1 PASS on owner ARM64 **and** Phase 2 lab CLI:

1. Narrow adapter behind `load_app` / `embed_bgr` without changing thresholds.  
2. Default remains OpenCV DNN when it loads.  
3. On Windows ARM64 native, if OpenCV DNN load fails, allow ORT via **explicit** opt-in (not silent).  
4. Re-embed only if embedding-space agreement fails — otherwise stop.  
5. Update `docs/IDENTITY-PACK.md` / runtime notes with native vs emulated labels.  
6. MSI still fail-closed on weights (L OPEN).

## Phase 4 — Parallel OpenCV DNN ARM64 repair

1. Keep `tools/perf_p1_arm64_repro.ps1` as the load gate.  
2. If a DNN-ON ARM64 OpenCV build loads, re-bench OpenCV vs ORT natively; prefer the faster native backend that still passes identity-safety.  
3. Do not retune clustering from PERF numbers.

## Exit criteria for “production default = ORT on ARM64”

| Gate | Requirement |
|---|---|
| Identity numerical | Owner-set agreement PASS vs OpenCV DNN reference |
| Platform | `process_execution=native`, `process_arch=arm64`, ORT CPU EP |
| Perf | Measured speedup vs **emulated** baseline on same photographic stills; no invented ratios |
| Resolution | `DETECT_LONG_SIDE` unchanged unless separate quality PASS |
| Product | No silent backend swap; Settings/preflight states which backend ran |

Until those pass: keep production on OpenCV DNN; keep ORT experimental.
