# Decision — local Lens-style retrieval is a ranking system, not a model swap

**Date:** 2026-10-19  
**Status:** current — interactive path **IMPLEMENTED** (query spec, BM25, RRF, feature rerank, part/word chrome, after-grid match check). Heavy VLM/ColQwen and ANN remain off the path.  
**Branch:** `cursor/lens-retrieval-strategy-1388` (cut from `origin/main` `86fdcbf`)  
**Related:** `docs/PRODUCT.md`, `docs/BUILD-STATUS.md`, `docs/ROADMAP.md`, `docs/SEM-ARCH-V1.4.md`, `docs/decisions/2026-10-18-local-visual-discovery.md`, `docs/REGION-PACK.md`, `docs/OBJECT-PACK.md`

This is the enhancement strategy for “point, understand, and find.” It does not reopen `docs/ARCHITECTURE.md`, identity thresholds, or the identity firewall. Geometry, colour, objects, text, language vectors, and region matches still do not write `faces.person_id` or `embeddings.modality='face'`.

---

## Verdict

Semblon already has two of the three recall legs: DINOv2 patch late-interaction (appearance) and OCR / NanoDet (text and class). A near-exact local Lens is not one more model swap. It is four functions on those legs:

```text
1. Region decomposition — what part of the highlight did the user mean?
2. Multi-modal recall     — appearance, language, and text in parallel
3. Fuse + rerank          — RRF, then rescore the top candidates
4. Refinement loop        — a query spec the user can change
```

End-to-end:

```text
User highlight
   │
   ├─ cheap detect / optional Grounded SAM 2 → object, part, text-block regions
   ├─ OCR → strings + boxes
   └─ optional caption / attributes (async; not a product name)
          │
          ▼
   Query spec: {region, object_crop, text, attributes, doors, modifiers}
          │
   ┌──────┼──────────────┬────────────────┐
   ▼      ▼              ▼                ▼
 DINOv2  SigLIP        BM25 over OCR    SigLIP text of
 patch   image +       (stored text)    caption / attributes
 late    object crop
   │      │              │                │
   └──────┴──────┬───────┴────────────────┘
                 ▼
            RRF fusion → top-20
                 │
                 ▼
       Feature rerank now; optional VLM judge async
                 │
                 ▼
          Result grid + refinement (other part / modifier / door)
```

Do not collapse this into one crop vector. Do not replace DINOv2 with SigLIP. You need both: DINOv2 wins on the same object at another angle; SigLIP wins on “same kind, different instance.”

---

## What “near-exact local Lens” means

Google Lens is a pipeline, not a retrieval model. Locally, “near-exact” means those four functions on **this** archive. It does not mean Google’s web index, shopping graph, or freshness.

| Function | Lens does | Semblon on `main` | Gap |
|---|---|---|---|
| Region decomposition | object / part / logo / text inside the highlight | User box, stored face / NanoDet / OCR boxes, optional SAM 2 mask of the whole crop | No open-vocab part split. No “search the logo, not the shirt.” |
| Multi-modal recall | appearance + language + text in parallel | DINOv2 patches + OCR substring + NanoDet class. SigLIP exists as an optional embed / naming probe, not a recall door. | No language-aligned door. Focus Similar region still runs appearance only. |
| Fuse + rerank | RRF then cross-encoder / judge | Union by `media_id`, max score, bonus for more bases | No RRF. No rerank. |
| Refinement | “this part,” “similar but red,” exact vs category | Fast / Balanced / Max are latency profiles. Separate doors exist (Similar region, Same face, Whole photo, Duplicates). | No query spec. No text modifier. No exact-instance vs same-kind toggle. |

SightRAG and similar local visual-RAG stacks are **references for orchestration** (detect → embed → index → retrieve, OCR + optional Grounding DINO, ONNX). They are not a second product stack. Do not import FastAPI, Chroma, or their application boundary.

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
| No language channel | `lens.embed_siglip` and `visual.naming.siglip` are optional probes. They do not run as a Focus recall door. |
| No merge | Screen-selection retrieval already runs region + text + object and merges by `media_id`. Focus **Similar region** still does not. |

Citations on `main`:

