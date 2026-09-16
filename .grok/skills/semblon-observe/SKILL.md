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

FACE-002 → FACE-003 → FACE-004 → FACE-005 recorded (`docs/FACE-GATES.md`). Identify vs named persons, never clusters. STRONG is not a person until `name`. Local pair labels are not cluster/person ground truth. Incremental ingest + inbox 1.1 on `main`. S6 memory is on `main`. Time/place must not change identity scores.

Do not print precision without `--eval-set confirmatory`.

## Out of v1

Public lookup, CCTV, webcam, video, ACC, mobile, multi-user, sharing, GUI, live ID, automatic identity.

If a change needs any of those, stop and say which FACE id authorizes it.
