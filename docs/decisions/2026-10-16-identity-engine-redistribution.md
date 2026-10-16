# Decision: Identity engine path and redistribution

**Date:** 2026-10-16  
**Status:** Current  
**Tracker:** `docs/BUILD-STATUS.md` issue 04

## Decision

1. **Production identity runtime** is YuNet + SFace (`docs/IDENTITY-PACK.md`). FaceKit / `buffalo_l` is retired from dependencies and ingest.
2. **Do not** bundle YuNet/SFace (or buffalo_l) ONNX weights in the installer until licence gate **L PASS** (`docs/licenses.md`: BYO / MSI fail-closed).
3. **Operational path:** owner places Zoo ONNX files under `~/.semblon/models/yunet_sface` and pins with `semblon lab pack-accept`. Ingest refuses unpinned packs and does not download weights.
4. Historical buffalo_l S1 constants remain in `semblon/identity_buffalo_frozen.py` for old stores; they must not control the SFace engine.

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

## Related evaluation (non-committing)

Candidate friction and four-gate clearance live in  
`docs/decisions/2026-10-16-identity-engine-evaluation.md`.  
Evaluation **order** (YuNet + SFace first, isolated only) lives in  
`docs/decisions/2026-10-16-identity-stack-eval-order.md`.  
Neither amends this BYO / redistribution stance; production cutover remains unapproved.
