# Decision — local Lens-style retrieval is a ranking system, not a model swap

**Date:** 2026-10-19  
**Status:** current — **PLAN ONLY**. No retrieval behaviour changes in this record.  
**Branch:** `cursor/lens-retrieval-strategy-1388` (cut from `origin/main` `86fdcbf`)  
**Related:** `docs/PRODUCT.md`, `docs/BUILD-STATUS.md`, `docs/ROADMAP.md`, `docs/SEM-ARCH-V1.4.md`, `docs/decisions/2026-10-18-local-visual-discovery.md`, `docs/REGION-PACK.md`, `docs/OBJECT-PACK.md`

This is the enhancement strategy for “point, understand, and find.” It does not reopen `docs/ARCHITECTURE.md`, identity thresholds, or the identity firewall. Geometry, colour, objects, text, and region matches still do not write `faces.person_id` or `embeddings.modality='face'`.

---

## Verdict

Do not try to “do better” by swapping one embedding. Do better by changing the retrieval structure:

```text
detect + OCR on the crop
  → parallel recall (dense visual + sparse text + cheap metadata)
  → Reciprocal Rank Fusion
  → lightweight rerank of the top ~50
  → optional heavy describe / late-interaction mode on demand
```

That is the local, low-end-laptop version of the Lens pattern. A single crop vector asked to do everything is one retrieval leg. Lens is several independent evidence channels, fused and then reranked.

Semblon already has most of those channels. The gap is that the product door still treats one of them as the search, and merges the others by union. The work is to make query understanding, multi-leg recall, fusion, and rerank the default Similar-region path — on the existing store, packs, and shell.

---

## The “current pipeline” diagnosis is stale

The brief that starts `crop → OpenCLIP single vector → ChromaDB top-k` does not describe `main` today.

| Claim in that brief | What `origin/main` actually does |
|---|---|
| OpenCLIP single vector | DINOv2 ViT-S/14 content patches (`embeddings.modality='region_patch'`), scored by late interaction. Proposal CLS is fallback only. Colour histogram is the labelled last resort. |
| ChromaDB top-k | SQLite embeddings are authoritative. Similar search reads the exact derived matrix through `index_provider.active_vector_index`. ANN is named and disabled. FAISS and Chroma are not product dependencies. |
| Whole-image average | Ingest stores every content patch plus overlapping windows. A pointed crop is scored against those patches. The match box is the union of winning patches. |
| Moondream / VLM in the hot path | **Name this area** is a button. Similar search does not wait on the naming model. |
| No text channel | OCR substring search exists (`search_text` over `observation_items kind=text`). Crop OCR can feed that door. |
| No object channel | NanoDet BYO class search exists (`search_object`). Contours stay geometry, not a class. |
| No merge | Screen-selection retrieval already runs region + text + object and merges by `media_id`. Focus **Similar region** still does not. |

Citations on `main`:

- Dense visual: `semblon/region_search.py`, `docs/REGION-PACK.md`, `docs/evidence/photo-region-eval.json`
- Index seam: `semblon/index_provider.py` (ANN unwired; FAISS/Chroma refused until a measured bottleneck)
- Multi-door merge: `semblon/selection_retrieval.py` (union by photo; max score; bonus for more bases)
- Focus door: `Application.remember_and_find_region` → `region_search.remember_and_find` (visual first; text is a door only when the selection is text-priority)
- Identity firewall: Face Similar stays a separate door (`search_similar_faces`)

Milestone 2 on the photographic set stays **VERIFIED**. This decision does not reopen that gate. It names the quality gap that remains after it.

---

## Why the current structure still underperforms Lens

The remaining weakness is not “we picked the wrong single vector.” It is that one channel still has to carry the search.

1. **Focus Similar region is one visual leg.** `remember_and_find` embeds the highlighted box (patch late-interaction when the pack is ready) and only falls through to colour. Stored OCR and NanoDet labels are understanding, not recall, unless the selection is text-priority.
2. **Query understanding is incomplete on the crop.** Crop OCR exists. Query-time NanoDet on the highlight does not. There is no high-confidence tighter object crop used as a second visual query.
3. **Text recall is substring, not tokens.** `search_text` requires the query string to appear inside the stored payload. Brand fragments, OCR noise, and word order miss. There is no BM25 inverted index over extracted text.
4. **Fusion is a union, not rank fusion.** `selection_retrieval._merged` groups by `media_id`, keeps the max score, and prefers hits that appeared on more doors. Scores from cosine, substring, and class match are not comparable. Reciprocal Rank Fusion is the honest combine.
5. **There is no rerank stage.** Nothing rescores the top fused candidates with object-crop similarity, OCR token overlap, class consistency, or colour/layout distance.
6. **A late-interaction visual scorer already exists** (`region_patch` MaxSim-style). That is the local stand-in for ColPali-class patch correspondence. It must stay the dense visual engine, not be replaced by a whole-image SigLIP vector.

