---
name: identity-firewall
description: Keep identity comparisons on FaceKit/InsightFace only. Use when touching compare, cluster, embed, pack_id, weights, or any second similarity signal.
---

# Identity firewall

FaceKit / InsightFace is the only identity engine.

- No cross-pack compare. `pack_id` includes weight hashes.
- `buffalo_l` is a family name, not the compare key.
- Geometry, appearance, objects, and semantic similarity must not silently change identity scores or cluster membership.
- DBSCAN is `1 − cosine` on `status=ok` **stills** (`media.source_type=folder`) only. Hypothesis, not truth. S7a video samples are held out of clustering.
- Weights: internal evaluation only. Record in `docs/licenses.md`. Do not add parked §20 libraries.
- CONTRACTS.md is V1.1-corrected. Do not invent schema columns.
- `report` does not write to the store.
