# Decision: Identity engine path and redistribution

**Date:** 2026-10-16  
**Status:** Current  
**Tracker:** `docs/BUILD-STATUS.md` issue 04

## Decision

1. **Keep** FaceKit / InsightFace with `buffalo_l` as the identity engine for product ingest and review.
2. **Do not** bundle `buffalo_l` ONNX weights in the installer until a separate redistribution licence exists (`docs/licenses.md`: UNAVAILABLE).
3. **Operational path:** owner (or lab) places weights locally and pins them with `semblon lab pack-accept`. Product ingest refuses unpinned packs and does not download weights.
4. **Do not** silently switch to YuNet + SFace. An alternative engine requires an owner-provided representative eval set, a recorded accuracy trade-off, and an explicit follow-up decision — not this release.

## Non-negotiables

- Frozen clustering / detect parameters unchanged.
- No silent engine substitution; no download during normal ingest.
- Local `pack-accept` success is **not** proof of redistributability (Gate C).

## Gate impact

| Criterion | State |
|---|---|
| Local offline ingest with accepted pack | Achievable (IMPLEMENTED path) |
| Legally redistributable bundled assets | BLOCKED — licence |
| MSI contains weights | Forbidden until licence |

## Commercial ship stance (2026-10-16)

**Chosen path until a redistribution licence exists: bring-your-own pack.**

- Semblon code MSI / checkout install may ship.
- `buffalo_l` ONNX files are **not** bundled.
- The operator places weights locally and pins them with `semblon lab pack-accept`.
- InsightFace research-only model-zoo terms are treated as **blocking redistribution**, not blocking local personal use with BYO weights.
- Swapping to YuNet/SFace/AuraFace/DeepFace is **out of scope** here. FaceKit remains the only identity engine until an explicit eval + decision.

## Unblock (Gate C identity assets)

1. Obtain written redistribution rights for the exact weight files (version + hashes), **or**
2. Keep BYO permanently and document that commercial redistribution of weights is never offered, **or**
3. Supply an authorized alternative pack and complete the eval gate before switching engines (separate decision; not this release).