- Dense visual: `semblon/region_search.py`, `docs/REGION-PACK.md`, `docs/evidence/photo-region-eval.json`
- Index seam: `semblon/index_provider.py` (ANN unwired; FAISS/Chroma refused until a measured bottleneck)
- Multi-door merge: `semblon/selection_retrieval.py` (union by photo; max score; bonus for more bases)
- Focus door: `Application.remember_and_find_region` → `region_search.remember_and_find` (visual first; text is a door only when the selection is text-priority)
- SigLIP probe: `semblon/lens.py` `embed_siglip` / `probe_siglip`; naming in `semblon/visual/naming_local.py`
- SAM 2: `semblon/sam2_runtime.py`, `lens.ground_selection` (mask of the crop, not open-vocab parts)
- Identity firewall: Face Similar stays a separate door (`search_similar_faces`)

Milestone 2 on the photographic set stays **VERIFIED**. This decision does not reopen that gate. It names the quality gap that remains after it.

---

## Why the current structure still underperforms Lens

The remaining weakness is not “we picked the wrong single vector.” Two recall legs exist and the product door still treats one of them as the search.

1. **Focus Similar region is one visual leg.** `remember_and_find` embeds the highlighted box (patch late-interaction when the pack is ready) and only falls through to colour. Stored OCR and NanoDet labels are understanding, not recall, unless the selection is text-priority.
2. **There is no language-aligned door.** DINOv2 is an appearance matcher. It cannot answer “other chairs like this one” when the other chair is a different instance. SigLIP (or SigLIP-2) is the missing third recall leg: image + object crop + text embeddings of caption / attributes.
3. **The highlight is not decomposed.** The user box is the query. There is no “the logo / the handle / the text block” split, so a shirt search averages away the mark on it. SAM 2 can mask the whole crop; it does not propose parts.
4. **Query understanding is incomplete on the crop.** Crop OCR exists. Query-time NanoDet on the highlight does not. There is no high-confidence tighter object crop used as a second visual query. Caption / attributes, when they exist, name the area; they do not expand the query.
5. **Text recall is substring, not tokens.** `search_text` requires the query string to appear inside the stored payload. Brand fragments, OCR noise, and word order miss.
6. **Fusion is a union, not rank fusion.** `selection_retrieval._merged` groups by `media_id`, keeps the max score, and prefers hits that appeared on more doors. Scores from cosine, substring, and class match are not comparable.
7. **There is no rerank stage.** Nothing rescores the top fused candidates against the original region.
8. **Search is one-shot.** Fast / Balanced / Max change floors and limits. They are not a refinement loop (other part, text modifier, exact-instance vs same-kind).

---

## Target architecture (mapped onto Semblon)

Keep the production path: PySide6 `semblon shell` → `Application` → domain / storage / providers. No second shell. No new schema columns. No vector database as a product dependency. No FastAPI orchestration layer.

### 0. Query spec

Retrieval accepts a specification, not a raw crop:

| Field | Meaning |
|---|---|
| `region` | The active box or mask (user highlight, or one proposed part) |
| `object_crop` | Tighter crop when a detector is confident |
| `text` | OCR strings from that region |
| `attributes` | Honest local tokens (colour, material, category, style). Not a product, landmark, or species name. |
| `doors` | Which recall legs to run |
| `modifiers` | Extra text (“red”, “wooden”, “same brand”) folded into BM25 and SigLIP text |
| `mode` | `exact` (DINOv2 up, SigLIP down) or `kind` (SigLIP + attributes up, DINOv2 down) |

This lives on `Application`, same session. It is not a hidden model picker. The shell shows the choices as “this part,” “same look,” “same kind,” and a modifier field.

Fast / Balanced / Max stay latency profiles. They do not replace the query spec.

### 1. Query understanding — decompose the highlight

When the user highlights a box, do not pass the whole crop to one model and hope. Run cheap extractors in parallel. Heavy captioning is async and must not block the first grid.

