# 10k validation — 2026-11-05 — SKY

Checkpoint only. This is not the 100k floor.

## Environment
- OS / arch / CPU / RAM / execution: Windows-11-10.0.26300-SP0 / x64 / ARMv8 (64-bit) Family 8 Model 1 Revision 201, Qualcomm Technologies Inc / 15983 MB / emulated
- Corpus: `K:\LIBRARY` — reservoir sample of 10000 from 328696 photos, seed sha256(corpus)[:8]=da96664e
- Command: `python -m semblon.brain.pilot --corpus K:\LIBRARY --limit 10000 --chunk 1000 --workers 4 --out docs\brain\PILOT-10K-VALIDATION.md --store K:\semblon-stress\pilot-10k.sqlite`
- Status: complete
- Exit code: 0

## Aggregate
- Total photos: 10000
- Tag-window elapsed: 19m 44s
- Wall elapsed: 19m 45s
- Throughput: 506.7 photos/min (8.44/s)
- Peak RSS: 1372.5 MB
- Cluster runs: 0 totalling 0s
- Swap events: 0

## Per-chunk
| Chunk | Photos | Elapsed (s) | RSS peak (MB) | Cluster (s) | Throughput (ph/min) |
|---|---|---|---|---|---|
| 1 | 1000 | 94.4 | 1372.5 |  | 635.7 |
| 2 | 1000 | 102.7 | 1372.5 |  | 584.5 |
| 3 | 1000 | 107.1 | 1372.5 |  | 560.3 |
| 4 | 1000 | 137.2 | 1372.5 |  | 437.4 |
| 5 | 1000 | 114.9 | 1372.5 |  | 522.1 |
| 6 | 1000 | 73.5 | 1372.5 |  | 816.8 |
| 7 | 1000 | 87.7 | 1372.5 |  | 684.2 |
| 8 | 1000 | 137.0 | 1372.5 |  | 438.0 |
| 9 | 1000 | 150.9 | 1372.5 |  | 397.6 |
| 10 | 1000 | 179.0 | 1372.5 |  | 335.2 |

## Notes / anomalies
- reservoir sample of 10000 from 328696 photos, seed sha256(corpus)[:8]=da96664e
- No provider fallback. A failed photo is logged and skipped.
- Workers: 4
- Photo errors: 442. The harness listed the first 30 paths; those paths are omitted here. Each logged error was `FileNotFoundError: unreadable image` from `cv2.imread` on a non-ASCII path. The bytes still decode with `np.fromfile` plus `cv2.imdecode`.
- Store after the run (`K:\semblon-stress\pilot-10k.sqlite`): media 10000, C1 `brain_observations` 9459, media with no C1 row 541, `embeddings` 0, modality `region`/`region_patch` 0, product `observations` 0, `observation_items` 0.
- Top tags: person=9230:tentative, bed=1046:tentative, chair=339:tentative, potted plant=312:tentative, cell phone=298:tentative, tie=164:tentative, cat=161:tentative, bottle=160:tentative
- Providers seen: opencv-zoo-nanodet

## Preflight — region embeddings

Counted on the stopped run's store `K:\semblon-stress\pilot-100k.sqlite` before this 10k run:

| Table | Count |
|---|---|
| `media` | 6030 |
| `brain_observations` where `capability_id='C1'` | 5682 |
| media with no C1 row | 348 |
| `embeddings` | 0 |
| `embeddings` modality `region` or `region_patch` | 0 |
| product `observations` | 0 |
| `observation_items` | 0 |

The table name matches. `rebuild_object_clusters` loads `embeddings` joined to `observation_items` and product `observations` where modality is `region` or `region_patch` (`semblon/brain/object_cluster.py` `_load_region_members`). The pilot counts the same two modalities (`semblon/brain/pilot.py` `_region_embedding_count`) and calls the rebuild only when that count grows, or when any exist and no cluster has run yet.

Nothing in this harness writes those rows. `_infer_photo` only calls `NanoDetObserver.observe`. An empty tag list returns `[]` and records no brain row (`semblon/brain/nanodet_observer.py`). Region vectors are written by product ingest (`semblon/ingest.py` semantic pass), `semblon/observers.py` `index_image_regions`, `semblon/category_backfill.py`, and `semblon/detail_priority.py`, through `persist_region_index` (`semblon/region_encoder.py`: crops `region`, patches `region_patch`). Whole-frame embeddings are modality `scene` and are not a region query.

The 10k store repeats the gap: 0 region embeddings, cluster runs 0 totalling 0s. A longer tag-only run cannot measure ObjectCluster time.

## Preflight — C1 misses on the stopped store

348 of 6030 media rows had no C1 observation. Every miss was classified (cloud attributes before any read; `imread` versus `imdecode`; NanoDet re-detect on 12 files that `imread` opened):

| Class | Count |
|---|---|
| Offline Yandex placeholder (not the held-out `DCIMaw\me` tree) | 143 |
| `cv2.imread` failed, file bytes still decode | 120 |
| File decoded, NanoDet returned no tags | 84 |
| Dark thumbnail (mean pixel 1.0) | 1 |

Of the 84 empty detections, 15 are `.photovault` thumbnails. Re-running `detect_objects` on 12 decoded misses (8 camera-roll or gallery stills and 4 thumbnails) returned zero tags. Those are empty detections, not lost exceptions.

## Decision

Cluster time on this complete 10k run is 0. The 100k run was not started. Slice B is to write region embeddings on the measurement path, then measure cluster time, before any 100k tag run.
