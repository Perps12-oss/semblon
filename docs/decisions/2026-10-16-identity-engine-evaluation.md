# Decision: Identity-engine evaluation (YuNet / AuraFace / buffalo_l)

**Date:** 2026-10-16  
**Status:** Current — **NO ENGINE CHANGE APPROVED** (production)  
**Kind:** Non-committing engineering evaluation (evidence record)  
**Related:** `docs/decisions/2026-10-16-identity-stack-eval-order.md` (**YuNet + SFace isolated eval authorised**), `docs/decisions/2026-10-16-identity-engine-redistribution.md` (BYO / redistribution), `docs/licenses.md`, `docs/S1-GOLDEN.md`, `docs/BUILD-STATUS.md` issue 04  
**Code:** none in this record. Production identity remains FaceKit / InsightFace + `buffalo_l` (BYO).

## Verdict (read this first)

| Question | Answer |
|---|---|
| Is a production **release** cutover approved (all gates)? | **No** (L/Q/P incomplete). |
| Is YuNet + SFace the production **runtime** path? | **Yes** (implementation landed; buffalo_l retired from deps). |
| May archive / Similar / day-context work continue? | **Yes** — independent of face-stack evaluation; core promise must not wait on recognition. |
| Is identity-asset redistribution cleared? | **No** — Gate C identity assets remain **BLOCKED** / **UNAVAILABLE**. |
| Evaluation order | (1) YuNet + SFace → (2) YuNet + separately licensed ArcFace-compatible → (3) YuNet + AuraFace hold |
| AuraFace commercial redistribution? | **Hold** pending written licence + provenance confirmation. |
| Role of `buffalo_l` during eval? | **Comparison baseline** and current production engine (BYO). Not an assumed distributable asset. |

Passing any single gate below does **not** pass the others. Legal clearance ≠ technical suitability ≠ product approval.

---

## Recommended stance (preserved)

### YuNet + SFace — first isolated-eval stack

YuNet remains the leading **detector** candidate; SFace is the first **recogniser** to pair with it for lab measurement (authorised in `2026-10-16-identity-stack-eval-order.md`). Before experimental integration:

1. Pin the exact OpenCV Zoo ONNX file names and commits for **both** YuNet and SFace.
2. Copy each model directory’s licence notice (MIT for YuNet; Apache-2.0 claim for SFace) — OpenCV **code** licence does not clear model weights by itself.
3. Record local SHA-256 after download (not only a remote UI claim).
4. Probe the actual Windows **x64** and **ARM64** production OpenCV paths Semblon uses today.

YuNet alone is **not** a drop-in identity engine. Detector-only progress must not be misread as engine replacement.

### AuraFace — hold pending evidence

Do **not** approve commercial redistribution yet.

- Obtain **written** confirmation that the exact `glintr100.onnx` file is covered by the published Apache-2.0 grant and is not a re-hosted InsightFace non-commercial weight under another name.
- Investigate training-data provenance (names, licence terms, commercial-use restrictions).
- Keep published accuracy **and** fairness / demographic-coverage concerns in the record (model card limitations are material).

Public Apache-2.0 labelling and benchmark numbers are background, not Semblon clearance.

### `buffalo_l` — baseline, not assumed distributable

Preserve FaceKit / `buffalo_l` for existing development and evaluation where the operator’s local use is permitted (BYO + `pack-accept`).

Bundled commercial distribution of these weights remains **blocked** until appropriate rights are established (`docs/licenses.md`, redistribution decision). Local personal BYO use is a separate question from installer redistribution.

---

## Three refinements (binding for this record)

### 1. EU AI Act Article 53 — do not over-claim

Do **not** treat a named training dataset as an automatic legal requirement under EU AI Act Article 53. Applicability depends on the model and the provider role. General-purpose AI model obligations must not be casually equated with a blanket duty to publish every training dataset.

AuraFace’s training-data provenance nevertheless remains a **legitimate due-diligence concern** for Semblon’s commercial clearance. Clearing “we are not forced by Art. 53 to publish X” does not clear “we are comfortable shipping Y.”

