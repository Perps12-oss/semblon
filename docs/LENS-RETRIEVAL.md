# Local Lens-style retrieval — design

**Status:** engineering design on the closed architecture baseline.  
**Date:** 2026-10-19  
**Decision:** `docs/decisions/2026-10-19-local-lens-retrieval.md`  
**Product contract:** `docs/PRODUCT.md` (unchanged).  
**Evidence:** `docs/BUILD-STATUS.md`.

This file is the retrieval plan for the defining act: point at a thing in a local photo and find that visual content again in this archive. It is not a second product, not a second shell, and not identity.

Google Lens parity on a low-end CPU laptop is not the acceptance bar. The bar is a multi-leg retrieve-and-rank path that stays honest, local, and responsive, and that beats a single average vector.

---

## 1. What `main` actually does (audit, 2026-10-19)

HEAD at design time: `86fdcbf` on `main` (merge of highlight-region similar search).

The sketch `crop → OpenCLIP → Chroma top-k` is **not** the production path. Mapping:

| Claim | On `main` |
|---|---|
| OpenCLIP single vector for the crop | Optional observer `clip/openclip-vitb32@1` in `semblon/observers.py`. Whole-image Similar prefers DINOv2 `scene`, then CLIP, then colour. Region Similar does **not** default to OpenCLIP. |
| ChromaDB | Explicitly unwired. `semblon/index_provider.py` searches the exact derived matrix. SQLite embeddings stay authoritative. FAISS and Chroma are named as future ANN providers, disabled until a measured scan bottleneck. |
| One average crop vector | Production region encoder is DINOv2 ViT-S/14 ONNX (`semblon/region_encoder.py`). Ingest stores **content patches** (`embeddings.modality='region_patch'`) plus overlapping windows (`MAX_PATCH_WINDOWS = 9`). Query late-interacts the crop patches against those maps (`search_patches` in `semblon/region_search.py`). Proposal CLS crops are fallback only. Colour histogram is the labelled fallback when the pack is missing. |
| No query understanding | **Name this area** is already off the hot path (`name_selection`). Similar search labels from stored face / NanoDet / overlapping OCR; it does not wait on SigLIP naming or a VLM. Screen selection runs `lens.query_image` capabilities (OCR/objects) then `retrieve_selection`. Focus **Similar region** still calls `remember_and_find` → `find_similar_region`, which is visual-first and only takes the text door when `selection_kind` is text. |
| No text channel | OCR is Tesseract BYO. Ingest writes `observation_items.kind='text'`. `search_text` is **substring** on the longest ≥4-character token, not BM25. |
| No object channel | NanoDet BYO (`docs/OBJECT-PACK.md`), COCO-80. `search_object` is label substring. Contours are geometry, not a class. |
| No fusion | Screen / selection retrieval merges by media, keeping each basis, then ranked by (text-priority, number of bases, max raw score) until this slice. Focus similar-region does not call that merge. |
| Describer on the hot path | Not default. Optional VLM / SigLIP naming is **Name this area** or an install offer. `optional_providers` reports object and VLM separately. |

Cite:

- Region door: `Application.remember_and_find_region` → `region_search.remember_and_find` (`semblon/application.py`, `semblon/region_search.py`).
- Patch index: `index_image_regions` writes `scene`, `region_patch`, and up to six proposal `region` rows (`semblon/region_encoder.py`).
- Selection merge: `semblon/selection_retrieval.py` (screen path via `visual_query.run_visual_query`).
- ANN seam: `semblon/index_provider.py`.
- Identity firewall: extras never write `faces.person_id` or `embeddings.modality='face'` (`docs/CONTRACTS.md`, `docs/SEM-ARCH-V1.4.md` §F.3).

### Remaining gaps versus a Lens-style system

These are real, after the audit:

