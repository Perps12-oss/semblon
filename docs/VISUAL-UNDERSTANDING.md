# Open-vocabulary interactive visual understanding

**Production UI:** PySide6 `semblon shell` (`semblon/native_shell`). The Canvas / Tk paths in the table below are historical.

**Status:** historical Canvas slice (non-identity observation layer). Production door is PySide6 `semblon shell`.  
**Authority:** observation extras under `SEM-ARCH-V1.4` / PRODUCT Level 2; identity firewall unchanged  
**Not:** a second GUI, SAM3-as-architecture, or automatic person naming

## A. Architecture audit (production paths)

| Area | Production path | Citation |
|---|---|---|
| A. Image load/render | `CanvasWorkspace.show_media` → `load_bgr` → `_png_photo` → Tk `PhotoImage` | `semblon/canvas.py` |
| B. Workspace | Home embeds `CanvasWorkspace` (Library \| Workspace \| Inspector) | `semblon/home_ui.py` |
| C. Detection providers | `FaceKitProvider` only for identity | `semblon/providers.py` |
| D. Face observations | `faces` + dual-write `observation_items kind=face` | `semblon/ingest.py`, `observers.py` |
| E. Object/visual | Contour objects + optional OCR/CLIP/pose; Lens grounding | `observers.py`, `lens.py` |
| F. Embeddings | Face on `faces`; appearance/clip/siglip on `embeddings` (never `modality=face`) | `store.py` MIGRATION_2 |
| G. Bboxes | Pixel space on faces / observation_items | Canvas hit-test |
| H. Masks | No schema column; Lens digest in payload; **this slice** stores masks in `visual_cache` sidecars | `visual_cache.py` |
| I. Provider abstraction | FaceKit + Lens `CapabilitySpec`; **this slice** adds `SemanticVisualProvider` | `semantic_visual.py` |
| J. Schema | `SCHEMA_VERSION=4`; no new DDL for VisualSegment | `store.py` |
| K. Jobs | `JobEngine` ingest + **visual_analyze slot** | `jobs.py` |
| L. Coordinates | Canvas `_ox/_oy/_scale`; `geometry.widget_point_to_image` | `geometry.py` |
| M. Mouse | Canvas `<Motion>` / click / drag | `canvas.py` |
| N. Inspector | Soft copy via `product_surface` | `product_surface.py` |

## B. Reused capabilities

- Production Canvas hover/click/selection (extended, not replaced)
- `observation_items` conventions for soft Inspector (payload labels)
- Lens SAM2 probe path (optional refine backend)
- OpenCV contour discovery patterns from `observers.contour_objects`
- JobEngine as the single background door
- Identity soft labels stay FaceKit / person decisions only

## C. VisualSegment

Model-independent dataclass in `semblon/visual_segment.py`. Fields: segment_id, observation_id, media_id, frame_id, label, label_type, confidence, bbox, mask_ref, parent_segment_id, source_provider, model_id, model_version, embedding_ref, created_at.

Persistence: **no new SQLite columns**. Cache sidecars under `{store_parent}/visual_cache/{media_id}/{config_key}/` (`segments.json`, `pixel_map.bin`, `masks.npz`, `meta.json`).

## D. Provider abstraction

`SemanticVisualProvider` Protocol:

- `discover_concepts(image)`
- `discover_regions(image)`
- `segment_concept(image, concept)`
- `refine_from_point(image, x, y)`
- `refine_from_box(image, bbox)`

Default: `LocalSemanticVisualProvider` (OpenCV). Optional CLIP / VLM / SAM2 behind probes — missing models degrade gracefully.

## E–H. Pipeline

1. **Scene inventory** — appearance-grounded labels from multi-threshold regions (image-dependent). Optional CLIP open-candidate ranking; optional VLM concepts.
2. **Region discovery** — class-agnostic connected components (no class list required).
3. **Grounding** — concept↔region reconcile; SAM2 when env configured; else mask from region / flood-fill / box.
4. **Salience** — `SaliencePolicy` (area, confidence, IoU merge, caps). Configurable/testable.

## I. Pixel → segment index

`PixelSegmentIndex` (`pixel_index.py`): uint16 map in source-image coordinates. Hover: widget → `widget_point_to_image` → `map[y,x]` → VisualSegment. No model/SQLite on the hot path.

## J–K. Production Canvas UX

- Clean photo by default
- Hover: translucent mask stipple + human label
- Click: persistent selection → Inspector (`soft_inspector_for_visual_segment`)
- Unknown click: `refine_from_point` interactive segment
- Never auto-assigns person names

## L–M. Cache + background

`analyze_and_cache` + `JobEngine.submit_visual_analyze` (separate slot from ingest). Opening a photo loads cache instantly or analyzes without freezing Tk (`after(0)` apply).

## N. Performance (measured in tests / lab)

Typical local-opencv on ~220² synthetic images (CPU Linux agent, `docs/VISUAL-EVAL-CORPUS.json`):

