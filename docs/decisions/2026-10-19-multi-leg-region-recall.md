# Design — multi-leg region recall

**Date:** 2026-10-19
**Status:** PLAN ONLY. No retrieval behaviour changes with this record.
**Base:** `main` at `86fdcbf` (merge of highlight-region similar search). Working tree was clean. This branch was cut from that commit.

This is the enhancement design for local, highlighted-region retrieval. It records what the code on that commit actually does, which part of a Lens-style pipeline is already present, and the smallest structural change that closes the remaining gap. It does not retune identity, add schema, or replace the PySide6 shell.

Product contract stays `docs/PRODUCT.md`. Landed behaviour stays `docs/BUILD-STATUS.md`. This file is not a second status board. `docs/BUILD-STATUS.md` is updated only when a later slice lands the behaviour.

## What the audit found

The pipeline on this commit is not crop → one OpenCLIP vector → ChromaDB top-k.

OpenCLIP ViT-B/32 still exists as an optional observer (`semblon/observers.py`, `CLIP_PACK = "clip/openclip-vitb32@1"`, `clip_embed`). Whole-image Similar may fall through to it only after the DINOv2 scene vector (`semblon/search.py`, `_WHOLE_MODALITY_RANK`: scene, then clip, then appearance). ChromaDB is not imported. FAISS is not a dependency. `semblon/index_provider.py` searches an exact derived matrix and states that an ANN provider is unwired until a measurement shows the library scan is the bottleneck. `docs/SEM-ARCH-V1.4.md` §I.4 parks a vector DB. SQLite embeddings stay authoritative (`semblon/ann_index.py`).

There are two retrieval doors. They do not share a ranker.

### Focus — Similar region

`ShellBridge` calls `Application.remember_and_find_region`, which calls `region_search.remember_and_find`.

1. The highlighted rectangle is cropped with `crop_bgr`. The box the user drew stays the box on screen.
2. A stored face box, a stored NanoDet label, or stored OCR that overlaps the box can label the selection (`describe_selection`). The local noun model is not on this path. **Name this area** (`name_selection`) is a separate call and does not choose matches.
3. Visual rank is `search_patches` when the DINOv2 pack is installed. The query crop is split into DINOv2 ViT-S/14 patch tokens (letterbox 224, ImageNet mean/std, L2, pack id ending `/patch`). Each query token takes its best cosine against that photo's stored content patches. The photo score is the mean of those maxima. A coverage floor drops photos whose tokens miss the token line. The match box is the union of the winning patches. Floors for Balanced, chosen on `docs/evidence/photo-region-eval.json`, are token cosine 0.35, mean score 0.28, coverage 0.28 (`semblon/similarity_profile.py`).
4. Text is a retrieval door only when the selection kind is `text` or `text_priority`. Otherwise a stored OCR string is understanding copy. The token kept is the single longest alphanumeric word of length at least 4 (`_text_query_token`). Lookup is `search_text`: a full scan of `observation_items.kind='text'` and a case-insensitive substring test.
5. If the patch map is absent, the fallback is one CLS vector of the whole crop against proposal rows (`modality='region'`). If the encoder fails or is not installed, the labelled fallback is a colour histogram (`Colour only`).
6. Balanced and Max publish a Fast first look, then replace it. Fast strides query tokens by 2 and tightens the floors. Cancel during refine keeps the first look.

Face rows are refused (`search_vector` raises if `modality == "face"`). The query does not write an embedding. Same face stays the other Focus door.

### What ingest already stores

`region_encoder.index_image_regions` writes, when the pack probes ready:

- one scene CLS (`modality='scene'`), which a region query does not scan;
- every content patch of the letterboxed frame (`modality='region_patch'`);
- the same patch split on up to eight extra windows (`patch_windows`: fractions 0.62 and 0.40, anchored at the corners, cap `MAX_PATCH_WINDOWS = 9` including the full frame);
- up to six proposal CLS crops (`proposal_boxes`: NanoDet boxes when that pack is installed, then contours).

A region query never scans scene vectors. The derived `.npz` matrix is not read by `search_patches`. That function loads every matching patch blob from SQLite and multiplies.

The window grid leaves a hole. A 0.40 window placed at 0 and at 60% of the side covers the corners and the edges. The band from 40% to 60% is outside those windows. The 0.62 windows and the full frame do cover the center, at coarser scale. A small object in the middle of a large photo is a few tokens of a 224 input, plus the 0.62 window. The window CLS that `content_patch_records` already computes for those tiles is discarded; only the patch tokens are stored.

Indexing cost on the landed note is up to nine ONNX passes per still. The encoder header records about two seconds for the first embed and under one second after that, on emulated x64. That is the interactive encode, before the library scan.