Google Lens extracts object regions, text, and visual semantics, retrieves from several indexes, then reranks. Closing that gap means adopting that *structure* on Semblon's existing legs — not importing Chroma, YOLO11n, or a second identity engine.

---

## Target architecture (mapped onto Semblon)

Keep the production path: PySide6 `semblon shell` → `Application` → domain / storage / providers. No second shell. No new schema columns. No vector database as a product dependency.

### 1. Query understanding — do not skip this

When the user highlights a box, do not pass the whole crop to one model and hope. Run two cheap signals in parallel with the existing visual embed. Neither signal writes identity.

| Signal | Semblon provider | Output | Notes |
|---|---|---|---|
| Object detection | NanoDet BYO (`docs/OBJECT-PACK.md`) | main class + box, when confidence is high | YOLO11n / YOLOv8n is **not** a required swap. A later BYO detector may sit behind the same object-pack probe. Missing pack = that signal unavailable, not a failed search. |
| OCR | Tesseract BYO (`observers` / `probe_ocr_status`) | text strings + boxes | PaddleOCR / Florence-2 is **not** a required swap. Same honesty rule. |
| Visual embed | DINOv2 ViT-S/14 region pack | patch tokens of the full crop, and of the tighter object crop when NanoDet confidence is high | SigLIP is an optional second dense channel when its pack is ready. It does not replace DINOv2. |

Do not put a VLM, Moondream, or **Name this area** on this path. Describe / name stays a button.

Fast quality may skip the detector/OCR pair and publish the first visual look. Balanced and Max run the cheap signals on the refine pass that already exists.

### 2. Indexes — offline, derived from the store

The library is not a flat Chroma collection of full-image CLIP vectors. It must not become one. Build (or keep) three recall sources from rows Semblon already stores.

**A. Dense visual index (exists; keep)**

