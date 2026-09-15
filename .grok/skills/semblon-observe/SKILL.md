---
name: semblon-observe
description: Semblon product and FACE-queue guard. Use on any Semblon code, CLI, schema, clustering, review, eval, or docs change.
---

# Semblon observe

Folder-first, face-first, local-first. Still photographs in, conservative groups out, human names people.

## Invariants

- `cluster → review → person → name`. Cluster id is never person id.
- Corrections write `decisions`. Naming links `cluster_person` and stamps `faces.person_id`.
- Unknown is valid. Prefer false split over false merge.
- S1 golden: `docs/S1-GOLDEN.md`. Frozen `eps=0.40`, `min_samples=2`, `1-dot`, `STRONG_MIN_INTRA=0.50`.
- Do not retune those params. Do not re-ingest `20260913T153515Z-1e915abe` to beautify clusters.

## Queue

FACE-004 `identify` ships (vs persons, never clusters). FACE-002 = eval harness + confirmatory set on the owner dump, not threshold fishing. FACE-005 is post-v1.

Do not print precision without `--eval-set confirmatory`.

## Out of v1

Public lookup, CCTV, webcam, video, ACC, mobile, multi-user, sharing, GUI, live ID, automatic identity.

If a change needs any of those, stop and say which FACE id authorizes it.
