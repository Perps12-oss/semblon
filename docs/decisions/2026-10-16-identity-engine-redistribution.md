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

## Unblock

Obtain written redistribution rights for the exact weight files (version + hashes), or supply an authorized alternative pack and complete the eval gate before switching engines.