| Metric | Measured |
|---|---|
| Analysis | ~0.005–0.03 s / image (mean ≈ 0.01 s) |
| Hover lookup | ≈ 0.0005 ms / probe (memory map) |
| Cached reopen | ≈ 0.5–2 ms |
| Segments / image | ≈ 1–29 (salience-capped; clutter high) |
| Distinct inventories / 15 scenes | 13–14 |

Exact numbers: run `pytest tests/test_visual_understanding.py -q` and inspect `docs/VISUAL-EVAL-CORPUS.json`.

## O. 15-image evaluation

Synthetic corpus in `tests/test_visual_understanding.py` (`CORPUS_KINDS`): portrait, group, pet, street, interior, kitchen, landscape, forest, urban, product, screenshot, clutter, unusual, reflection, overlap.

Gate: ≥8 distinct label-set inventories across the 15 scenes (not one fixed vocabulary).

## P. Negatives

Covered: empty/dark/bright, low/high res, overlap/nest, tiny/huge salience reject, JobBusy on second visual job, coordinate zoom/pan/portrait/landscape/square.

## Q. SAM 2 / SAM 3

Official package: `facebookresearch/sam2`, distribution `SAM-2` (installed 1.0 in the dev venv). Not an arbitrary PyPI `sam2` fork.

| | SAM 2 | SAM 3 |
|---|---|---|
| In repo today | `semblon/sam2_runtime.py` automatic masks when `SAM2_READY`; Lens grounding still separate | **Not present** |
| Role | Class-agnostic spatial discovery. It does not name objects | Future candidate only |
| Checkpoint | `SEMBLON_SAM2_CHECKPOINT` local file. Config `SEMBLON_SAM2_CONFIG` or inferred from the filename. Optional `SEMBLON_SAM2_SHA256` | — |
| States | `SAM2_NOT_INSTALLED`, `SAM2_AVAILABLE` (import + file, not loaded), `SAM2_NOT_CONFIGURED`, `SAM2_WEIGHTS_MISSING`, `SAM2_LOAD_FAILURE`, `SAM2_READY` | — |
| Download | Never. Semblon does not fetch weights | — |
| Device | CUDA if `torch.cuda` is available, else CPU. DirectML is not used | — |
| Hover | Owner-map lookup. Pointer motion does not call SAM 2 | — |

Example local layout (operator-provided, not shipped):

```text
set SEMBLON_SAM2_CHECKPOINT=%LOCALAPPDATA%\Semblon\weights\sam2.1_hiera_small.pt
```

Config for that file is `configs/sam2.1/sam2.1_hiera_s.yaml` when `SEMBLON_SAM2_CONFIG` is unset.

Dev install (CPU wheel first, then the official repo). This is not a core `requirements.txt` dependency:

```text
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
set SAM2_BUILD_CUDA=0
pip install git+https://github.com/facebookresearch/sam2.git
```

## R. Hardware / deployment

- Default path: OpenCV CPU — works wherever Semblon Home works (x64 / ARM64 with working `cv2`).
- ARM64 OpenCV load hang remains a Semblon-wide issue (`docs/PERF-P1-ARM64.md`); this slice does not silent-swap S1 FaceKit.
- CLIP/SAM2 optional; never downloaded by Semblon.
- Emulation (x64-on-ARM64) is `emulated` only — do not claim native.

## S. Licensing / redistribution

| Component | Note |
|---|---|
| Local OpenCV path | Typical Apache/MIT/BSD stack — already a Semblon dep |
| CLIP (OpenAI ViT-B-32 via open_clip) | Optional; weights not redistributed by Semblon |
| SAM2 | Apache-2.0 code typical; checkpoints separate — env-provided only |
| SAM3 | Verify licence before any pack decision; do not bundle |
| buffalo_l | Unrelated identity weights — still non-redistributable |

See `docs/licenses.md`.

## T. Remaining gaps vs Grok reference

1. **Noun quality** — without a local VLM/SAM3, labels are appearance-grounded (“vegetation”, “water”, “clothing”) more often than scene-specific nouns (“hooded figure”, “muddy bank”). CLIP/VLM/SAM3 providers close this when installed.
2. **Hierarchy UI** — parent/child is stored; sidebar tree like the reference is not built (no second GUI; Inspector lines only).
3. **Progressive T3/T4** — faces + regions + labels ship; advanced embeddings/relationships not auto-linked.
4. **Windows live dump-gate** — Canvas hover polish needs owner Windows verification (this agent is Linux).
5. **Permanent SQLite dual-write** of every VisualSegment into `observation_items` is optional/not required for hover (cache is authoritative for the map).

## CLI

```text
semblon lab visual-understand --image "C:\path\photo.jpg" --store "%LOCALAPPDATA%\Semblon\store.sqlite" --json
semblon lab providers
```

## Identity firewall

Visual segments never write `faces.person_id` or `embeddings.modality='face'`. A segment labelled Person is not John until a human identity decision exists.
