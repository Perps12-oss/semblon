# Implementation plan — ORT YuNet/SFace backend (lab → optional → production)

**Status:** Plan only. Production inference path **must not** change until gates below PASS.  
**Winning candidate (lab):** `ort_yunet_sface` for hosts where OpenCV DNN cannot load natively (Windows ARM64).  
**Evidence:** `docs/PERF-INFERENCE-BACKENDS.md`, `docs/evidence/perf-inference/`.

## Invariants (never reopen in this plan)

- Same model filenames; no weight substitution  
- No eps / min_samples / `DET_SCORE_MIN` / `CLUSTER_MIN_SIDE` edits  
- No automatic `faces.person_id` assignment  
- Identity firewall unchanged  
- `pack_id` continues to hash the ONNX bytes  
- `report` does not write the store  

## Phase 0 — Done on this branch (lab isolation)

1. Experimental package `semblon/experimental/inference/` (OpenCV DNN wrapper + ORT adapter).  
2. Harnesses: bench, identity-safety, resolution sweep, 48-still lab corpus builder.  
3. Linux x64 proxy: numerical agreement PASS; resolution keep 1280.  
4. Docs + `BUILD-STATUS.md` note. Production `engine.embed_bgr` untouched.

## Phase 1 — Owner native ARM64 measurement (required)

1. Use `.venv-arm64-perf` (native ARM64 Python + ORT 1.30.0). Do not swap S1.  
2. Point `SEMBLON_PERF_FACE_PACK` at the pinned BYO pack (same SHA-256).  
3. Run bench + identity-safety on the **owner photographic** 48-still set (or lab corpus if absent).  
4. Record `process_arch=arm64`, `process_execution=native`.  
5. Compare wall time to emulated x64 OpenCV on the same stills (honest labels).  
6. Pass bar: lab agreement criteria + clear native speedup vs emulated baseline on the same corpus. No 1K/5K/10K.

## Phase 2 — Optional lab CLI (still not production ingest)

1. Add `semblon lab infer-backend` (or extend `lab profile`) to select `opencv_dnn` | `ort_yunet_sface` for **read-only** profiling.  
2. Env `SEMBLON_EXPERIMENTAL_FACE_BACKEND=ort_yunet_sface` rejected by ingest/identify unless an explicit second flag is set later.  
3. Tests: pack missing fail-closed; backend enum; agreement smoke when pack present.

## Phase 3 — Gated production wire (separate PR)

Only after Phase 1 PASS on owner ARM64:

1. Introduce a narrow adapter interface behind `load_app` / `embed_bgr` **without** changing call sites’ thresholds.  
2. Default remains OpenCV DNN when `FaceDetectorYN` imports and loads.  
3. On Windows ARM64 native, if OpenCV DNN load fails/probes BLOCKED, allow ORT backend via explicit opt-in config (not silent).  
4. Re-embed is **not** required if embeddings stay in the same space (cosine agreement ≥ lab bar on owner set). If agreement fails, stop — do not ship.  
5. Update `docs/IDENTITY-PACK.md` / runtime notes with native vs emulated labels.  
6. MSI still fail-closed on weights (L OPEN).

## Phase 4 — Parallel OpenCV DNN ARM64 repair

1. Keep `tools/perf_p1_arm64_repro.ps1` as the load gate.  
2. If a DNN-ON ARM64 OpenCV build loads, re-bench OpenCV vs ORT natively; prefer the faster native backend that still passes identity-safety.  
3. Do not retune clustering from PERF numbers.

## Exit criteria for “production default = ORT on ARM64”

| Gate | Requirement |
|---|---|
| Identity numerical | Owner-set agreement PASS vs OpenCV DNN reference (or frozen embedding snapshot) |
| Platform | `process_execution=native`, `process_arch=arm64`, ORT CPU EP |
| Perf | Measured speedup vs **emulated** baseline on same stills; no invented ratios |
| Resolution | `DETECT_LONG_SIDE` unchanged unless separate quality PASS |
| Product | No silent backend swap; Settings/preflight states which backend ran |

Until those pass: keep production on OpenCV DNN; keep ORT experimental.
