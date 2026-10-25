# PERF — native face-inference backend investigation

**Slice:** PERF-4 / PERF-5 lab (SEM-ARCH-V1.4 §G.4–G.5).  
**Evidence date:** 2026-10-25 (Europe/London).  
**Production path:** unchanged — `semblon.engine.load_app` / `embed_bgr` via OpenCV `FaceDetectorYN` + `FaceRecognizerSF`.  
**Models:** same Zoo files (`face_detection_yunet_2026may.onnx` preferred, `face_recognition_sface_2021dec.onnx`). No substitutes.  
**Thresholds:** unchanged (`DET_SCORE_MIN`, `eps`, `min_samples`, min face side).

## Deliverables map

| # | Deliverable | Location |
|---|---|---|
| 1 | Native ARM64 runtime compatibility report | This file §1–§2 |
| 2 | Working experimental adapters | `semblon/experimental/inference/` |
| 3 | Backend comparison benchmark | `docs/evidence/perf-inference/backend-bench.json` |
| 4 | Identity-safety evaluation | `docs/evidence/perf-inference/identity-safety.json` |
| 5 | Recommendation | This file §5 |
| 6 | Implementation plan | `docs/PERF-INFERENCE-IMPLEMENTATION-PLAN.md` |

Harnesses: `tools/perf_inference_bench.py`, `tools/perf_inference_identity_eval.py`, `tools/perf_inference_resolution_sweep.py`, `tools/perf_inference_build_corpus.py`.

## 1. Native ARM64 ONNX Runtime (Task 1)

### What this cloud agent measured

| Check | Result |
|---|---|
| ORT version | `1.30.0` (repo pin) |
| Providers (Linux x64 native) | `CPUExecutionProvider` (+ listed `AzureExecutionProvider`, unused) |
| YuNet 2026may | Dynamic `input` `[1,3,H,W]`; 12 heads `cls/obj/bbox/kps` × strides `{8,16,32}` — **loads and runs** |
| YuNet 2023mar | Fixed `input` `[1,3,640,640]` under standalone ORT; OpenCV DNN accepts other sizes. Experimental ORT letterboxes to 640 when this file is selected. Prefer **2026may** for parity |
| SFace 2021dec | `data` `[1,3,112,112]` → `fc1` `[1,128]` — **loads and runs** |
| SHA-256 vs `IDENTITY-PACK.md` | 2023mar + SFace **match** pins; 2026may recorded separately |
| Preprocess | YuNet: BGR NCHW 0–255 (`blobFromImage`, no swapRB). SFace: BGR→RGB via `swapRB=True`, scale 1, 112×112 |
| YuNet decode | Port of OpenCV `FaceDetectorYNImpl::postProcess` (`yunet_decode.py`) |
| SFace align | Port of OpenCV `getSimilarityTransformMatrix` (`align.py`) |
| Numerical stability vs OpenCV DNN | Lab gate **PASS** — mean cosine ≈ 1.0, P/R = 1.0, mean IoU ≈ 1.0 on 48-still lab corpus |

### Windows ARM64 (owner — not re-run here)

Historical evidence (`docs/PERF-P1-ARM64.md`): native ARM64 ORT `1.30.0` in `.venv-arm64-perf` listed `CPUExecutionProvider` and ran. That remains the credible path for **native** YuNet/SFace when OpenCV DNN cannot load. This Linux run is a **compatibility + identity proxy**, not a native ARM64 speed claim. x64 Python on ARM64 Windows stays **emulated**.

## 2. Native ARM64 OpenCV DNN (Task 2)

| Question | Finding |
|---|---|
| Linux OpenCV 5.0.0 headless wheel | `FaceDetectorYN` + `FaceRecognizerSF` present → **BUILD_opencv_dnn effectively ON** |
| Identical source images vs ORT | Boxes/scores match; embeddings cosine ≈ 1.0 (`identity-safety.json`) |
| Windows ARM64 OpenCV with DNN | Still **BLOCKED** historically: local ARM64 build hung on `opencv_geometry500.dll`; PyPI fell back to sdist. Owner repro: `tools/perf_p1_arm64_repro.ps1` |
| FaceDetectorYN without DNN | OpenCV errors `StsNotImplemented` when DNN is off — matches the established `BUILD_opencv_dnn=OFF` bottleneck |

**Conclusion:** Obtaining a loadable Windows ARM64 OpenCV **with** DNN + face modules remains the open platform repair. Until that load is fixed, OpenCV DNN cannot be the native ARM64 identity backend.

## 3. Benchmark (Task 3) — Linux x64 native proxy