| Signal | Semblon provider | Output | Notes |
|---|---|---|---|
| Closed-set object | NanoDet BYO (`docs/OBJECT-PACK.md`) | main class + box, when confidence is high | Default cheap detector. YOLO11n is **not** a required swap. |
| Open-vocab parts | Optional Grounding DINO + existing SAM 2 (`sam2_runtime`, `lens.ground_selection`) | top-3 boxes/masks inside the highlight (“object”, “part”, “text block”) | Run **only on the user highlight**, only top-3. Missing pack = no parts, search the user box. Do not library-wide segment. |
| OCR | Tesseract BYO (`probe_ocr_status`) | strings + boxes | PaddleOCR / Florence-2 OCR is **not** a required swap. |
| Caption / attributes | Existing **Name this area** / local noun / optional Florence-2 or Qwen2-VL-2B | short caption + attribute tokens | Query expansion only. A local model does not invent a product, landmark, or species (`docs/PRODUCT.md`). Async. Not the default first-grid blocker. |
| Visual embed | DINOv2 ViT-S/14 + optional SigLIP | patch tokens of the full crop, the object crop, and (when a mask exists) the masked object | SigLIP does not replace DINOv2. |

Do not put Moondream, ColQwen, or **Name this area** on the blocking path. Describe / name stays a button. Caption tokens may join a later refine pass when that pack is ready.

### 2. Recall doors — offline indexes, derived from the store

The library is not a flat Chroma collection. It must not become one.

**A. Appearance — DINOv2 `region_patch` (exists; keep)**

