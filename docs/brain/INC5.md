# Inc 5–11

Schema stays 12. No new inference model. No region-crop writer. Identity stays OpenCV DNN CPU. Azure is probed and never chosen over CPU.

The tag-only floor from the completed 10k run is 506.7 photos/min. Inc 5 does not wait on a cluster-time measurement. The governed run records its own rate.

| Inc | Behaviour | Module |
|---|---|---|
| 5 | EP probe per provider, RSS governor (pause under 256 MB free, throttle at 12 GB), input yield, chunk checkpoint, live status line, per-model throughput from samples | `semblon/brain/resources.py`, `pilot.py` |
| 6 | `TEMPORAL_NEXT` in media mtime order | `temporal.py` |
| 7 | `CO_OCCURS` between tags that share a photo | `cooccur.py` |
| 8 | `SAME_AS` between ObjectCluster centroids inside eps | `same_as.py` |
| 9 | `HAS_FACE` from an existing `faces.cluster_id` | `face_link.py` |
| 10 | `HAS_SCENE` from `modality='scene'`; `brain_gaps` is a query | `scene_link.py` |
| 11 | `approximate_predict` onto the nearest int8 centroid within eps | `object_cluster.py` |

Inc 8 does not link a Person node and does not write `faces.person_id`. Inc 9 does not update `faces`. Inc 11 does not run DBSCAN and is not called from product ingest. The pilot runs Inc 6–10 once after tags. It does not call `approximate_predict` and it does not call `index_image_regions`.

Tests: `tests/brain/test_inc5_resources.py`, `tests/brain/test_inc6_11.py`. Brain suite after this slice: 72 passed.

## 2M pilot — skipped

On 2026-11-05 the governed tag pilot (limit 2,000,000, corpus `K:\LIBRARY`, workers 4) was started and then stopped before any chunk report. Scheduled task `SemblonPilot2m` and pid 44600 were removed. No `PILOT-2M.md` was written. The partial store `K:\semblon-stress\pilot-2m.sqlite` was discarded, and `K:\semblon-stress\run-pilot-2m.py` was removed. That start is not a measurement. Do not resume it. Do not cite it. The last completed pilot number remains the tag-only 10k floor, 506.7 photos/min, in `PILOT-10K-VALIDATION.md`.