### Screen selection — a second fusion

`visual_query.run_visual_query` for a screen source calls `query_screen_with_image`, then `retrieve_selection`.

`query_image` walks `LENS_CAPABILITIES` in order: grounding (SAM 2 or the rectangle), barcode, Tesseract OCR, SigLIP `visual_embedding`, translation, VLM, then local knowledge packs. Those calls are sequential. The VLM runs before any archive retrieval. NanoDet is not in that capability list. Grounding observations are stored with `class: "region"`, and `selection_retrieval._OBJECT_SKIP_LABELS` drops `region`, so the object door usually has no class to search.

`retrieve_selection` then runs three doors and merges by `media_id`:

- region: `find_similar_crop` with empty observed text and kind `region`, so the visual door does not read the crop's text and does not tighten the box;
- text: Tesseract on the crop when the observations have no text, then a substring search per token;
- object: labels already present on the passed-in observations.

The merge keeps the higher raw score (`_add_hit`) and sorts by how many doors hit, then that score. A substring hit and a cosine are compared as if they shared a unit. Reciprocal rank fusion is not implemented.

### Measured impurity, and what that set cannot see

`docs/BUILD-STATUS.md` records the 16-image photographic run (`tools/eval_photo_regions.py`, exit 0). Viewpoint is a homography of the crop onto another photograph. Lighting is gamma plus a colour cast. The distractor is the crop's mean colour on another photograph.

| Query | Viewpoint rank | Lighting rank | Own colour distractor |
|---|---|---|---|
| chelsea | 1 (0.564) | 2 (0.546) | absent |
| clock | 1 (0.526) | 4 (0.501) | 6 |
| coins | 2 (0.424) | 1 (0.706) | absent |
| camera | 2 (0.613) | 1 (0.627) | absent |

Coins lighting had proposal IoU 0.0 and was still rank 1, so the patch map is doing the job proposal boxes cannot. Clock lighting is rank 4: other library photos sit between the two true hits. The colour distractor still enters the list. That set has no brand text and no same-class different-object pair, so it cannot measure a text leg or a class leg.

## Where a single vector still hurts, and where it does not

Layout inside the highlighted box is already a late-interaction score on DINOv2 tokens, not one averaged OpenCLIP vector. Replacing that score with one SigLIP vector would throw away the mechanism that placed coins lighting at rank 1 with proposal IoU 0.0. SigLIP remains the optional `visual_embedding` capability in `semblon/lens.py`. It is not the region ranker.

The gap that matches the Lens pattern is that Focus Similar asks that one visual score to do every job:

- Text in the box does not move the rank, except on an explicit text selection, and then only the longest token, unranked.
- A detector class does not move the rank. NanoDet runs at ingest and as a separate object search. It does not run on the query highlight to tighten the pixels that are embedded or to agree with the candidate's class.
- Colour is a substitute engine when DINOv2 is absent, not a small term on a visual candidate. That is why a mean-colour distractor can sit in the patch list with nothing to push it down.
- Several objects inside one box share one patch-mean. There is no second visual query on the dominant detected object.
- Late interaction is the first pass over every photo. There is no cheap candidate list and no second score on the top of that list. Cost grows with every stored patch. The exact derived matrix, which already exists, is unused here.
- The screen path inverts the latency order: VLM and the rest of the lens list run before the archive is searched. Focus already kept the noun model off the hot path. The screen path did not.

Those are structural. Swapping the detector for YOLO, the reader for PaddleOCR or Florence-2, or the index for FAISS HNSW does not fix them, and each of those swaps collides with a rule already on `main`.

## Out of this design

- FAISS, HNSW, Chroma, or any other vector database. Parked in SEM-ARCH §I.4. A later provider belongs behind `active_vector_index` after a timing run shows the exact scan, rather than the DINOv2 forward, dominating. ANN stays disabled in `index_seam_status`.
- A second detector. NanoDet is the pinned optional object model (`semblon/object_pack.py`). YOLO11n / YOLOv8n would be a second pack writing the same kind of label.
- A second OCR engine as the first change. Tesseract is the reader (`OCR_PROVIDER = "tesseract"`). A different reader is justified only after the same crops show a read-quality failure. The missing piece is ranked retrieval over the text already stored.
- ColPali / ColQwen on the click path. The click path already runs a patch MaxSim. The CPU-shaped use of late interaction is to run that MaxSim on a short candidate list, not to add a heavier token model in front of the library.
- VLM / Moondream on the default query. **Name this area** and `describe_vlm` stay button actions.
- New tables, new columns, `embeddings.modality='face'`, writes to `faces.person_id`, identity-threshold edits, public lookup, and downloads during search.
- Retuning 0.35 / 0.28 / 0.28 to make a fused list look better on the existing four queries. Those floors stay the visual-leg floors. Fusion weights come from a separate fixture.
- A claim of web-scale identification. Public lookup stays out of the product (`docs/decisions/2026-10-18-local-visual-discovery.md`).

