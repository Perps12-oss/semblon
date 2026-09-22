---
name: semblon-observe
description: Semblon product and planned-work guard. Use on any Semblon code, CLI, schema, clustering, review, eval, or docs change.
---

# Semblon observe

Folder-first, local-first. Faces are the first mature capability, not the centre. Still photographs in, conservative groups out, human names people.

North star / planned work: `docs/SEM-ARCH-V1.4.md`.

## Invariants

- `cluster → review → person → name`. Cluster id is never person id. Plan-only generalization: `group ≠ entity`.
- Corrections write `decisions`. Naming links `cluster_person` and stamps `faces.person_id`.
- Unknown is valid. Prefer false split over false merge.
- S1 golden: `docs/S1-GOLDEN.md`. Frozen `eps=0.40`, `min_samples=2`, `1-dot`, `STRONG_MIN_INTRA=0.50`.
- Do not retune those params. Do not re-ingest `20260913T153515Z-1e915abe` to beautify clusters.
- Identity firewall: geometry / appearance / objects / semantics must not silently influence identity.

## Queue

Planned work is `docs/SEM-ARCH-V1.4.md` (APP-1 JobEngine MERGED; §I.5 human ship gates **CLOSED / DONE**; next = Application-API clients, R3 native shell chrome, PERF parallel). FACE-002 → FACE-005 is a closed validation index (`docs/FACE-GATES.md`), not the queue. Identify vs named persons, never clusters. STRONG is not a person until `name`. Incremental ingest + inbox and S6 memory are on `main`. Time/place must not change identity scores. Sampled video is holdout evidence (`docs/S7A.md`), not a second identity engine. S8 toolkit spike is presentation-only (`docs/S8-TOOLKIT.md`).

Do not print precision without `--eval-set confirmatory`.

## Out of v1

Public lookup, CCTV, webcam, ACC, mobile, multi-user, sharing, live ID, automatic identity. GUI is not required for v1 (`review-ui` is a shipped vertical).

If a change needs any of those, stop and say which SEM-ARCH-V1.4 slice authorizes it.
