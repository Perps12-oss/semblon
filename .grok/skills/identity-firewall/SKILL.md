---
name: identity-firewall
description: Keep identity comparisons on the active face pack only. Use when touching compare, cluster, embed, pack_id, weights, or any second similarity signal.
---

# Identity firewall

Production identity engine: **YuNet + SFace** (`opencv/yunet_sface`). FaceKit / `buffalo_l` is retired from the runtime.

- No cross-pack compare. `pack_id` includes weight hashes.
- Family name is not the compare key.
- Geometry, appearance, objects, and semantic similarity must not silently change identity scores or cluster membership.
- DBSCAN is `1 − cosine` on `status=ok` **stills** (`media.source_type=folder`) only. Hypothesis, not truth. S7a video samples are held out of clustering.
- Weights: BYO OpenCV Zoo ONNX; MSI bundling blocked until licence gate L PASS. See `docs/IDENTITY-PACK.md` and `docs/licenses.md`.
- CONTRACTS.md is V1.1-corrected. Do not invent schema columns.
- `report` does not write to the store.
- Historical buffalo_l S1 constants: `semblon/identity_buffalo_frozen.py` — do not transfer to SFace.