Geometry, colour, objects, text, and region scores stay off the identity compare. `compare()` remains the face pack. `compare_space()` remains the non-identity path and still refuses `modality='face'`.

## Target path

One ranker for Focus Similar region and for screen selection. The rectangle on screen stays the user's rectangle. Detection chooses which pixels are embedded. It does not rename or replace the drawn box.

```
highlight
  ├─ NanoDet on the crop, when the pack probes ready
  │     top box inside the highlight + class, or no detection
  ├─ Tesseract on the crop, when the binary is on PATH
  │     every word with confidence ≥ 70 and length ≥ 4
  └─ DINOv2 patches of the highlight
        and, on Balanced and Max, of the tight box when detection is confident

recall, each list independent
  A. Visual candidates from search_patches
        Fast token stride, candidate cap about 50
        second list from the tight box when that box exists
  B. Ranked token overlap on stored OCR payloads
  C. Class list from stored NanoDet labels
        same label ranks; a missing pack omits the list

fuse the lists that actually ran (reciprocal rank fusion)
rerank the top of the fused list
publish that order, with each hit's bases preserved
```

A missing reader or a missing detector drops that list. It does not clear the visual hits. The source photo is excluded. Face embeddings are not read.

### Query signals

Run NanoDet and Tesseract on the crop at the start of the refine pass. Fast stays the visual first look that `remember_and_find` already publishes, so the strip can fill before OCR returns.

`NanoDetSession` already drops boxes below `prob_threshold` 0.35 before they are returned (`semblon/object_nanodet.py`). The ranker does not add a second cutoff. It takes the highest remaining box that lies inside the highlight. The tight crop is a second embedding, not a new user region. No box, or a pack that probes missing, leaves the highlight as the only visual query.

OCR keeps the word filter already in `_ocr_crop_text` (confidence ≥ 70, length ≥ 4) and stops collapsing to one longest token. Tokens are the text query. The product label for a text hit stays **Text in the selection**. The substring command used by explicit text search can remain; this ranker needs an ordered score.

### Recall

**Visual.** `search_patches` gains a candidate mode: the Fast stride, a wider cap, and the existing floors used only as a candidate cut. The published order is the rerank, not this cut. The second visual list, when a tight box exists, is the same function on that crop. Both lists stay on `region_patch` and the pinned pack id. Scene rows stay unscanned.

**Text.** Score stored OCR by token overlap, computed from the rows `search_text` already scans. A photo that contains more of the query tokens ranks above a photo that contains one shared word. A single implementation can use Okapi BM25 over those tokens, or the overlap fraction `|query ∩ document| / |query|` with a length penalty. Either one is a ranked score. A substring hit is not score 1.0. No new column. If a later timing run shows the full text scan dominating, the postings can be a derived sidecar beside the store, rebuilt from SQLite, on the same pattern as `{store}.semblon-index.npz`. SQLite remains authoritative.

**Class.** `search_object` already matches NanoDet labels and ignores contour `class=region`. For the ranker, the query class is the detection on the crop, and the list is photos that stored that label. The list is capped. It is a vote, not a dump of every photo of that class into the strip.

### Fusion

Reciprocal rank fusion over the lists that returned rows:

`score(photo) = Σ 1 / (k + rank_in_list)`

with `k = 60`, ranks starting at 1. A photo missing from a list contributes nothing from that list. Raw cosines are not compared with substring flags. The fused order is the candidate order for the rerank. Each surviving hit keeps the bases that nominated it, so the strip can still say Similar look, Text in the selection, or the NanoDet basis.

`selection_retrieval._add_hit` (max of incomparable scores) stops being the screen ranker. Screen selection calls this same function. `query_image` for that path does not run `vlm`, translation, or knowledge lookup before retrieval. Those stay available on the describe action.

### Rerank

Rescore the top of the fused list, on the order of 50 photos, and publish that order. Terms, all in `[0, 1]` before weighting:

| Term | Source | Role |
|---|---|---|
| Patch MaxSim | full stride, tight crop when one exists, otherwise the highlight | main visual score; current Balanced floors still describe this space |
| Token overlap | fraction of query tokens present in that photo's stored OCR | text evidence on the candidate, not a second library scan story |
| Class agreement | 1 when both sides have a NanoDet label and they match, 0 when both exist and differ, omitted when either side has no label | stops a shared class from being mandatory and stops a clash from being invisible |
| Colour | cosine of `color_histogram` on the query crop and on the match box | small tie-break; the term that let clock's mean-colour distractor in must not be able to lead the list alone |