### 2. No threshold transfer

Do **not** transfer current identity thresholds (`eps=0.40`, `min_samples=2`, metric `1-dot`, `STRONG_MIN_INTRA=0.50`, identify cut at `1 − eps`) to AuraFace, SFace, or any YuNet-paired recogniser.

Equal embedding dimensions and ArcFace-family compatibility do **not** guarantee equivalent score distributions. Keep the frozen S1 configuration unchanged for the production FaceKit path (`docs/S1-GOLDEN.md`). Evaluate candidates only on an **isolated experimental path**. Any proposed production migration requires a **separate, explicit decision** and a **fresh validation plan** (not a retune of the golden dump).

### 3. Semblon-specific evaluation required

Published benchmarks (LFW, WIDER Face, etc.) are useful background, **not** proof of suitability for Semblon’s archive workflow.

A Semblon eval must measure **detection and recognition separately**, including at least:

| Axis | Why it matters here |
|---|---|
| Pose / partial face | Family albums; not passport photos |
| Image quality / compression | Phone JPEG, HEIC→JPEG, video frames |
| Demographic variation | Fairness; model-card gaps |
| False merges | Product rule: wrong identity worse than unknown |
| False splits | Accepted when needed; must stay honest |
| CPU throughput | Default product path |
| ARM64 performance / load | First-class machine; OpenCV ARM64 load historically **BLOCKED** (`docs/PERF-P1-ARM64.md`) |

---

## Candidate inventory (sources checked 2026-10-16)

Hashes marked *reported* are from publisher UIs / pages on the verification date. They are **not** Semblon-local pin evidence until an owner download records `sha256sum` (or equivalent) against a frozen URL + commit.

### A. YuNet (detector)

| Field | Value |
|---|---|
| Role | Face **detection** (+ landmarks in Zoo demos) |
| Zoo tree | https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet |
| Licence file | https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE — **MIT** (Copyright 2020 Shiqi Yu) |
| README claim | “All files in this directory are licensed under MIT License” |
| Upstream train | https://github.com/ShiqiYu/libfacedetection.train |
| Paper | *Yunet: A tiny millisecond-level face detector* (Machine Intelligence Research) |
| Candidate files | `face_detection_yunet_2023mar.onnx` (fixed shape); `face_detection_yunet_2026may.onnx` (dynamic H/W, Zoo default for OpenCV 5.x ORT engine); int8 / block-quant variants |
| Semblon SHA-256 | **UNVERIFIED** — not downloaded for this record |
| Licence gate | **OPEN** — MIT text present; still need pinned file + local hash + NOTICE packaging plan |
| Quality gate | **OPEN** — Zoo WIDER numbers exist; Semblon archive eval not run |
| Integration gate | **OPEN** — not wired; see friction |
| Platform gate | **OPEN** — depends on OpenCV DNN / FaceDetectorYN on Windows x64 and ARM64 |

### B. SFace (recogniser often paired with YuNet in Zoo demos)

| Field | Value |
|---|---|
| Role | Face **recognition** embedding |
| Zoo tree | https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface |
| Licence | Apache-2.0 per Zoo `LICENSE` / README (“All files… Apache 2.0”) |
| Candidate file | `face_recognition_sface_2021dec.onnx` (+ int8 variants) |
| Semblon SHA-256 | **UNVERIFIED** |
| Note | First recogniser in the authorised evaluation order. Zoo Apache-2.0 claim is **not** L PASS until exact file + local hash + redistribution plan are evidenced. **Isolated eval only — not production.** |

### C. AuraFace (`glintr100.onnx`)

