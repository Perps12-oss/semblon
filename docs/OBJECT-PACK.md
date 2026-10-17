# Object pack — NanoDet (observation only)

**Status:** BYO runtime path for COCO-80 object labels.  
**Redistribution / MSI bundling:** **BLOCKED** (L OPEN) until legal sign-off for the exact bytes.  
**Identity:** never writes `faces.person_id` or face embeddings.

## Exact artifact

| Role | Filename | Upstream |
|---|---|---|
| Detector | `object_detection_nanodet_2022nov.onnx` | [opencv_zoo NanoDet](https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_nanodet) |

Variant: NanoDet-Plus-m 416, COCO-80. Int8 zoo files are not the Semblon pin.

### Local SHA-256 (owner machine BYO download 2026-10-16)

| File | SHA-256 | Size |
|---|---|---|
| `object_detection_nanodet_2022nov.onnx` | `4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186` | 3800954 bytes |

Source URL used for BYO (not an in-app download):  
`https://github.com/opencv/opencv_zoo/raw/refs/heads/main/models/object_detection_nanodet/object_detection_nanodet_2022nov.onnx`

Zoo directory claims **Apache-2.0** for files in that folder ([LICENSE](https://github.com/opencv/opencv_zoo/blob/main/models/object_detection_nanodet/LICENSE)). Recorded notice: `docs/notices/nanodet-APACHE-2.0.txt`. That is **not** MSI bundling clearance for the weight bytes.

Required pin beside the ONNX:

```text
semblon-object-pack-pin.json
{ "sha256": "4b82da9944b88577175ee23a459dce2e26e6e4be573def65b1055dc2d9720186", ... }
```

Probe refuses missing pin, hash mismatch, truncated/LFS pointer files, or digests other than the documented artifact.

## Install (BYO, offline after download)

Semblon **never** downloads these files in product code.

```text
%USERPROFILE%\.semblon\models\nanodet\
  object_detection_nanodet_2022nov.onnx
  semblon-object-pack-pin.json
```

Optional override: `SEMBLON_OBJECT_PACK` = absolute directory.

Missing pack → honest UNAVAILABLE. Contour regions (`opencv-contour`, `class=region`) remain separate and are **not** object search hits.

## Search

```powershell
semblon search --store "%LOCALAPPDATA%\Semblon\store.sqlite" --object "dog"
```

Shell: Settings → Search objects. Results respect the active Field scope when set, then become the Field selection. Basis: `COCO object detection (NanoDet)`.

## MSI

`tools/msi/assert-no-weights.py` refuses `.onnx` and `object_detection_nanodet` paths until a separate L PASS allowlists bundling.
