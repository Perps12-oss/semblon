# S7b — Derived video tracks

**Status:** implemented as **derived evidence** (no store table).  
**Depends on:** S7a sampled observations (`frame_id`, `t_ms`); S8 inspectability (`path`+`frame_id`+`bbox`).  
**Does not depend on:** schema columns, ByteTrack / parked §20 libraries, video DBSCAN, S7c webcam, S7d RTSP, Canvas.  
**Planned work:** `docs/SEM-ARCH.md`.

## What this slice is

`semblon tracks --run --store` associates `status=ok` video face observations **inside one Media item** using:

```text
same media
  + later t_ms
  + t_ms gap ≤ 2500 (one missed 1 Hz sample)
  + bbox IoU ≥ 0.30
  + exclusive membership (one face per track per timestamp)
```

Output is JSON. It does **not** write the store. It does **not** set `cluster_id` or `person_id`.

```text
Observation  →  Track (temporal)  →  Hypothesis (optional, not this slice)
                                    →  Decision / Entity (never from Track)
```

## What it is not

- Not embedding clustering. `compare()` / `pack_id` / DBSCAN do not vote.
- Not a person. Machine ACCEPT still does not create an Entity.
- Not cross-video fusion. Fragments after a gap stay separate Tracks.
- Not a requirement that every Observation belongs to a Track. Untracked is valid.
- Not S7c / S7d. Not ByteTrack. Not a JPEG dump.

## Defaults (do not retune stills eps)

| Knob | Value |
|---|---|
| `iou_min` | `0.30` |
| `max_t_ms_gap` | `2500` |
| stills `eps` | frozen `0.40` (untouched) |

## Acceptance

1. Two overlapping boxes 1 s apart on one `.mp4` become one Track even if embeddings differ.
2. Two faces on the same frame never share a Track.
3. A 4 s gap does not fuse fragments.
4. A still (`source_type=folder`) is not a Track member.
5. `sqlite_master` has no `tracks` table after the command.
6. `identify` / `cluster_run` behavior unchanged.

## Next

S8 `review-ui` / `review.html` render these Tracks as the video review unit. This file does not open a full shell, identify UI, or live sources.
