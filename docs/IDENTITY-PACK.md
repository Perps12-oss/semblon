# Identity pack — YuNet + SFace (production engine)

**Status:** Production runtime path is YuNet detect + SFace recognise.  
**Redistribution / MSI bundling:** **BLOCKED** until licence gate **L PASS** (BYO only).  
**Product cutover quality:** **Q OPEN** — thresholds in `semblon/identity_config.py` are provisional.

## Exact artifacts

| Role | Filename | Upstream |
|---|---|---|
| Detector | `face_detection_yunet_2026may.onnx` (preferred) or `face_detection_yunet_2023mar.onnx` | [opencv_zoo YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) |
| Recogniser | `face_recognition_sface_2021dec.onnx` | [opencv_zoo SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) |

### Local SHA-256 (owner machine download 2026-10-16)

| File | SHA-256 |
|---|---|
| `face_detection_yunet_2023mar.onnx` | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` |
| `face_recognition_sface_2021dec.onnx` | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` |

Zoo commit at download time: `opencv/opencv_zoo` **main** tip (pin a commit SHA before L PASS). These hashes are **not** MSI-bundling clearance.

Licence texts (verify independently — OpenCV **code** licence ≠ model clearance):

- YuNet: MIT — `models/face_detection_yunet/LICENSE`
- SFace: Apache-2.0 — `models/face_recognition_sface/LICENSE`

## Install (BYO, offline after download)

Semblon **never** downloads these files.

```text
%USERPROFILE%\.semblon\models\yunet_sface\
  face_detection_yunet_2023mar.onnx   (or 2026may)
  face_recognition_sface_2021dec.onnx
```

Optional override: `SEMBLON_FACE_PACK` = absolute directory.

```powershell
semblon lab pack-accept
semblon lab models
```

Missing or unpinned packs fail closed with recovery instructions (no silent fallback to buffalo_l).

## pack_id

Family: `opencv/yunet_sface@{opencv-version}/adapter-{n}/sha256:{16hex}`  
Embedding dim: **128** (L2-normalised).  
Never compare to `insightface/buffalo_l` embeddings.

## Alignment

SFace features are produced only after `FaceRecognizerSF.alignCrop` using YuNet’s five-landmark face row. Do not feed unaligned bbox crops.

## Clustering

Defaults live in `semblon/identity_config.py` (provisional). Historical buffalo_l S1 constants: `semblon/identity_buffalo_frozen.py` / `docs/S1-GOLDEN.md`.

## Re-embed

```powershell
semblon lab reembed --store "%LOCALAPPDATA%\Semblon\store.sqlite"
```

Backup the store first. Checkpoint: `<store>.reembed-checkpoint.json`. Preserves persons/decisions; new faces start without `person_id`; re-cluster and review.

## MSI

`tools/msi/assert-no-weights.py` refuses any `.onnx`, buffalo_l, and YuNet/SFace names in the payload until a separate L PASS authorises bundling.