Corpus: `docs/evidence/perf-inference-48still/` (**lab stand-in**; owner photographic 48-still set was not in the repo).  
Host: `process_arch=x64`, `process_execution=native`, OpenCV threads=4.

| Backend | Decode p50 | YuNet detect p50 | Align p50 | SFace embed p50 | Total p50 | Wall (48) | Peak RSS |
|---|---|---|---|---|---|---|---|
| `opencv_dnn` | 1.30 ms | 5.90 ms | 0.06 ms | 4.69 ms | 12.11 ms | 1.05 s | ~316 MB |
| `ort_yunet_sface` | 1.68 ms | 30.17 ms | 0.27 ms | 23.19 ms | 56.63 ms | 4.18 s | ~360 MB |

Full percentiles + CPU util: `docs/evidence/perf-inference/backend-bench.json`.

**Reading:** On a machine where OpenCV DNN already runs natively, OpenCV is faster. The investigation target is Windows ARM64 where OpenCV DNN does **not** load and today’s path is **emulated x64** OpenCV (5K resume evidence: face processing 1,666 s). Native ORT is the candidate to remove that emulation tax — owner must re-bench on ARM64 native Python before any speed claim.

## 4. Identity safety (Task 4)

Reference: `opencv_dnn`. Candidate: `ort_yunet_sface`. Same models, same gates.

| Metric | Value |
|---|---|
| Detection precision / recall | 1.0 / 1.0 (tp=64, fp=0, fn=0) |
| Mean bbox IoU | ≈ 1.0 |
| Mean / min embedding cosine | ≈ 1.0 / ≈ 1.0 |
| Lab agreement gate | **PASS** |
| Production cutover authorised | **No** |

No threshold, eps, min_samples, confidence, or min-face edits. No automatic identity assignment. Firewall untouched.

## 5. Resolution sweep (Task 5)

Backend: ORT. Long-side caps vs production `DETECT_LONG_SIDE=1280`:

| Long side | Face-count recall vs 1280 | Detect time (sum) |
|---|---|---|
| 320 | 0.55 | 0.75 s |
| 640 | 0.75 | 1.45 s |
| 960 | 0.92 | 2.21 s |
| **1280** | **1.00** | 2.85 s |
| 1600 | 1.00 | 3.68 s |

**No resolution change becomes production default.** Smaller caps lose small/distant faces on this lab set. Keep 1280 until an owner photographic eval passes.

## 6. Recommendation (evidence-backed)

1. **Linux lab:** ORT is numerically safe vs OpenCV DNN on the same ONNX files — **not** a throughput win (OpenCV was faster on native Linux x64).  
2. **PERF-6 (required next; currently BLOCKED/PENDING):** measure native ARM64 ORT vs emulated x64 OpenCV on the owner photographic 48-still set. Harness is shipped; measured JSON is not. Exact owner command on SKY:  
   `powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_inference_owner_arm64.ps1 -Corpus "<owner-photographic-48still>"`  
   See `docs/PERF-INFERENCE-IMPLEMENTATION-PLAN.md` §PERF-6.  
3. **Do not cut over production** until PERF-6 `owner-arm64-decision.json` recommends controlled experimental integration **and** identity PASS.  
4. **Keep OpenCV DNN** as the production backend wherever it loads natively.  
5. **Parallel track:** ARM64 OpenCV DNN load (`PERF-P1`).  
6. **Do not** shrink `DETECT_LONG_SIDE` without quality PASS.

## 7. How to re-run (owner Windows ARM64 native)

```text
REM Isolated native venv — do not silent-swap S1
set SEMBLON_PERF_FACE_PACK=%USERPROFILE%\.semblon\models\yunet_sface
.venv-arm64-perf\Scripts\python.exe tools\perf_inference_build_corpus.py --out docs\evidence\perf-inference-48still
.venv-arm64-perf\Scripts\python.exe tools\perf_inference_bench.py --corpus docs\evidence\perf-inference-48still\stills --out docs\evidence\perf-inference\backend-bench-arm64.json
.venv-arm64-perf\Scripts\python.exe tools\perf_inference_identity_eval.py --corpus docs\evidence\perf-inference-48still\stills --out docs\evidence\perf-inference\identity-safety-arm64.json
```

Prefer the owner photographic 48-still folder when available (`--corpus <owner-folder>`). Do **not** rerun 1K/5K/10K stress for this investigation.

## Related

- `docs/PERF-P1-ARM64.md` — OpenCV load blocker  
- `docs/IDENTITY-PACK.md` — exact filenames / SHA-256  
- `docs/PERF-INFERENCE-IMPLEMENTATION-PLAN.md` — cutover steps  
