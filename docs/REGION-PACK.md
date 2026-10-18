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
| `region` | A crop. Region search reads only this, and only this pack. |
| `scene` | The whole frame of the same model. Whole-image Similar may use it. |
| `appearance` | Colour histogram. Labelled "Colour only" when the encoder or a compatible index is missing. |

A session or run that exceeds 15 seconds is abandoned. Later encodes fail closed until the process restarts, and search says colour only.

Ranking: cosine via `compare_space`, same modality and pack, drop the source media, keep the best score per media, drop scores below 0.76, cap the list. That floor was chosen on the synthetic glyph corpus in `docs/evidence/visual-discovery-eval.json`. It is not a photograph confirmation and it is not a claim of same-physical-object retrieval.
