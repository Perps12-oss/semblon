# SEM-EXECUTION — measured against current main

The brief named `main@2c19d05` and `docs/SEM-RECONCILIATION-2026-09-21.md`.
That reconciliation is not on `main`. Current `main` when this note was written is `549161c` (`Preserve local launcher improvements`, 2026-10-26), Semblon `1.4.0`. The code on that commit is the authority. Nothing below reopens FACE-002 through FACE-005, retunes thresholds, replaces the tracker, or adds an Episode type.

## What was already true before this change

| Workstream | Current code | Action this pass |
|---|---|---|
| Product shell | Closed 2026-10-05. Production UI is PySide6 `semblon shell` → `Application` (`docs/ARCHITECTURE.md`). `docs/SEM-ARCH-V1.4.md` §E is labelled historical, not a live instruction. | No second GUI. No shell rewrite. |
| Live engine | `live_capture` detects, associates, identifies ACCEPT/UNKNOWN, never writes `faces.person_id`. | Tests extended. Not moved into the archive shell. |
| Live overlay | Tk lab surface (`semblon/live_overlay.py`). `docs/PRODUCT.md` (2026-10-16) lists live CCTV as out of the product. | Left outside the shell. |
| Review | `review.html` is retired. `review_board` / `name_track` already work at track level with a representative face. There is no Episode type. | Not invented. |
| Identity engine | Code is YuNet + SFace (`opencv/yunet_sface`). buffalo_l is not the runtime. | Not reverted. Not retuned. |
| Workers | Hash-only pool. Product default remains `1`. | Measured. Default not changed. |
| Observers | Probes distinguish import from a usable API. | Runtime on this machine recorded below. |

## What was implemented

- `semblon/track_fragmentation.py` — runs the existing greedy IoU associator and reports durations, short tracks, label purity, and crossings. It does not write the store and does not change `DEFAULT_IOU_MIN` or `DEFAULT_MAX_T_MS_GAP`.
- `tools/measure_track_fragmentation.py` — synthetic geometries plus a video pass. Video detection uses YuNet at the product score (`0.70`), NMS (`0.30`) and top-k. SFace is not run. The tool does not download weights. OpenCV 5.0 has no `CascadeClassifier` and no HOG people detector; the tool does not claim them.
- `semblon/hash_workers_measure.py` and `tools/measure_hash_workers.py` — time the current `_iter_hash_results` pool only.
- Tests for 0-face and 3-face live overlays, independent ink, tracker fragmentation, and hash digest equivalence.

## Live UI status

Not promoted into `semblon shell`.

Reason: `docs/PRODUCT.md` puts live CCTV outside the product, and `docs/ARCHITECTURE.md` keeps the live overlay off the production shell unless that contract changes. Putting a camera page on the archive shell would be a product-contract change, not a wiring fix. The Tk overlay was not copied into a second toolkit.

What the engine surface does, exercised with a fake camera:

- 0 faces: frames still arrive, annotations are empty, no face rows, no persons.
- 2 faces: already covered (`test_live_on_frame_emits_boxes_track_and_labels`).
- 3 faces: three boxes, three track ids, Alice only on the matching box, the other two stay UNKNOWN, `faces.person_id` stays null, the persons table stays at the one named person.
- Cancel of an unbounded capture already exists (`test_live_seconds_zero_stops_on_cancel`).
- Headless overlay still refuses to assign `person_id`.

Webcam and RTSP hardware were not opened. Windows UI responsiveness was not verified.

## Multi-person status

Simultaneous boxes do not share a track in one frame (existing `test_same_frame_exclusive`, plus the 3-face overlay test). A known name does not move onto another box when the embedding does not match. UNKNOWN stays UNKNOWN. No automatic Person is created.

## Track fragmentation

Associator unchanged: greedy IoU `0.30`, gap `2500` ms, embeddings do not vote.

### Synthetic, labelled (the tracker, given perfect boxes)

| Case | Result |
|---|---|
| 0 detections | 0 tracks |
| 1 detection | not a track (singleton) |
| Slow continuation | 1 pure track |
| 3 separated people | 3 pure tracks, no false associations |
| Gap beyond 2.5 s | 2 fragments, same label, not merged |
| One missed sample inside the window | still 1 track |
| Fast position swap | 2 impure tracks. Track centres do not cross, because the chains follow the boxes |
| 12 px/s cross of equal boxes | also 2 impure tracks. At the pass, the other last-box outscores own last-box |
| Large jump inside the time gate | split on IoU (`below_iou_within_gap`) |

So the tracker false-associates when two similar boxes occupy each other's previous footprint. That is measured. It is not, by itself, a reason to import a new tracking library: the same function holds separated people and a missed sample.

### Real video

YuNet `face_detection_yunet_2023mar.onnx` (local file, not committed), product detect thresholds, no SFace, no store writes. Clips are not in the repo: OpenCV `vtest.avi` (corridor, mostly side/back, 79.5 s, 768×576) and Intel `face-demographics-walking.mp4` (frontal walking, 61 s, 768×432). No ground-truth ids, so `false_associations` is null on these rows.

| Clip | Sample | Decoded | Sampled | Detections | Tracks | Singletons | Peak | Track duration | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| vtest.avi | 1 Hz | 795 | 80 | 27 | 0 | 27 | 2 | none | 18 in-window boxes were under the IoU gate |
| faces.mp4 | 1 Hz | 732 | 61 | 39 | 4 | 31 | 3 | every track is exactly 2 observations, p50 1000 ms, max 2000 ms | product sample rate does not hold a walking face |
| vtest.avi | 5 Hz | 795 | 398 | 146 | 10 | 119 | 3 | p50 200 ms, max 800 ms | still detection-limited |
| faces.mp4 | 5 Hz | 732 | 366 | 234 | 16 | 19 | 3 | mean 13.4 observations, p50 1500 ms, max 5333 ms / 32 observations | same associator, longer chains |

