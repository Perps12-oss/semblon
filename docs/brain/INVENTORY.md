# BRAIN capability inventory (Increment 1)

**Status:** Complete for C1–C9 against live code on branch `grok/p2-decision-erasure`.  
**Freeze note:** P1a base `c6fc730`; inventory read at HEAD of this branch (schema 8 → 9).  
**Latency / coverage:** fixture / `UNMEASURED` this session — no owner 100-image sample. Harness is ready to fill numbers later.  
**Adoption rule:** `adopted=1` only after §6 gates + `brain_benchmarks` row. Inc 1 adopts **zero** new models.

| Field | Meaning |
|---|---|
| Existing provider | Module / function that already does this, or `NONE` |
| Input / output | What it consumes and produces |
| Embedding pack | Pack id / hash, dim, dtype, normalisation — or `n/a` |
| Latency (p50/p95) | Measured on a 100-image sample, or `UNMEASURED` |
| Coverage | Fraction successfully processed, or `UNMEASURED` |
| Quality signal | If measurable, else `UNMEASURED` / `n/a` |
| Reusable? | `YES_REUSE` / `YES_WRAP` / `NO_DUPLICATE` |
| Inc 1 adoption | Recommendation for this increment |

---

## Summary — Inc 1 adoption board

| ID | Capability | Existing | Candidate (dormant) | Inc 1 `adopted` |
|---|---|---|---|---|
| C1 | `tag_generic` | NanoDet COCO labels (+ optional CLIP item) | `ram_plus` | **0** — baseline only |
| C2 | `localise_object` | NanoDet bbox (+ optional SAM2 mask/box) | `grounding_dino` | **0** — baseline only |
| C3 | `embed_object` | `region_encoder` DINOv2 CLS | — | **0** — reuse path; no new model |
| C4 | `embed_face` | YuNet+SFace (`yunet_sface`) | `adaface_ir18` | **0** — baseline only |
| C5 | `cluster_vectors` | `cluster.py` DBSCAN | `hdbscan` | **0** — baseline only |
| C6 | `search_similar` | `index_provider` exact-derived | — (FAISS out until ANN gate) | **0** — reuse path |
| C7 | `verify_same_instance` | `compare.py` / `compare_space` | — | **0** — reuse path |
| C8 | `scene_classify` | DINOv2 `scene` **embedding** (not a classifier) | — | **0** — wrap; labels via graph later |
| C9 | `ocr` | `observers.ocr_image` (tesseract) | — | **0** — reuse or defer if unavailable |

**Inc 1 outcome:** `adopted=1` count = **0**. Success condition met: inventory complete, baselines registered dormant, no candidate loaded.

---

## C1 — `tag_generic(photo)`

| Field | Value |
|---|---|
| Existing provider | `semblon.object_nanodet.detect_objects` → COCO-80 class labels; optional `semblon.observers` CLIP item (`clip/openclip-vitb32@1`) as non-identity observation |
| Module entry | `semblon.object_nanodet`, `semblon.object_pack` (`PROVIDER=opencv-zoo-nanodet`); category door `semblon.category_backfill` Objects |
| Input / output | BGR image → `list[{label, score, bbox, ...}]`; CLIP path → embedding item, not open-vocab tags |
| Embedding pack | n/a for NanoDet labels; CLIP `clip/openclip-vitb32@1` when that observer runs |
| Latency (p50/p95) | `UNMEASURED` |
| Coverage | `UNMEASURED` (pack BYO; probe fails closed if missing) |
| Quality signal | `UNMEASURED` (COCO closed vocab — not open-tag F1) |
| Reusable? | `YES_WRAP` |
| Inc 1 adoption | **`adopted=0`** for `existing_nanodet_tags` (baseline). **`adopted=0`** for candidate `ram_plus`. Do not re-implement tagging. |

---

## C2 — `localise_object(photo, tag)`