1. **Focus similar-region is still one retrieval leg.** Detector class and OCR are understanding, not recall, unless the selection is marked text.
2. **Fusion was score-mixing.** Visual cosine, OCR 0/1, and detector score are not comparable. Rank fusion is.
3. **No rerank of the fused head.** A same-colour distractor can still outrank a weaker but multi-channel true hit (clock lighting rank 4 in `docs/evidence/photo-region-eval.json`).
4. **Text is a single substring token**, so brand phrases and noisy OCR lose.
5. **Query-time detection on the crop is missing** on the Focus door. Ingest-time NanoDet boxes on the whole frame are used only when the click centre already sits in one.
6. **Tiles are coarse.** DINOv2 patches exist, but windows are at most nine overlapping fractions of the frame, letterboxed to 224. That is not 1024×1024 CLIP tiles, and it does not need to become that.
7. **Library scan is exact.** Fine until a measurement says otherwise. Not a reason to add Chroma.

---

## 2. Target architecture (local, CPU, BYO)

Keep the closed shell and the closed schema. Add legs, then fuse, then rerank.

```text
                    highlight box
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
     NanoDet crop     Tesseract OCR    DINOv2 crop
     (if pack ready)  (if binary)      patches
          │               │               │
          ▼               ▼               ▼
     class + tight     query strings    query tokens
     object crop
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
     metadata filter   BM25 over       patch MaxSim
     (class/colour)    stored OCR      (existing index)
          │               │               │
          └───────────────┼───────────────┘
                          ▼
                    Reciprocal Rank Fusion
                          ▼
              lightweight rerank (top ~50)
                          ▼
              strip: first look, then refined
                          │
                          └── Name this area (optional)
```

Moondream / Florence / SigLIP naming stay off this diagram's default path.

### 2.1 Query understanding — do not skip, do not describe

On highlight, run two **cheap** signals in parallel. Do not pass the whole crop to a describer and hope.

| Signal | What Semblon uses | Output | Notes |
|---|---|---|---|
| Object detection | Existing NanoDet-Plus-m 416 ONNX (`opencv-zoo-nanodet`). Not YOLO11n. | Main overlapping class + tighter box when confidence is high | BYO pack. Missing pack is honest, not an empty match. Contours are not a class. |
| OCR | Existing Tesseract. Not PaddleOCR or Florence-2 as a new default. | Strings + boxes in the crop | Reuse stored overlapping text when the query photo was ingested with OCR. Crop OCR only when stored text does not cover the box. |
| Visual tokens | Existing DINOv2 content patches of the crop | Query patch matrix | Already the primary similar-region engine. |
| Describe | SigLIP naming / optional VLM | One local noun or abstain | **Name this area** only. |

Do not add YOLO11n beside NanoDet. A second detector is a second pack, a second licence gate, and a second failure mode. If NanoDet is missing, the object leg is UNAVAILABLE; visual search still runs.

Do not add Florence-2 or PaddleOCR to the interactive default. Tesseract is the installed OCR probe. A later BYO OCR provider can implement the same `kind='text'` payload. The index is the stored strings, not the engine name.

### 2.2 Indexes — reuse the store, do not add a vector database

Library rows already live as observation items + embeddings. Build **views** over that store, not a parallel Chroma collection.

| Index | Backing rows | Query | New columns? |
|---|---|---|---|
| **A. Dense visual** | `embeddings.modality='region_patch'` with pack id `region/dinov2-vits14@1/<hash16>/patch`. Scene and proposal `region` stay fallback. | Crop patches MaxSim, then best per media. Match box = union of winning patches. | No |
| **B. Sparse text** | `observation_items.kind='text'` `payload_json.text` | Query-time OCR / stored overlap → BM25 (in-process over those strings). Substring remains the Fast fallback. | No |
| **C. Cheap metadata** | NanoDet `kind='object'` labels + scores + boxes; `appearance/rgb8@1` colour histogram already stored; box aspect from existing bboxes | Filter or rescore: class consistency, colour distance, aspect / layout | No |