1 Hz timings on faces.mp4: decode 0.54 s for 732 frames, YuNet 0.72 s for 61 samples, associate 0.7 ms. Embed, UI, and storage were not on this path. Association is not the cost. Detection is. No GPU path was added.

**Tracker replacement: not justified yet.** On frontal faces the dominant failure at the product sample rate is the 1 Hz step, not the associator. At 5 Hz the same function keeps multi-second chains. `vtest.avi` mostly never sees a stable face, so it cannot indict the tracker. False swaps are proven on synthetic overlaps and unmeasured on these clips.

Evidence: `docs/evidence/track-fragmentation-2026-10-27.json`, `docs/evidence/track-fragmentation-5hz-2026-10-27.json`.

## Observer capability matrix

`optional_status()` on this Linux process (Python 3.11, numpy 2.4.6, opencv 5.0.0, no extra models):

| Capability | Installed here | Executes here | What the code actually does |
|---|---|---|---|
| Face identity | OpenCV DNN present. YuNet/SFace weights not in the product tree | Detection only, in the measurement tool, from a local ONNX | YuNet + SFace. Not MediaPipe. Not buffalo_l |
| OCR | `tesseract` not on PATH. `pytesseract` not installed | No | `probe_ocr_status` is false until the binary is on PATH. `search_text` is a substring over stored `kind='text'` payloads. It is not a face lookup |
| CLIP | `open_clip` / `torch` absent | No | `clip_embed` calls `encode_image` only. No image-text CLI was added. Separate text encoders exist in optional naming/semantic modules and were not exercised |
| Objects | No NanoDet ONNX | Contours only if called | `contour_objects` is a region heuristic (`class: region`). `optional_status()["object"]` is that heuristic, always true. NanoDet is a separate BYO probe and was false (`object_detection_nanodet_2022nov.onnx` missing). Contours are not COCO detection |
| Pose / hands / landmarks | `mediapipe` not installed | No | `probe_pose_status` requires `mediapipe.solutions.pose`. A 1.0 package without `solutions` stays false. No hands or face-mesh path was found in the pose observer |
| Region encoder | DINOv2 ONNX absent | No | Reported unavailable. Colour fallback is not that encoder |

This does not contradict an owner Windows machine where Tesseract or a BYO pack is present. It is this process. `semblon lab providers` remains the per-machine check. No capability flag was flipped.

## Worker benchmark

Current `_iter_hash_results` on 32 distinct 1 MiB files. Digests for workers 1, 2 and 4 matched on every repeat (`semantic_equivalent: true`). This is not ingest and not inference.

| Repeat | w=1 wall / files/s | w=2 | w=4 | RSS after w=4 |
|---|---|---|---|---|
| 1 (cold page cache) | 0.159 s / 201 | 0.046 s / 699 | 0.044 s / 733 | 114 MB |
| 2 (warm) | 0.044 s / 723 | 0.033 s / 970 | 0.040 s / 803 | 114 MB |
| 3 (warm) | 0.043 s / 752 | 0.039 s / 832 | 0.038 s / 832 | 114 MB |

Warm hash-only speedup is about 1.2× at 2 workers and about 1.1× at 4. Four workers use more RSS (~114 MB vs ~84 MB) and do not beat two. `/proc/stat` over a 40 ms window is too short to trust as CPU utilisation. Product default stays `workers=1`. The Windows harness in `docs/PERF-WORKERS-HARNESS.md` is still the only gate that may consider a default change, and this run is not that gate.

Evidence: `docs/evidence/hash-workers-2026-10-27.json`.

## Tests

Focused run, this machine, `pytest --noconftest` (the suite `conftest` imports PySide6, which is not installed here):

- `tests/test_live_overlay.py`
- `tests/test_live.py`
- `tests/test_tracks.py`
- `tests/test_track_fragmentation.py`
- `tests/test_hash_workers_measure.py`

Result: **37 passed, 0 skipped, 0 failed**, 1.16 s.

The full suite was not collected. Historical full-suite figures (262 at `2c19d05`, 914 at the 2026-10-05 shell baseline) were not re-run and are not claimed. Windows-only shell, webcam, RTSP, MSI, and ARM64 OpenCV were not verified. FACE-002 through FACE-005 files were not edited.

## What remains unimplemented

- Live boxes on the PySide archive shell.
- A real-webcam or RTSP session.
- SFace embed latency, overlay paint time, and live SQLite cost on a camera.
- Ground-truth identity switches on a real clip.
- End-to-end ingest at workers 1/2/4 (needs a stills folder and the face pack).
- OCR, CLIP, pose, and NanoDet execution on this machine.
- Any change to the tracker.

## Recommended next work

1. Sample frontal video above 1 Hz and measure the same associator again before touching it. At 1 Hz, `faces.mp4` produced only 2-observation tracks; at 5 Hz the same function held a chain for 5.3 s.
2. Put ids on one short frontal clip and count impure tracks. Synthetic overlaps already swap (fast swap and the 12 px/s cross). The real clips cannot say whether that happened.
3. Leave `workers=1`. Warm hash-only parallelism topped out near 1.2× at 2 workers, and 4 workers did not improve on that. Inference was not parallel.
4. Keep live CCTV off `semblon shell` until `docs/PRODUCT.md` says otherwise. The engine path for 0, 2 and 3 faces is tested and does not create a Person.
5. Treat optional observers as off unless `optional_status()` is true on the machine that will run them. This process had no Tesseract, no MediaPipe `solutions`, no CLIP weights, and no NanoDet pack.