| Field | Value |
|---|---|
| Existing provider | NanoDet returns per-detection bboxes for COCO classes; `semblon.sam2_runtime.predict_box` / `generate_regions` refine or propose regions when SAM2 pack present |
| Module entry | `semblon.object_nanodet.detect_objects`; `semblon.sam2_runtime`; Focus/Lens paths in `semblon.lens` / `semblon.visual_segment` |
| Input / output | Image (+ optional prompt box) → bbox / mask regions. NanoDet is class-conditioned among COCO-80, not free-text Grounding DINO |
| Embedding pack | n/a |
| Latency (p50/p95) | `UNMEASURED` |
| Coverage | `UNMEASURED` |
| Quality signal | `UNMEASURED` |
| Reusable? | `YES_WRAP` |
| Inc 1 adoption | **`adopted=0`** baseline `existing_nanodet_localise` (+ optional `existing_sam2`). **`adopted=0`** for `grounding_dino` (explicitly not required per `docs/SHIP-GATES.md`). |

---

## C3 — `embed_object(region)`

| Field | Value |
|---|---|
| Existing provider | `semblon.region_encoder` DINOv2 ViT-S/14 ONNX CLS for crop / region |
| Module entry | `semblon.region_encoder`; persisted via `embeddings` with `modality=region` / `region_patch` |
| Input / output | Crop / window BGR → float32 L2 CLS vector |
| Embedding pack | `region/dinov2-vits14@1/<sha16>/cls` family; weight SHA-256 `f22797eabf810a75e41de68d378541ebea372122b25c4ce3ef25ff618250c20a`; dim **384**; dtype float32; **L2** |
| Latency (p50/p95) | `UNMEASURED` this session (module notes ~2s first / &lt;1s warm on emulated x64 — not a 100-image sample) |
| Coverage | `UNMEASURED` |
| Quality signal | Prior glyph eval in `docs/evidence/visual-discovery-eval.json` (not owner-photo Inc 1 baseline) |
| Reusable? | `YES_REUSE` |
| Inc 1 adoption | **`adopted=0`** register `existing_region_encoder` as baseline only. No candidate. Never duplicate DINOv2 for the same crop. |

---

## C4 — `embed_face(region)`

| Field | Value |
|---|---|
| Existing provider | YuNet detect + SFace recognise (production FaceKit path) |
| Module entry | `semblon.identity_config` (`PACK_FAMILY=opencv/yunet_sface`); persist on `faces.embedding`; gate `semblon.compare.validate_identity_embedding` |
| Input / output | Aligned face crop → float32 L2 identity vector on `faces.*` only |
| Embedding pack | `opencv/yunet_sface@…/sha256:…`; dim **128**; dtype float32; **L2** (fail-closed) |
| Latency (p50/p95) | `UNMEASURED` |
| Coverage | `UNMEASURED` |
| Quality signal | Q-gate **OPEN** (`identity_config` thresholds provisional) |
| Reusable? | `YES_REUSE` |
| Inc 1 adoption | **`adopted=0`** baseline `existing_face_embedder`. **`adopted=0`** candidate `adaface_ir18`. Must call `validate_identity_embedding` on every future face observation. |

---

## C5 — `cluster_vectors(vectors)`

| Field | Value |
|---|---|
| Existing provider | `semblon.cluster.cluster_run` — DBSCAN on ok face embeddings (`1-dot` metric) |
| Module entry | `semblon.cluster`; eps/min_samples from `identity_config` |
| Input / output | Face embedding set for a run → cluster labels (clusters ≠ persons) |
| Embedding pack | Uses face pack of the run; clustering itself emits no pack |
| Latency (p50/p95) | `UNMEASURED` |
| Coverage | `UNMEASURED` |
| Quality signal | `UNMEASURED` |
| Reusable? | `YES_REUSE` |
| Inc 1 adoption | **`adopted=0`** baseline `existing_dbscan`. **`adopted=0`** candidate `hdbscan`. No re-implementation of face clustering. |

---

## C6 — `search_similar(vector, k)`