**SigLIP** stays the naming runtime (`semblon/visual/naming_local.py`), not a second dense index. A SigLIP whole-crop vector would re-introduce the average-impression failure the patch map was built to avoid. If a contrastive query vector is added later, it is an extra channel behind the same fuse, with its own `pack_id`, never mixed into DINOv2 space, and never `modality='face'`.

**Tiles:** keep DINOv2 content patches. Optional later denser `patch_windows` (more than nine, still bounded) if a photographic eval shows small objects averaged away. Do not switch to 1024×1024 OpenCLIP tiles. The ONNX input is 224; overlapping windows already exist to give a small object more patches.

**ANN:** `active_vector_index()` stays the exact derived matrix. A FAISS HNSW provider may be added **behind that seam** only after a measured library-scan bottleneck (SEM-ARCH §G, §H). ChromaDB stays out. Approximate search must not become a second source of truth.

### 2.3 Retrieve in parallel, then fuse

At query time:

1. Crop the highlight (`crop_bgr`). Persist the user box once (`persist_user_region`). Do not write a query embedding.
2. NanoDet on the crop when the pack is ready → class hint + optional tighter crop.
3. OCR strings from overlapping stored text, else crop OCR when Tesseract is present.
4. Embed DINOv2 patches for the full crop, and for the tighter object crop when detector confidence is high.
5. Query patch MaxSim with both visual embeddings (same pack). Dedup by media, keep match boxes.
6. Query BM25 (or substring on Fast) with OCR tokens.
7. Optionally filter metadata (class / colour) without another neural model.
8. Fuse ranked lists with Reciprocal Rank Fusion (`semblon/retrieval_fuse.py`).
9. Lightweight rerank of the fused head (~50, then the quality profile's `max_results`).

Face similarity is a **separate door** (Focus **Same face**). It is not a fourth fuse channel.

### 2.4 Rerank — this is what makes it feel like Lens

Take the fused head and rescore with signals that are already local:

| Signal | Source | Role |
|---|---|---|
| Patch MaxSim on the object crop | DINOv2, tighter box if NanoDet was confident | Compare the object, not the whole highlight |
| OCR overlap | Token Jaccard / BM25 score against the candidate's stored text | Brand names, labels |
| Class consistency | Query NanoDet class vs candidate NanoDet class | Mug vs vase without a VLM |
| Colour histogram distance | Existing `appearance/rgb8@1` | Cheap reject of same-tint distractors |
| Layout / aspect | Stored bbox vs query bbox | Weak prior only |

Weighted sum. Weights live in `retrieval_fuse.py` and are tuned on the photographic holdout (`tools/eval_photo_regions.py`), **not** on S1 identity. Missing signals contribute nothing.

A ColPali / ColQwen late-interaction reranker is the GPU-class optional mode. DINOv2 patch MaxSim **is already** the CPU late-interaction scorer. Do not put ColPali on the interactive laptop path.

### 2.5 Latency budget (low-end laptop, ONNX CPU)

Keep the existing progressive UI: Fast first look, then Balanced/Max refine. Search stays off the UI thread. Cancel keeps the first look.

| Step | Budget | Current / plan |
|---|---|---|
| Crop + persist box | <10 ms | Exists |
| NanoDet on crop | 10–30 ms | Pack optional; skip when missing |
| OCR (small text) | 50–200 ms | Prefer stored overlap; crop OCR only if needed |
| DINOv2 1–2 crops | 30–100 ms typical after warm session; first call can be ~2 s on emulated x64 | Exists; Fast already strides tokens |
| Exact patch scan | 1–50 ms small libraries; **measure** before ANN | Exact derived index |
| BM25 / substring | <5 ms | Substring exists; BM25 in-process |
| RRF + rerank top-50 | <20 ms | This slice starts RRF |
| **Interactive total** | **~0.15–0.6 s** after warmup when packs are local | Show visual hits immediately; Name this area on click |

Moondream2 / VLM stays out of that total.

---

## 3. Identity firewall

Non-negotiable:

- Geometry, colour, objects, OCR, SigLIP, DINOv2, and RRF **must not** change `compare()`, DBSCAN, or `faces.person_id`.
- `embeddings.modality='face'` remains forbidden for these rows. Patch pack ids end in `/patch`.
- `report` still does not write the store. Query-time search still does not write an embedding for the user box.
- Unknown remains valid. A missing pack, a photo that was never indexed, and a genuine empty match stay different outcomes.

---

## 4. Slices (one path each)

Do not open a FACE-n or OBS/SIM ticket queue. These are product-construction slices on the closed architecture.

| Slice | Change | Out of scope |
|---|---|---|
| **0 — fuse** (this branch) | Reciprocal Rank Fusion (+ optional rerank API) in `selection_retrieval`. Face rows dropped. | Focus similar-region still visual-first |
| **1 — one retrieve door** | Focus Similar region calls the same multi-channel retrieve as screen selection. Understanding labels stay; they do not pick the matches. | No new encoder |
| **2 — BM25 text** | In-process BM25 over stored `kind='text'` payloads. Fast profile may keep substring. | No PaddleOCR, no new table |
| **3 — query-time object crop** | If NanoDet is ready, detect on the highlight, rescore with the tighter crop, pass class into rerank | No YOLO |
| **4 — lightweight rerank wired** | Object-crop MaxSim + OCR overlap + class + colour on the fused head. Tune on `eval_photo_regions` | No identity eval |
| **5 — denser windows (only if eval requires)** | Raise bounded `MAX_PATCH_WINDOWS` after a miss on small objects | Not 1024px CLIP tiles |
| **6 — ANN behind the seam (only if measured)** | FAISS HNSW provider in `active_vector_index` after a scan bottleneck | Not Chroma; SQLite remains authoritative |

Acceptance for each slice: tests on that door, no schema change, no face writes, missing pack stays UNAVAILABLE. Photographic ranks are re-run when a slice can change them; glyph eval is not the photo claim.

---

## 5. Accuracy order (what actually moves NDCG)

Biggest gains, given what is already on `main`:

1. **OCR as a recall channel on Focus similar-region** (slice 1 + 2) — text is the signal CLIP-style vectors ignore.
2. **RRF instead of max-score merge** (slice 0) — stops a strong colour/visual score from burying a weaker but jointly evidenced hit.
3. **Detected-object crop rescoring** (slice 3–4) — compare the object, not the whole highlight.
4. **Class + colour rerank** (slice 4) — cheap, already stored.
5. **Denser patch windows** (slice 5) — only if small objects still vanish.
6. **SigLIP as an extra dense channel** — optional, later, never a replacement for patches.
7. **GPU late-interaction reranker** — optional high-accuracy mode, not the laptop default.

---

## 6. What we refuse

- Public lookup, ACC, cloud indexes.
- Swapping DINOv2 for OpenCLIP or SigLIP as the sole region representation.
- ChromaDB, or any ANN that becomes authoritative.
- YOLO11n / PaddleOCR / Florence-2 / Moondream2 as default query understanding.
- New SQLite columns, a second store, or a second shell.
- Feeding region/object/text scores into identity.

---

## 7. Files

| Path | Role |
|---|---|
| `semblon/retrieval_fuse.py` | RRF + lightweight rerank. No I/O. No identity. |
| `semblon/selection_retrieval.py` | Parallel doors, now fused by rank. |
| `semblon/region_search.py` | Dense visual + understanding. Focus door until slice 1. |
| `semblon/index_provider.py` | Exact derived index; ANN off. |
| `semblon/search.py` | `search_text` / `search_object` (substring today; BM25 in slice 2). |
| `semblon/region_encoder.py` | DINOv2 patches and windows. |
| `tests/test_retrieval_fuse.py` | Rank fusion and firewall. |
| `tests/test_selection_retrieval.py` | Merge keeps each basis. |
