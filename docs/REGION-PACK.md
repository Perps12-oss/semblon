# Region pack — DINOv2 ViT-S/14 (observation only)

**Status:** BYO runtime path for region and scene vectors.  
**Redistribution / MSI bundling:** **BLOCKED** (L OPEN). The ONNX is not vendored.  
**Identity:** never writes `faces.person_id` or `embeddings.modality='face'`.

This is a visual region embedding, not a face embedding and not a class name.

## Exact artifact

| Role | Filename | Upstream |
|---|---|---|
| Encoder | `dinov2-vits14.onnx` | [onnx-community/dinov2-small](https://huggingface.co/onnx-community/dinov2-small) commit `ef1fb1005bfd7768839d18080f7038b403506f87` |

Apache-2.0. Facebook DINOv2 ViT-S/14. The stored vector is the CLS token, L2-normalised.

| File | SHA-256 | Size |
|---|---|---|
| `dinov2-vits14.onnx` | `f22797eabf810a75e41de68d378541ebea372122b25c4ce3ef25ff618250c20a` | 88532934 bytes |

Source URL (explicit fetch only, never at query time):

```text
https://huggingface.co/onnx-community/dinov2-small/resolve/ef1fb1005bfd7768839d18080f7038b403506f87/onnx/model.onnx
```

## Install

```text
.venv-312\Scripts\python.exe tools\fetch_region_pack.py
```

Writes `%USERPROFILE%\.semblon\models\region\` (or `SEMBLON_REGION_PACK`):

- `dinov2-vits14.onnx`
- `semblon-region-pack-pin.json` whose `sha256` must equal the file

Probe refuses a missing file, a hash mismatch, or a pin that does not match the bytes. After install, search stays offline.

## Compare key

`region/dinov2-vits14@1/f22797eabf810a75/cls`

Preprocess for query and index: letterbox to 224 (the whole crop is kept), divide by 255, ImageNet mean/std, CLS token, L2. Dimension 384.

| Stored modality | What it is |
|---|---|
| `region` | A proposal crop (CLS). Used only when a patch map is absent. |
| `region_patch` | Every content patch of the frame. Region search reads this first. Pack id ends in `/patch`. |
| `scene` | The whole frame CLS of the same model. Whole-image Similar may use it. |
| `appearance` | Colour histogram. Labelled "Colour only" when the encoder or a compatible index is missing. |

A pointed region is embedded as its own content patches and scored against `region_patch` rows by late interaction (mean of each query patch's best cosine in the other photo). The match box is the union of those winning patches. The six proposal crops are not the search space.

A session or run that exceeds 15 seconds is abandoned. Later encodes fail closed until the process restarts, and search says colour only.

Whole-frame CLS ranking for the proposal fallback stays cosine 0.76, chosen on the glyph corpus.

Patch search is different. Each indexed photo stores content patches of the full frame and of overlapping windows (the ONNX input is fixed at 224, so a small object needs a closer window). The query crop's patches score the other photo by the mean of each query patch's best cosine. Token floor 0.35, score floor 0.28, coverage floor 0.28, chosen on `docs/evidence/photo-region-eval.json`. The match box is the union of the winning patches. This is not a person and not a claim of web identification.
