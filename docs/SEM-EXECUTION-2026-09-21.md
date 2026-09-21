# SEM execution report — 2026-09-21

**Baseline:** reconciliation `docs/SEM-RECONCILIATION-2026-09-21.md` + code on `main` (1.4.0 lineage)  
**Branch:** `cursor/sem-1.4-execution-bf81`  
**Principle:** engine → product surface → real-world measurement → correction

FACE-002→FACE-005 remain **CLOSED**. No threshold retune. Observation ≠ Track ≠ Person.

---

## What was implemented

1. **Product shell decision (resolved):** existing PySide6 `semblon.desktop` is the **accepted** Home. Evidence: `semblon home` already launched it; navigation/pages/service/workers/import/review mutations already existed. Docs and CLI help were contradicting code — updated to match. Tk Home retained as `--legacy`. No second GUI framework.
2. **Live product surface:** new **Live** nav page with Start/Stop, source field, viewport overlays (label + Track id per box). `LiveWorker` runs `live_capture` off the UI thread. Engine gained `on_frame` + `build_frame_overlays` (runtime labels only; never stamps `faces.person_id`).
3. **Multi-person validation:** portable tests for 0/1/2/3+ faces, independent boxes/tracks, UNKNOWN, known name without leakage, no automatic Person.
4. **Tracker measurement (no rewrite):** `semblon track-measure` + `semblon.track_measure` fragmentation stats.
5. **Observer truth:** `optional_status()` / `pose_landmarks()` distinguish import vs runnable MediaPipe `solutions` API; object labeled as contour regions.
6. **Hash worker bench:** `semblon bench-hash-workers` measures workers=1/2/4 hash-only with digest equivalence.

---

## What was measured

### Track fragmentation (synthetic multi-person MP4)

Command: `semblon track-measure …/multi_person_synthetic.mp4 --synthetic-boxes --hz 10 --max-frames 60`  
Evidence: `artifacts/sem-exec-2026-09-21/track_frag.json`

| Metric | Value |
|---|---:|
| detections | 90 |
| tracks | 2 |
| obs/track | 45 / 45 |
| fragmentation_index | 0.0222 |
| short_lived_tracks | 0 |
| missed_associations_heuristic | 0 |
| max_simultaneous_faces | 2 |

**Verdict for this fixture:** greedy IoU is **adequate** — do **not** replace the tracker yet. Real camera crossings/occlusions still unmeasured on hardware.

### Hash workers (current hash-only implementation)

Folder: 48 small JPEGs. Evidence: `artifacts/sem-exec-2026-09-21/hash_workers.json`

| workers | elapsed_s | hash_files/s | digests ≡ |
|---:|---:|---:|---|
| 1 | 0.0007 | ~71k | baseline |
| 2 | 0.0015 | ~31k | yes |
| 4 | 0.0178 | ~2.7k | yes |

**Verdict:** keep default **workers=1**. Higher counts were slower on this folder. Still **not** inference parallelism.

### Live path (mocked FaceKit)

Evidence: `artifacts/sem-exec-2026-09-21/live_perf_mock.json` — synthetic frames + mocked detect/embed only. Useful for wiring latency, **not** a Windows webcam claim.

### Observer capability (this Linux environment)

| Capability | Installed/runnable | Notes |
|---|---|---|
| FaceKit identity | code path | weights/hardware env-dependent |
| Color / appearance | yes | non-identity |
| Objects | yes as **contour regions** | not a trained detector |
| OCR | false here | needs `pytesseract` (+ binary) |
| CLIP image embed | false here | needs `open_clip` + weights; **no** text-query CLI |
| MediaPipe pose | false here | import≠`solutions.pose`; Semblon now records that honestly |
| Hands / landmarks beyond pose | not claimed | |

Search remains: `--person/--people/--face/--similar` only. No `search --image` / `--text`.

---

## What remains unimplemented

- Real webcam/RTSP hardware proof of Live overlays on Windows
- Real multi-person camera video fragmentation (crossings/occlusions)
- Full live decode/detect/embed/UI cost breakdown on device
- OCR/CLIP/pose product features (optional libs + weights)
- Image/text visual retrieval CLI (intentionally not invented)
- Inference-parallel workers
- Episode abstraction (correctly absent)
- IPC / WinUI migration

---

## Live UI status

**Accepted shell:** PySide Home includes **Live**.  
Start/Stop + overlays for multiple faces with independent boxes and Track ids.  
Known names only from identify evidence; UNKNOWN valid; no auto Person.

Linux offscreen tests cover page/overlay/controls. Hardware camera not verified in this environment.

---

## Multi-person status

Portable engine tests cover 0 / 1 / 2 / 3+ simultaneous faces, independent tracks, no `person_id` leakage on live faces, no cross-box identity leak. UI paints multiple overlays independently.

---

## Track fragmentation results

See table above. Synthetic two-person continuity: fragmentation_index **0.022**. Replacement **not justified** by this evidence.

---

## Observer capability matrix

See table above. Docs (`PRODUCTION-STATUS`, `SEM-ARCH-V1.4`) updated so claims match executable truth.

---

## Worker benchmark results

workers=1 fastest on current hash-only path for the 48-file fixture; semantic digests equivalent across 1/2/4. Default remains **1**. Do not claim inference speedup.

---

## Tests

| | |
|---|---|
| collected/passed | **277 passed** |
| skipped | **1** (`tests/test_profile_out.py` — Windows peak RSS) |
| failed | **0** |
| runtime | **~14.5–15.1 s** (Linux, `QT_QPA_PLATFORM=offscreen`) |
| environment-dependent | InsightFace weights / real webcam / MediaPipe solutions / OCR binaries **not** exercised as product installs here |
| Windows-only not verified | native Home mica/backdrop, real camera Live, Windows RSS profiler |

FACE gates untouched.

---

## Remaining bottlenecks

1. Live quality/perf unknown on real cameras (mocked path only).  
2. Tracker unproven on crossings/occlusions (synthetic continuity looks fine).  
3. Hash workers>1 add overhead on small files; inference still serial.  
4. Optional observers mostly unavailable without extra installs.  
5. APP-1 Windows live ingest gate still required per SEM-ARCH-V1.4 C.3.

---

## Recommended next work

1. **Windows Live hardware gate** — webcam/RTSP through PySide Live page; record FPS, overlay correctness, cancel.  
2. **Real multi-person video fragmentation** — one library clip with crossings; keep/replace tracker from numbers.  
3. **APP-1 Windows ingest gate** — pause/cancel/responsive UI during real ingest (SEM-ARCH C.3).  
4. **Larger hash-worker bench** — multi-hundred MB stills on Windows native before any default change.  
5. **Observer install matrix on Windows** — document which extras actually run with the owner’s packs; keep identity firewall.
