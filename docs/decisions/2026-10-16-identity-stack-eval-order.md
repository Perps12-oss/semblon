# Decision: Identity-stack evaluation order (YuNet + SFace first)

**Date:** 2026-10-16  
**Status:** Current  
**Kind:** Evaluation authorisation — **not** production cutover  
**Related:**  
`docs/decisions/2026-10-16-identity-engine-evaluation.md` (friction + four gates),  
`docs/decisions/2026-10-16-identity-engine-redistribution.md` (BYO / buffalo_l),  
`docs/PRODUCT.md` (visual memory; FaceKit remains production identity engine until a separate cutover decision),  
`docs/BUILD-STATUS.md` issue 04 / milestones 1–3  

**Code:** none authorised by this record.

## Verdict

| Question | Answer |
|---|---|
| Production engine today? | **YuNet + SFace** runtime path landed (`opencv/yunet_sface`). `buffalo_l` retired from deps. |
| Production **release** cutover approved (L+Q+P+product)? | **No** — L OPEN (BYO), Q OPEN (provisional thresholds), P partial (x64 exercised; native ARM64 not evidenced). |
| Isolated evaluation of YuNet + SFace approved? | **Yes** — and implementation is now the production identity pipeline (not a demo). |
| May archive / whole-image Similar / region Similar / day context proceed? | **Yes.** Face recognition must not gate the core visual-memory promise. |
| buffalo_l redistribution? | Still **BLOCKED** / **UNAVAILABLE** until separate rights. |

Legal clearance ≠ technical suitability ≠ product approval. Passing one gate does not pass the others  
(`docs/decisions/2026-10-16-identity-engine-evaluation.md`).

---

## Product goal (why this order exists)

Semblon is local visual memory: find similar photos, group faces usefully, let users correct mistakes, and work offline on Windows x64 and ARM64. The goal is **not** to win an isolated face-recognition benchmark.

Strategic intent if a licensed stack clears all gates: replace `buffalo_l` as the redistributable / shippable recognition stack with an independently evaluated detector **and** recogniser — not “another face model” bolted on. That intent is **aspirational** until L+Q+I+P and a separate product-approval decision all PASS. This file does not amend `docs/PRODUCT.md`.

---

## Evaluation order (binding)

Investigate in this order. Do not skip ahead to AuraFace as the default.

| Order | Stack | Role in programme | Recommendation |
|---|---|---|---|
| **1** | **YuNet + SFace** | Lightweight OpenCV Zoo detector + recogniser pairing | **First candidate** — approved for **isolated evaluation** |
| **2** | YuNet + separately licensed ArcFace-compatible recogniser | Higher accuracy ceiling if exact weights + redistribution rights are established | Second candidate — only after path 1 fails quality targets or is licence-blocked |
| **3** | YuNet + AuraFace | Research candidate | **Hold** until provenance and commercial rights for the exact weights are resolved |

None of these is approved for production. YuNet solves **detection**, not recognition. The recogniser, embedding compatibility, thresholds, and model-pack lifecycle each need their own clearance.

### Candidate comparison

| Candidate | Strength | Main risk | Recommendation |
|---|---|---|---|
| YuNet + SFace | Lightweight; native OpenCV integration; documented Zoo detector/recogniser pairing ([YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), [SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)) | Exact SFace weight licence must be verified from the **model directory / weight file**, not inferred from OpenCV’s code licence; recognition quality, pose, and demographic error rates need Semblon measurement | First to evaluate |
| YuNet + commercially licensed ArcFace-compatible model | Potentially stronger accuracy ceiling | Rights, provenance, redistribution, runtime, and support for the **exact** weights | Second |
| YuNet + AuraFace | Potentially viable recogniser | Training provenance and exact weight rights unresolved in the evaluation record | Keep on hold |

**Licence distinction:** OpenCV’s library licence does **not** automatically clear every Zoo model. Check the exact SFace directory `LICENSE`, README redistribution claim, and the specific ONNX file (name + local SHA-256 + Zoo commit) before treating the complete stack as cleared.

---

## What “isolated evaluation” means

Approved now:

1. Owner (or designated engineer) may download **pinned** YuNet and SFace ONNX files for lab use, record hashes, and copy licence texts into evidence.  
2. An experimental adapter may be sketched or prototyped **behind a non-default path** that cannot be selected as production ingest without a further decision.  
3. Semblon-specific measurement on an ordinary family-photo set (below).  
4. Independent threshold calibration for that pack only. New `pack_id` space. **No** transfer of buffalo_l thresholds or embeddings.

Not approved:

- MSI / installer bundling of any candidate weights.  
- Silent swap of `load_app` / FaceKit.  
- Mixing candidate embeddings with buffalo_l compare.  
- Retuning S1 golden (`docs/S1-GOLDEN.md`) to fit the candidate.  
- Declaring Gate C identity assets cleared.

---

## Semblon-specific test set and metrics

Build (or designate) a set with ordinary family photos, group shots, small faces, pose changes, varied lighting, and difficult near-duplicates. Measure at least:

| Metric | Notes |
|---|---|
| False merges and false splits | After clustering **and** after human review loop; wrong identity worse than unknown |
| Recognition quality | Across pose and demographic groups; detect vs recognise reported separately |
| CPU time and memory | Windows **x64** and **ARM64**; native vs emulated labelled honestly |
| Provenance / licence / hash / redistribution | Exact model files; OpenCV code licence ≠ model clearance |

If SFace **passes** L+Q+I+P on that evidence, it becomes the practical replacement candidate for a **separate** production-cutover decision.  
If SFace **fails** the quality target, move to path 2 (separately licensed stronger recogniser) rather than accepting inferior grouping solely to remove `buffalo_l`.

---

## Strategic parallel track

Whole-image and region-based visual Similar, archive browsing, and contextual discovery **continue** while the face stack is evaluated. Face recognition must not become the dependency that stalls the core promise.

Production FaceKit / BYO `buffalo_l` remains available for identity work where the operator’s local use is permitted; redistribution stays blocked.

---

## Evidence to promote beyond isolated eval

Same bar as the evaluation ADR: L PASS + Q PASS + I PASS + P PASS for every ONNX in the proposed set, then a **new** product-approval decision that cites that evidence. This file only authorises ordered evaluation with YuNet + SFace first.
