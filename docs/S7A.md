# S7a — Video files (sampled observations)

**Status:** gate open 2026-09-17. Dump evidence on owner machine (run `20260917T161452Z-a012c0fe`).  
**This is** the first S7 engine slice: video *files* as temporal sources.  
**Design:** `docs/SEMBLON_MATURITY_BLUEPRINT.md` §S7.  
**Not yet:** S7b tracklets / Appearances, S7c webcam, S7d RTSP, Canvas(Video), JPEG-per-frame dumps.

## What this slice is

A folder may contain video files. Ingest **samples** frames (default 1 Hz) into the existing store:

- `media.source_type = 'video'`
- `observations.frame_id` = source frame index
- `observations.t_ms` = timestamp in the file
- FaceKit detect+embed on the sampled BGR frame (no frame written to disk)

Same `compare()` / pack_id / frozen stills clustering params. Time does not vote on identity.

## What it is not

- Not still-image ingest of every frame.
- Not tracking (S7b).
- Not live / USB / RTSP.
- Not a new identity engine.
- Not a PRODUCT v1 requirement — v1 remains stills. S7a is post-v1 maturity work.
- No new schema columns. No ByteTrack / parked §20 libraries.

## Identity rules (unchanged)

```text
sampled face observation
  → compare() vs confirmed person references (same pack_id)
  → ACCEPT | UNKNOWN
```

Cluster is still a hypothesis. Video sampled `status=ok` faces are **held out of DBSCAN** in this slice so a talking-head clip cannot become a stills-style JPEG cluster. `identify` vs **named persons** is the identity path. Human review still names people.

**Semantics:** `observation ≠ tracklet ≠ person`. A large `unassigned` count after video ingest is an **observation** count (temporal repetition across sampled frames), not an identity count. Do not “fix” that number by enabling product DBSCAN on video.

## Defaults (do not retune stills eps)

| Knob | Value | Notes |
|---|---|---|
| `sample_hz` | `1.0` | one sampled frame per second of video |
| detect / embed | same FaceKit pack as stills | `embed_bgr` |
| `eps` / `min_samples` | frozen S1 | stills-only clustering |

## Acceptance

1. A folder with an `.mp4` (and stills) ingests: stills unchanged (`source_type=folder`, `frame_id` NULL); video media is `source_type=video` with multiple observations (`frame_id`, `t_ms` set).
2. Sampled observation count is far below native frame count (not 25–30 per second).
3. Incremental skip: same video sha256 is skipped unless `--reprocess`.
4. Video ok faces are not assigned `cluster_id` by `cluster_run`.
5. `identify --face` on a named person still works for stills; video faces may be identified against persons, never clusters.
6. No change to `eps=0.40` / confirmatory 0.60.

## Dump evidence (2026-09-17)

Run `20260917T161452Z-a012c0fe`: 2 videos → 231 samples @1 Hz → 434 ok faces → 0 product clusters (holdout). Offline frozen DBSCAN compresses those faces into a few groups (two dominant cross-video); that supports temporal repetition, **not** person labels. S8 must make each observation inspectable (`docs/S8-REVIEW-UI.md` Reviewability) before S7b design locks.

## Next (ordered, not this ticket)

1. **S8 Reviewability** — video path + `frame_id` + bbox → render-time thumb (`docs/S8-REVIEW-UI.md`).  
2. S7b design decision: tracklets / Appearances as the video review unit (observation → tracklet → representative frames → optional person).  
3. S7c webcam / S7d RTSP remain deferred.  
4. S8 Canvas(Video) only after S7a + inspectability evidence exists.