| Field | Value |
|---|---|
| Existing provider | `semblon.index_provider.active_vector_index` → `ExactDerivedIndex` over SQLite embeddings (`semblon.ann_index.search_index`) |
| Module entry | `semblon.index_provider`, `semblon.region_search`, `semblon.search` |
| Input / output | Query vector + modality/pack → top-k exact neighbours |
| Embedding pack | Same pack/modality as query; authoritative store is SQLite |
| Latency (p50/p95) | `UNMEASURED` |
| Coverage | `UNMEASURED` |
| Quality signal | ANN **disabled**; FAISS/Chroma refused until `docs/SHIP-GATES.md` ANN gate reopens |
| Reusable? | `YES_REUSE` |
| Inc 1 adoption | **`adopted=0`** baseline `existing_index`. **No FAISS** in policy or registry until ANN gate reopens. |

---

## C7 — `verify_same_instance(v1, v2)`

| Field | Value |
|---|---|
| Existing provider | `semblon.compare.compare` (identity) and `compare_space` (non-identity modalities) |
| Module entry | `semblon.compare` |
| Input / output | Two pack+dim+blob → cosine / dot under fail-closed pack rules |
| Embedding pack | Caller-supplied; identity requires L2 |
| Latency (p50/p95) | `UNMEASURED` (pure CPU; free relative to model invoke) |
| Coverage | 1.0 for valid finite L2 pairs; fail-closed otherwise |
| Quality signal | Contract tests in `tests/test_schema.py` / compare suite |
| Reusable? | `YES_REUSE` |
| Inc 1 adoption | **`adopted=0`** baseline `existing_compare`. Stage-2 SuperPoint etc. deferred to later increments. |

---

## C8 — `scene_classify(photo)`

| Field | Value |
|---|---|
| Existing provider | DINOv2 whole-frame **scene embedding** via `region_encoder` (`modality=scene`) — **not** a place/scene class labeler |
| Module entry | `semblon.region_encoder` (`MODALITY_SCENE`); Regions category backfill |
| Input / output | Full-frame image → 384-d L2 CLS vector stored as scene modality |
| Embedding pack | Same DINOv2 region pack; modality `scene`; dim **384**; float32; L2 |
| Latency (p50/p95) | `UNMEASURED` |
| Coverage | `UNMEASURED` |
| Quality signal | Embedding similarity only; scene *labels* are out of scope for this provider |
| Reusable? | `YES_WRAP` |
| Inc 1 adoption | **`adopted=0`** wrap as `existing_scene_embedding`. Policy semantics: `embedding_then_cluster`. A true scene **classifier** would be a **new** capability `C8b`, not an upgrade to C8. |

---

## C9 — `ocr(photo)`

| Field | Value |
|---|---|
| Existing provider | `semblon.observers.ocr_image` / `probe_ocr_status` — pytesseract + `tesseract` on PATH |
| Module entry | `semblon.observers` (`OCR_PROVIDER=tesseract`); Words door in `category_backfill.words_ocr` |
| Input / output | Image → text payload (or unavailable/error item — no crash) |
| Embedding pack | n/a |
| Latency (p50/p95) | `UNMEASURED` |
| Coverage | `UNMEASURED` (0 when tesseract missing — capability effectively deferred at runtime) |
| Quality signal | `UNMEASURED` |
| Reusable? | `YES_REUSE` when available; treat as deferred/`NONE` at runtime if probe fails |
| Inc 1 adoption | **`adopted=0`** baseline `existing_ocr`. No candidate OCR model. |

---

## Candidates registered dormant (not loaded, not adopted)

| capability_id | provider_name | Notes |
|---|---|---|
| C1 | `ram_plus` | Open-vocab tagger candidate; requires §6 vs NanoDet/CLIP baseline |
| C2 | `grounding_dino` | Prompted box candidate; SHIP-GATES currently refuses as required splitter |
| C4 | `adaface_ir18` | Face embedder candidate; must pass `validate_identity_embedding` + trust firewall |
| C5 | `hdbscan` | Clusterer candidate vs DBSCAN baseline |

---

## Stop condition check

Every capability the BRAIN intends to use in later increments has an existing provider (`YES_REUSE` / `YES_WRAP`) or an explicit dormant candidate with `adopted=0`. No capability is marked for silent re-implementation. Inventory is **complete** for C1–C9.