| Field | Value |
|---|---|
| Role | Face **recognition** (ArcFace-family ResNet100; InsightFace-compatible usage examples) |
| Hub | https://huggingface.co/fal/AuraFace-v1 |
| Licence file | https://huggingface.co/fal/AuraFace-v1/blob/main/LICENSE.md — labelled **Apache-2.0** |
| Model card | Claims commercial/public training data; notes ethnicity / generalisation limits; published LFW etc. scores |
| File | `glintr100.onnx` (~261 MB) |
| SHA-256 (HF UI, 2026-10-16) | `a7933ea5330113b01c9b60351d8f4c33003f145d8470ac5f0e52ee2effe25c60` (*reported*, not locally verified) |
| Provenance Qs outstanding | HF discussion #8 (weights original vs InsightFace NC `glintr100` / antelopev2); discussion #9 (commercial redistribute) — **no Semblon-owned written answer on file** |
| Licence gate | **HOLD** — label alone insufficient |
| Quality / fairness | **OPEN** — card concerns retained; Semblon eval not run |
| Integration / platform | **OPEN** |

### D. `buffalo_l` (current baseline)

| Field | Value |
|---|---|
| Role | Full FaceKit pack (detect + recognise + related ONNX set) |
| Production status | **Current engine** (BYO + pin); see redistribution decision |
| Redistribution | **UNAVAILABLE** / Gate C **BLOCKED** for bundled ship |
| S1 golden | `docs/S1-GOLDEN.md` — pack `insightface/buffalo_l@2.0/adapter-1/sha256:20a9264f823c3c3c`; thresholds frozen |
| Eval role | Comparison baseline for any experimental path |

---

## Four independent gates

A candidate may advance only when **all** applicable gates are **PASS** for the exact files under review. Mixed stacks (e.g. YuNet detect + AuraFace embed) need **each weight** cleared on Licence, then the **pair** cleared on Quality / Integration / Platform.

| Gate | Owns | PASS means | Fail / hold examples |
|---|---|---|---|
| **L — Licensing** | Legal / lead | Written rights to use **and** (if bundling) redistribute the exact ONNX bytes; NOTICE/attribution plan; provenance answers filed | Research-only zoo terms; unanswered HF provenance; Art. 53 confusion used as substitute for diligence |
| **Q — Model quality** | Identity owner | Semblon-specific detect **and** recognise metrics on an owner eval set; false-merge/split honesty; fairness notes | Cite LFW/WIDER only; transfer S1 thresholds; “dims match ⇒ scores match” |
| **I — Integration** | Engineering | Isolated experimental path; new `pack_id` space; no silent write into production FaceKit compare; firewall intact | Drop-in replace `load_app`; mix embeddings across packs; retune golden |
| **P — Platform** | Engineering | Windows x64 **and** ARM64 evidence on the real OpenCV/ORT path; CPU throughput acceptable; no silent S1 env swap | Assume Zoo demo ≡ Semblon ingest; ignore ARM64 OpenCV load history |

**Product approval** is a fifth, separate act: an explicit decision record that cites L+Q+I+P PASS evidence and authorises production cutover. This file is not that act.

---

## Migration friction — YuNet-centred (engineering estimate, no code)

Friction is rated for moving **production** identity off FaceKit/`buffalo_l` toward a YuNet-based detect path (with some recogniser). Scale: **Low / Medium / High / Blocking**.