Weights are not chosen in this document. They are fit on the fixture below and written down with that run. Until that run exists, implementation uses equal weights on the terms that are present and records them as untuned. A colour-only lead is rejected by a cap: the colour term's maximum contribution stays below the gap between rank 1 and rank 2 of a pure patch ordering on the existing four queries. That cap is checked in the regression, not assumed.

The rerank reads patches for those candidates only. It does not open a new model. It does not write the query vector.

### Finer windows

The center hole in `patch_windows` is real, and the cap is already nine forwards. Adding a center 0.40 window is a tenth forward, or it replaces a corner window. That change waits on an index-time measurement on the 16-image run: seconds per still, patch-row count, and whether the four photographic queries move. It is not part of the fusion slice. The window CLS that is computed and dropped can later be stored as another non-face modality value on the existing `embeddings` table (no new column) and used as an exact shortlist in front of MaxSim. That shortlist is also later, and only after the fusion slice is measured. It is still an exact scan behind `active_vector_index`. It is not ANN.

### Latency, in the units this tree has

The 0.15–0.6 s budget assumes an INT8 SigLIP forward and an ANN probe. This tree's region forward is about one second after warmup on emulated x64, and the patch scan loads every `region_patch` row. This design does not promise that budget.

What it does specify:

| Step | Where it sits |
|---|---|
| Crop | unchanged, before either pass |
| Fast patch list | first look, already published |
| NanoDet on the crop, Tesseract on the crop | refine pass, skipped when the pack or the binary is missing |
| Second DINOv2 forward on the tight box | Balanced and Max only |
| Text overlap and class list | in memory over rows already stored |
| RRF and rerank | the fused head, not the library |

Cancel during refine keeps the first look. An empty refine keeps the first look. Both are the current `remember_and_find` contract.

### Accuracy order for this codebase

1. Let OCR tokens and the detector class vote on the Focus rank. This is the missing leg. The current photo set cannot see it.
2. Rerank the fused head with tight-crop MaxSim, token overlap, class agreement, and a capped colour term.
3. Close the center-window hole only if the index measurement says the extra forward is cheap enough and the four queries do not regress.
4. Leave SigLIP, FAISS, YOLO, PaddleOCR, Florence-2, and ColPali out until that fused DINOv2 rank has been measured and still fails.

### Eval

Keep `tools/eval_photo_regions.py` as the visual regression. Report the same four queries, the same floors, and the colour-distractor ranks before and after. A fused run that buries chelsea, clock, coins, or camera, or that promotes the clock colour distractor above rank 6, fails.

Add a second fixture, its own file, that the photo set does not cover: repeated readable text (a brand or label) on one object, the same object without that text, and a same-class different object. Record:

- rank of the labelled twin when the query crop contains the text;
- rank of the same-class distractor;
- the visual order when OCR returns no tokens, which must match today's patch order on that fixture.

Unknown stays a valid result. A confident text read is allowed to move a photo up. A failed or empty read must not.

Identity tests stay as they are. Region search still refuses face modality. No test writes `faces.person_id`.

## Implementation slices

This record is the design. Each slice is a later branch.

1. **Recall fuse.** Query-time NanoDet and Tesseract tokens inside the refine pass of `remember_and_find`. Ranked text overlap. Class list. Reciprocal rank fusion. Screen selection calls that ranker and does not run the VLM first. Tests around `tests/test_region_search.py`, `tests/test_local_lens.py`, and the selection-retrieval tests.
2. **Rerank.** Top-of-list rescore with the four terms. Weights written down from the new fixture. Visual regression on the four photographic queries.
3. **Window coverage.** Center window or stored window CLS, only with the index measurement above. Default cap stays 9 until that measurement is in `docs/BUILD-STATUS.md`.

Files slice 1 is expected to touch: `semblon/region_search.py`, `semblon/selection_retrieval.py`, `semblon/search.py`, `semblon/visual_query.py`, and the tests named above. It does not touch schema, `identity_config`, FaceKit, the ANN flag, pack pins, or shell chrome. The refine phase label already exists.

## Bottom line

On `main` at `86fdcbf`, Similar region embeds the highlighted crop with DINOv2 and scores every stored content patch by late interaction. OpenCLIP is a whole-image fallback. Chroma and FAISS are unwired. Text and object class are separate doors, and the screen door merges them by comparing a cosine with a substring flag.

The enhancement is to retrieve from those doors independently, fuse the ranks, and rerank a short head with the object crop, the text overlap, the class, and a capped colour term. The pinned region encoder stays the visual score. The describe model stays on the button.