- Engine: DINOv2 ViT-S/14 ONNX, `modality=region_patch`, pack id ending `/patch`.
- Compare: late interaction (mean of each query patch's best cosine in the other photo). Match box = union of winning patches.
- Why this stays: it already does the job the brief assigns to “tile-level embeddings with overlap.” Adding a second 1024×1024 tile index on top of content patches is a cost, not a gain, until a measurement says otherwise.
- Whole-image / scene / `clip` vectors remain supporting channels for **Whole photo**, not the region door.
- Optional later: SigLIP crop/scene vectors in the existing `embeddings` table (`modality` already used for clip/siglip/scene). Second list, same fuse. Not a swap.

**B. Sparse text index (upgrade)**

- Offline: OCR already writes `observation_items kind=text`.
- Query: OCR the crop (and any overlapping stored text on that photo).
- Recall: BM25 over the extracted text, derived from those payloads. No new table.
- Persistence: an exact derived sidecar, the same pattern as `ann_index` (SQLite remains authoritative; the sidecar can be rebuilt).
- This is the largest remaining accuracy lever. Substring search misses the brand / label / price-tag cases CLIP also misses.

**C. Cheap metadata index (filter / rescore, not a neural model)**

- NanoDet class on the library item (already stored).
- Colour histogram (`appearance/rgb8@1`, already stored).
- Aspect / layout from existing bbox payloads.
- Optional later: logo or barcode as their own observation kind, still not identity.

These let the fuse/rerank stage filter or bonus without another forward pass.

### 3. Retrieve in parallel, then fuse

At query time:

1. Run NanoDet and OCR on the crop when those packs are ready.
2. Embed the full crop with DINOv2 patches. If detector confidence is high, embed the tighter object crop too.
3. Query the patch index with both visual embeddings.
4. Query BM25 with the crop text.
5. Query `search_object` with the detected class.
6. Optionally restrict or bonus by class / colour / layout.
7. Fuse the ranked lists with Reciprocal Rank Fusion at `media_id`.

Each hit keeps the bases that found it (`Similar look`, `Text in photos`, `COCO object detection (NanoDet)`). Primary chrome still names the door. A fused score is not a name and is not proof it is the same object.

Promote this path into Focus **Similar region**. Do not leave multi-leg recall only on screen-selection retrieval.

### 4. Rerank the top candidates

Take the top ~50 fused `media_id`s and rescore them with a cheap weighted sum, tuned on a small validation set (the existing photographic region eval plus a labelled text/object holdout).

Low-end-friendly terms:

- DINOv2 (or SigLIP if that pack is the one that is ready) similarity on the **detected object crop**, not the whole highlighted box.
- OCR token overlap (BM25 score or Jaccard on tokens).
- NanoDet class-consistency bonus.
- Colour histogram distance.
- Layout / aspect agreement from stored boxes.

This is not as strong as a new late-interaction model, but the visual term can reuse the patch scorer Semblon already runs. It fixes the cases where the highlighted box is larger than the object, or where text/class should break a visual tie.

Late-interaction beyond the current DINOv2 patch MaxSim (ColPali / ColQwen-style) stays **off** the default interactive path. It is an optional Max or offline mode if a GPU-class pack is present. It must not become the Balanced laptop path.

### 5. Latency budget (target, not a claim)

Interactive Similar region on a low-end Intel/AMD laptop, ONNX Runtime, Fast first look already on screen:

| Step | Budget | Already on `main`? |
|---|---|---|
| Crop | <10 ms | yes |
| NanoDet on the crop | 10–30 ms | pack exists; not on this door |
| OCR on a small crop | 50–200 ms | crop OCR exists; not fused on this door |
| DINOv2 1–2 crops | 30–100 ms typical after warm-up | one crop today |
| Exact derived / later ANN top-50 | 1–5 ms once the matrix is in memory | exact scan today; ANN still unwired |
| BM25 | <5 ms | no |
| RRF + lightweight rerank top-50 | 50–200 ms | no (union merge only) |
| Total interactive path | ~0.15–0.6 s after warm-up | Fast first look already splits this |

Show visual results immediately. Run **Name this area** only on button click. Balanced/Max refine may add detector + OCR + rerank without blocking the first look.

Full Google Lens parity on a low-end CPU laptop is not realistic. This structure should beat a single-vector crop search and stay responsive. It will be measured, not asserted.

---

## Accuracy: what actually improves it here

Biggest remaining gains, in order, after the work already on `main`:

1. **OCR + BM25 as a first-class recall channel** — text is the discriminative signal the visual encoder still drops (brands, labels, price tags).
2. **Query-time object crop + class** — compare the object, not the whole highlighted box; use the class as recall and as a rerank bonus.
3. **RRF + lightweight rerank** — stop asking incomparable scores to share a max.
4. **Keep DINOv2 patch late-interaction** — this already is the tile-level / local-layout leg. Do not discard it for a whole-image SigLIP vector.
5. **SigLIP as an optional second dense list** — better single-vector quality when the pack is present; never the only index; never an identity embedding.
6. **Heavier late-interaction reranker** — best extra accuracy, GPU-class cost, optional Max / offline only.

Do not spend the next slice swapping DINOv2 for SigLIP, NanoDet for YOLO11n, or Tesseract for PaddleOCR. Provider swaps are later BYO options behind the same probes.

---

## Ordered slices (one path each)

These are implementation slices on this decision. They are not a FACE-n, OBS, SIM, or VISION ticket queue.

| # | Slice | Lands in | Acceptance (evidence in BUILD-STATUS) |
|---|---|---|---|
| 1 | Query signals on Focus Similar region | `remember_and_find` / `find_similar_from_crop` | Highlight runs crop OCR + NanoDet when ready, in parallel with the visual embed. Missing pack ≠ failed search. No identity writes. Fast may skip them. |
| 2 | BM25 over stored OCR | `search_text` + derived sidecar | Token retrieval beats substring on a labelled text holdout. SQLite payloads stay authoritative. No new columns. |
| 3 | RRF fuse at `media_id` | `selection_retrieval` and the Focus region door | Independent ranked lists; per-hit bases kept; text-only still skips visual. |
| 4 | Lightweight rerank top ~50 | same merge path | Object-crop rescore + text overlap + class consistency + colour. Weights locked on a recorded eval. |
| 5 | Optional SigLIP second dense list | existing `embeddings` rows | Only when the SigLIP pack probes ready. Fused, not swapped. |
| 6 | ANN provider | `index_provider.active_vector_index` | Only after a measured exact-scan bottleneck on a large library. FAISS may appear as one provider. Chroma stays out. |

Slice 1 is the next code path. Do not start slice 6 first. Do not implement a parallel search stack.

---

## Explicit refusals

This decision **does not**:

- Adopt ChromaDB, or make FAISS/HNSW a product dependency.
- Replace the exact derived SQLite index with a vector database. Vector DB stays parked (`docs/SEM-ARCH-V1.4.md` §I.4).
- Invent schema columns, a discoveries table, or `embeddings.modality='face'`.
- Let objects, OCR, colour, SigLIP, or region scores vote on identity or change S1 thresholds.
- Put YOLO11n, PaddleOCR, Florence-2, or Moondream2 on the default path.
- Retune clustering, re-ingest the S1 golden dump, or silent-swap the identity engine.
- Resurrect Tk Home, `review-ui`, `canvas`, `lens_home`, or a second Application/storage path.
- Claim web identification, product names, landmarks, or species.
- Rewrite `docs/PRODUCT.md` to match work that has not landed.

ANN remains a named, disabled seam (`semblon/index_provider.py`). A later FAISS provider is allowed only behind that seam, only after measurement, and only as an approximate over the same SQLite embeddings.

---

## What success looks like

A person highlights a logo, a mug, or a labelled box. Semblon says what it can say (text, a detector class, or an unlabelled region). Other photos in *this* archive appear because visual patches, readable text, and object class agreed, or because one of those channels was strong and the others did not contradict it. Each result still shows where the match sits. A missing model, an unindexed photo, and a genuine empty match stay different outcomes. Identity stays a separate door.

Evidence for each slice is a command plus a BUILD-STATUS row. The photographic patch eval remains the visual regression. A new text/object holdout is required before claiming BM25 or rerank improved anything.