| Area | Friction | Why |
|---|---|---|
| Detector API surface | **High** | Today ingest centres on InsightFace `FaceAnalysis` (`semblon/ingest.py` / `semblon.engine.load_app`). YuNet is OpenCV Zoo / `FaceDetectorYN`-class, not a FaceKit pack member. New adapter + pin model required. |
| Recogniser pairing | **High / Blocking until chosen** | YuNet does not replace recognition. SFace or AuraFace (or retained buffalo recognition) must be chosen and gated. Half-migration is not a shippable identity engine. |
| `pack_id` / store continuity | **High** | Existing runs and embeddings are buffalo_l-keyed. New pack namespace; no silent compare across packs (`docs/CONTRACTS.md`). Libraries need re-embed or dual-pack rules — product decision, not a silent migration. |
| Frozen thresholds / S1 golden | **Blocking if transferred** | Thresholds stay on FaceKit. Experimental path needs its own validation plan; do not re-ingest golden dump to “fit” a new model. |
| Clustering / review / identify loop | **High** | Score distributions will shift. Review UX and identify cutoffs must be re-evidenced; cluster≠person invariants stay, but operating points do not. |
| Identity firewall | **Medium** | Risk of “temporary” dual signals. Experimental path must not let geometry/appearance/YuNet det scores vote on identity compare. |
| Dependency / OpenCV | **High on ARM64** | YuNet path leans on OpenCV DNN. Native ARM64 OpenCV load remains historically **BLOCKED** (`docs/PERF-P1-ARM64.md`). x64-on-ARM64 emulation is not “native.” |
| MSI / redistribution story | **Medium if L passes; else unchanged Blocking** | MIT/Apache Zoo files may ease bundling **after** L PASS + hash pin. Does not unlock buffalo_l. AuraFace still HOLD. |
| Owner eval cost | **High** | Need labelled same/different pairs, pose/quality slices, false-merge hunt, CPU + ARM64 timing — not a weekend Zoo demo. |
| Dual-engine maintenance | **High** | While experimental, two packs/adapters/docs/tests. Product forbids a second identity engine in production (`docs/PRODUCT.md`) until an explicit swap decision. |
| Rollback | **Medium** | Keep FaceKit path authoritative until cutover decision. Experimental flags must default off. |

### Friction summary

- **YuNet as research detector probe:** Medium — feasible behind a lab flag once L-lite (MIT pin + hash) and P smoke (import + one image) exist.  
- **YuNet + SFace as production replacement:** High — full four gates + re-embed + new validation; ARM64 OpenCV is a known trap.  
- **YuNet + AuraFace as production replacement:** High + **Licence HOLD** — do not schedule cutover on Apache label alone.  
- **Claiming buffalo_l redistributable because YuNet exists:** Invalid — orthogonal; buffalo_l remains baseline/BYO/blocked for bundle.

**Estimate (order-of-magnitude, non-binding):** a serious Semblon-specific detect+recognise eval and isolated adapter is weeks of owner+engineering calendar time, not a single PR — dominated by eval set construction, ARM64 platform truth, and legal provenance — not by ONNX file copy.

---

## Evidence required to change “NO ENGINE CHANGE APPROVED”

All of the following must exist before a **separate** production-migration decision may be drafted:

1. **L PASS** for every ONNX file in the proposed ship set (written rights + local SHA-256 + URL/commit pin + NOTICE plan).  
2. **Q PASS** Semblon eval report: detect and recognise separated; false merge/split; fairness notes; CPU numbers; comparison vs buffalo_l baseline on the same set.  
3. **I PASS** design: experimental path only until cutover; pack_id rules; no threshold copy; firewall test evidence.  
4. **P PASS** Windows x64 and ARM64 on the intended OpenCV/ORT builds (native vs emulated labelled honestly).  
5. **Product approval** decision record that cites (1)–(4) and explicitly retires or dual-runs FaceKit — this evaluation file alone is insufficient.

Until then: production engine = FaceKit / `buffalo_l` (BYO). Redistribution of buffalo_l = **BLOCKED**. YuNet + SFace = isolated evaluation only. Path 2 (licensed ArcFace-compatible) if SFace fails quality. AuraFace = hold.

---

## What this record does not do

- Does not amend `docs/PRODUCT.md` identity engine clause.  
- Does not retune S1 thresholds or re-open FACE-002→005 as a queue.  
- Does not authorise InsightFace weight download, AuraFace bundling, or YuNet in the MSI.  
- Does not equate “fallback named in `docs/licenses.md`” with “approved.”  
- Does not block archive continuity, colour-histogram Similar, or day-context work.

## Verification date

Source URLs and publisher claims reviewed **2026-10-16**. Local file hashes for YuNet/SFace **not** captured in this pass. AuraFace SHA-256 recorded as Hugging Face UI report only.
