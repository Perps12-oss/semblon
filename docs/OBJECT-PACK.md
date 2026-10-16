# Object pack — NanoDet (observation only)

**Status:** BYO runtime path for COCO-80 object labels.  
**Redistribution / MSI bundling:** **BLOCKED** (L OPEN) until exact-byte licence clearance.  
**Identity:** never writes `faces.person_id` or face embeddings.

## Exact artifact

| Role | Filename | Upstream |
|---|---|---|
| Detector | `object_detection_nanodet_2022nov.onnx` | [opencv_zoo NanoDet](https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_nanodet) |

Variant: NanoDet-Plus-m 416, COCO-80. Int8 zoo files are not the Semblon pin.

### Local SHA-256

| File | SHA-256 |
|---|---|
| `object_detection_nanodet_2022nov.onnx` | **UNRECORDED** — owner must hash after download and record here before L PASS |

Zoo directory claims **Apache-2.0** for files in that folder ([LICENSE](https://github.com/opencv/opencv_zoo/blob/main/models/object_detection_nanodet/LICENSE)). That is **not** MSI bundling clearance for the weight bytes.

Optional pin file beside the ONNX:

```text
semblon-object-pack-pin.json
{ "sha256": "<hex digest of the ONNX>" }
```

## Install (BYO, offline after download)

Semblon **never** downloads these files.

```text
%USERPROFILE%\.semblon\models\nanodet\
  object_detection_nanodet_2022nov.onnx
  semblon-object-pack-pin.json   (optional until L PASS)
```

Optional override: `SEMBLON_OBJECT_PACK` = absolute directory.

Missing, truncated (Git LFS pointer), or hash-mismatched packs → honest UNAVAILABLE. Contour regions (`opencv-contour`, `class=region`) remain separate and are **not** object search hits.

## Search

```powershell
semblon search --store "%LOCALAPPDATA%\Semblon\store.sqlite" --object "dog"
```

Shell: Settings → Search objects, then type a COCO class substring. Results set Field media and show basis `COCO object detection (NanoDet)`.

## MSI

`tools/msi/assert-no-weights.py` refuses `.onnx`, NanoDet names, YuNet/SFace, and buffalo_l until a separate L PASS allowlists bundling.