- Engine: DINOv2 ViT-S/14 ONNX, `modality=region_patch`, pack id ending `/patch`.
- Compare: late interaction (mean of each query patch's best cosine in the other photo). Match box = union of winning patches.
- This already is the tile-level / local-layout / exact-instance leg. Do not add a second 1024×1024 tile index on top of it until a measurement says otherwise.
- Interactive multi-vector scorer. ColQwen / ColPali stays off this path (see §3).

**B. Language — SigLIP / SigLIP-2 (the biggest missing leg)**

- Engine: existing SigLIP ONNX probe (`lens.embed_siglip`, `SEMBLON_SIGLIP_ONNX`) or a later SigLIP-2 / SO400M BYO pin. INT8 ONNX, `CPUExecutionProvider`.
- Store: existing `embeddings` rows (`modality` already used for `siglip` / `clip` / `scene`). No new columns. Never `modality='face'`.
- Granularity: embed the full highlight, the detected object crop, and optionally the masked object (background zeroed in memory). Do not embed only one crop.
- Query expansion: embed the caption and each attribute / modifier with the **same** SigLIP text encoder. That is text-controllable retrieval without a separate text-to-image model.
- Index: exact derived matrix first (`index_provider.active_vector_index`). FAISS HNSW is allowed later only as one ANN provider behind that seam, only after a measured exact-scan bottleneck. Chroma stays out.

This is the door that makes “similar but red” and “same category, different instance” possible. DINOv2 still wins on “same object, different angle.”

**C. Sparse text — BM25 over stored OCR (upgrade)**

- Offline: OCR already writes `observation_items kind=text`.
- Query: OCR of the active region, plus attribute / modifier tokens.
- Recall: BM25 over those payloads. No new table. Sidecar rebuildable from SQLite, same pattern as `ann_index`.

**D. Cheap metadata (filter / rescore)**

- NanoDet class, colour histogram (`appearance/rgb8@1`), aspect / layout from existing bbox payloads.
- Optional later: logo or barcode as their own observation kind, still not identity.

### 3. Multi-stage ranking

Do not skip the second stage. Doors are not calibrated to each other; do not average raw scores.

**Stage 1 — parallel recall (interactive)**

- DINOv2 patch late-interaction → top-50
- SigLIP image (highlight + object crop) → top-50, when the pack is ready
- BM25 over OCR → top-50, when text exists
- Optional: SigLIP text of attributes / modifiers → top-50
- NanoDet class search remains a cheap extra list

**Stage 2 — fuse**

- Reciprocal Rank Fusion at `media_id`.
- Each hit keeps the bases that found it. A fused score is not a name and is not proof it is the same object.
- Promote this into Focus **Similar region**. Do not leave multi-leg recall only on screen-selection retrieval.

**Stage 3 — rerank (semi-interactive / async)**

- Take the top-20 fused candidates.
- **CPU default:** feature ranker over SigLIP similarity on the object crop, DINOv2 patch score, OCR token overlap, class consistency, colour histogram, layout. A hand-weighted sum first; a logistic / GBDT ranker once a labelled set exists. Even a few hundred labelled queries beat hand-tuned RRF weights.
- **Optional async judge:** a small VLM (Qwen2-VL-2B or Florence-2) that sees the original highlight and the candidate and scores same-object / same-kind / same-part. Reorders the grid in place after first render.
- **Not in the interactive path:** ColQwen2.5 / ColPali-family (3B-class, ~4 GB VRAM, ~100× slower on CPU). Offline index of a high-value subset, or optional Max / high-accuracy mode after the first grid. DINOv2 patch late-interaction remains the interactive multi-vector scorer.

### 4. Refinement loop

After the first grid the user can:

- select a different detected region (the logo instead of the shirt);
- add a text modifier (“red”, “wooden”, “same brand”);
- switch to **same look** (exact-instance: DINOv2 up, language door down);
- switch to **same kind** (semantic: SigLIP + attributes up, DINOv2 down).

The orchestration re-queries from the query spec. This is the difference between a search box and Lens. Face Similar stays its own door and is not a refinement of region search.

### 5. Latency budget (target, not a claim)

Never block the first grid on a 3B VLM. Render the fused top-20, then let a reranker reorder.

| Step | Budget | Already on `main`? |
|---|---|---|
| Crop | <10 ms | yes |
| NanoDet on the crop | 10–30 ms | pack exists; not on this door |
| Grounding DINO + SAM 2 on highlight, top-3 | 50–150 ms | SAM 2 optional; Grounding DINO not present; not on this door |
| OCR on a small crop | 50–200 ms | crop OCR exists; not fused on this door |
| Florence-2 / Qwen caption | 200–500 ms **async** | Name this area is a button |
| DINOv2 1–2 crops | 30–100 ms after warm-up | one crop today |
| SigLIP image 1–2 crops | 30–80 ms | probe exists; not a recall door |
| Exact derived / later ANN top-50 | 1–5 ms in memory | exact scan today; ANN still unwired |
| BM25 | <5 ms | no |
| RRF + feature rerank | 30–100 ms | union merge only |
| First grid | ~0.2–0.5 s after warm-up | Fast first look already splits this |
| VLM judge top-20 | 0.5–2 s **async** | no |

Full Google Lens parity on a low-end CPU laptop is not realistic. This structure should beat a single-vector crop search and stay responsive. It will be measured, not asserted.

---

## Accuracy: what actually improves it here

Biggest remaining gains, in order, after the work already on `main`:

1. **Language-aligned SigLIP door** — the missing third recall leg. Same kind, different instance; text-controllable modifiers.
2. **Highlight decomposition** — search the logo, not the shirt. NanoDet + optional Grounded SAM 2 on the user box only.
3. **OCR + BM25** — brands, labels, price tags the visual encoder drops.
4. **Wire the legs you have onto Focus Similar region** — appearance + text + class must actually run on the product door.
5. **RRF + feature rerank, then an optional async judge** — stop asking incomparable scores to share a max; rescore against the original region.
6. **Refinement query spec** — the interaction that makes it feel like Lens.
7. **Keep DINOv2 patch late-interaction** — exact-instance / local layout. Do not discard it for a whole-image SigLIP vector.
8. **ColQwen-class late-interaction** — best extra accuracy, GPU-class cost, Max / offline only.

Do not spend the next slice swapping DINOv2 for SigLIP, NanoDet for YOLO11n, Tesseract for PaddleOCR, or SAM 2 for a library-wide segmenter. Provider swaps are later BYO options behind the same probes.

---

## What “near-exact” still cannot match locally

A local pipeline can match Lens on region understanding, multi-modal recall, ranking, and refinement UX. It cannot match Lens on:

- **Web-scale index.** Semblon searches this person’s archive. Public lookup stays out of the product (`docs/PRODUCT.md`).
- **Shopping / SKU graph.** Exact-product matching needs a catalog Semblon does not have. A local model must not invent a product name.
- **Continuous freshness.** There is no remote index to refresh.

For a personal library, Lens-style interaction and ranking is the target. For open-world arbitrary images, no local system matches Google’s index. Do not claim otherwise.

---

## Eval harness — before tuning

The photographic patch eval (`docs/evidence/photo-region-eval.json`, `tools/eval_photo_regions.py`) stays the appearance regression. It is not enough for “near-exact.”

Add tuples `(highlight, relevant media_ids, hard negatives)` that cover:

- same object, different viewpoint / lighting (already present);
- same kind, different instance (language door; DINOv2 should not be the only scorer);
- logo / part vs whole object (decomposition);
- readable brand / label (BM25);
- hard negatives that are visually close and semantically wrong (DINOv2 will return these confidently).

Do not tune RRF weights, GBDT, or floors until that harness exists. Do not retune S1 identity constants. Do not print precision without `--eval-set confirmatory` where that flag applies.

---

## Ordered slices (one path each)

These are implementation slices on this decision. They are not a FACE-n, OBS, SIM, or VISION ticket queue.

| # | Slice | Lands in | Acceptance (evidence in BUILD-STATUS) |
|---|---|---|---|
| 1 | Query spec + existing doors on Focus Similar region | `Application`, `remember_and_find`, `selection_retrieval` | **IMPLEMENTED.** Highlight runs DINOv2 + crop OCR + NanoDet when ready. Spec carries region / doors / modifiers. Missing pack ≠ failed search. Fast may skip extras. No identity writes. |
| 2 | Language-aligned SigLIP door | `lens.embed_siglip`, existing `embeddings` `modality=siglip` | **IMPLEMENTED** as an optional door. Missing pack is skipped. Not a DINOv2 swap. |
| 3 | Highlight decomposition | NanoDet on the crop + stored boxes | **IMPLEMENTED** for top-3 parts plus Whole area. Grounding DINO still optional later. |
| 4 | BM25 over stored OCR | `search_text` + `text_index` | **IMPLEMENTED** in memory from SQLite payloads. No new columns. |
| 5 | RRF fuse at `media_id` | `selection_retrieval` and the Focus region door | **IMPLEMENTED.** Independent ranked lists; per-hit bases kept; text-only still skips visual. |
| 6 | Feature rerank top-20 | same merge path | **IMPLEMENTED** as a weighted sum. Learned GBDT still later. |
| 7 | Refinement UI | Focus | **IMPLEMENTED.** Part picker, text modifier, Same look / Same kind. No model names. |
| 8 | Async match check | refine pass after the first grid | **IMPLEMENTED** as a colour + local pixel-describer reorder. VLM/ColQwen stay off the blocking path. Phase: Checked the matches. |
| 9 | ANN provider | `index_provider.active_vector_index` | **NOT STARTED.** Only after a measured exact-scan bottleneck. |

Slice 1 is the next code path (use the legs already on disk). Slice 2 is the highest-leverage *new* capability. Start the eval harness as soon as slice 2 has a list to score. Do not start slice 9 first. Do not implement a parallel search stack.

---

## Explicit refusals

This decision **does not**:

- Adopt ChromaDB, or make FAISS/HNSW a product dependency.
- Replace the exact derived SQLite index with a vector database. Vector DB stays parked (`docs/SEM-ARCH-V1.4.md` §I.4).
- Invent schema columns, a discoveries table, or `embeddings.modality='face'`.
- Let objects, OCR, colour, SigLIP, SAM 2, language vectors, or region scores vote on identity or change S1 thresholds.
- Put YOLO11n, PaddleOCR, Florence-2, Qwen, Moondream2, or ColQwen on the **blocking** first-grid path.
- Require Grounding DINO or library-wide segmentation.
- Copy SightRAG, AURA, or any FastAPI / second application boundary.
- Claim web identification, product names, landmarks, species, or SKU matching.
- Retune clustering, re-ingest the S1 golden dump, or silent-swap the identity engine.
- Resurrect Tk Home, `review-ui`, `canvas`, `lens_home`, or a second Application/storage path.
- Rewrite `docs/PRODUCT.md` to match work that has not landed.

ANN remains a named, disabled seam (`semblon/index_provider.py`). A later FAISS provider is allowed only behind that seam, only after measurement, and only as an approximate over the same SQLite embeddings.

---

## What success looks like

A person highlights a shirt with a logo. Semblon can offer the logo as a part. They search that part. Other photos in *this* archive appear because appearance patches, language similarity, readable text, or object class agreed — or because one channel was strong and the others did not contradict it. They can then say “same kind” or add “red” and the query spec runs again. Each result still shows where the match sits. A missing model, an unindexed photo, and a genuine empty match stay different outcomes. Identity stays a separate door.

Evidence for each slice is a command plus a BUILD-STATUS row. The photographic patch eval remains the appearance regression. Language, part, and hard-negative tuples are required before claiming SigLIP, BM25, or rerank improved anything.
