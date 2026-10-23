# Third-Party Licenses and Attributions

Semblon uses the following third-party software and optional model packs.

This file is an attribution notice. It is **not** permission to put weights in the installer. Redistribution stays in [`docs/licenses.md`](docs/licenses.md). Gate **L** is open. The MSI build refuses every `.onnx` until that gate passes (`tools/msi/assert-no-weights.py`).

Semblon does not ship geographical databases, map tiles, or bundled icon fonts. Those are not part of this product.

## ML models

Semblon does **not** bundle ML weights in the installer.

Identity weights are bring-your-own. Semblon never downloads YuNet or SFace. Object and region packs download only from an explicit install action, then check a pinned SHA-256. Search and browse do not download. Upstream terms govern the weight bytes. Semblon is a local integrator, not the licensor.

OpenCV **library** licence is not clearance for a model file in the same repository.

### YuNet (face detection)

- Upstream: [opencv_zoo / face_detection_yunet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
- Files: `face_detection_yunet_2023mar.onnx` or `face_detection_yunet_2026may.onnx`
- Directory licence claim: MIT. Local copy: [`docs/notices/yunet-MIT.txt`](docs/notices/yunet-MIT.txt). Copyright (c) 2020 Shiqi Yu.
- Install: `%USERPROFILE%\.semblon\models\yunet_sface\` (or `SEMBLON_FACE_PACK`)
- MSI: **not bundled** until L PASS
- Detail: [`docs/IDENTITY-PACK.md`](docs/IDENTITY-PACK.md)

### SFace (face recognition)

- Upstream: [opencv_zoo / face_recognition_sface](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface)
- File: `face_recognition_sface_2021dec.onnx`
- Directory licence claim: Apache-2.0. Local copy: [`docs/notices/sface-APACHE-2.0.txt`](docs/notices/sface-APACHE-2.0.txt)
- Embedding: 128-d, L2-normalised, only after `FaceRecognizerSF.alignCrop`
- MSI: **not bundled** until L PASS. A directory README is not sign-off for the exact bytes.

### buffalo_l / InsightFace (retired)

- Not a production dependency. Not loaded. Not a fallback if YuNet or SFace is missing.
- Historical research weights are not cleared for commercial redistribution.
- Do not compare a buffalo_l embedding with a SFace embedding.

### NanoDet (object labels, not identity)

- Upstream: [opencv_zoo / object_detection_nanodet](https://github.com/opencv/opencv_zoo/tree/main/models/object_detection_nanodet)
- File: `object_detection_nanodet_2022nov.onnx` (NanoDet-Plus-m 416, COCO-80)
- Directory licence claim: Apache-2.0. Local copy: [`docs/notices/nanodet-APACHE-2.0.txt`](docs/notices/nanodet-APACHE-2.0.txt)
- Probe and search never download. A confirmed install from the object-search screen may fetch that pinned file once.
- MSI: **not bundled** until L PASS
- Detail: [`docs/OBJECT-PACK.md`](docs/OBJECT-PACK.md)

### DINOv2 ViT-S/14 (region and scene look, not a face)

- Upstream weights: Meta DINOv2, via `onnx-community/dinov2-small` at commit `ef1fb1005bfd7768839d18080f7038b403506f87`
- File: `dinov2-vits14.onnx`
- Recorded licence on the pin: Apache-2.0
- Query and ingest do not download. `install_region_pack` is a separate, hash-checked install.
- Not an identity embedding. It must not be written as `embeddings.modality='face'`.

### ONNX Runtime

The runtime that executes the ONNX packs above.

- Package: `onnxruntime==1.30.0`
- Licence: [MIT](https://github.com/microsoft/onnxruntime/blob/main/LICENSE)
- Attribution: Microsoft Corporation
- Shipped as a Python dependency. That wheel is not a model weight.

### Optional models (not the installer)

| Piece | When | Licence note | Bundled? |
|---|---|---|---|
| Tesseract | OS binary on `PATH`, plus optional `pytesseract` | Apache-2.0 upstream | **no** |
| CLIP / SigLIP (`open-clip-torch`) | Only if that extra is installed and weights are already on disk | Model licence is upstream. First download is a human step | **no weights** |
| SAM 2 | Checkpoint supplied by the owner (`SEMBLON_SAM2_CHECKPOINT`) | Code typically Apache-2.0. Checkpoints are not redistributed | **no checkpoints** |
| MediaPipe pose | Optional extra | Apache-2.0 | **no** |

Missing packs fail closed. They are not described as a built-in recogniser.

## Fonts

The production shell does not bundle a font.

QML asks for **Segoe UI** and **Segoe UI Variable**, which are Windows system fonts. Semblon does not ship Inter, JetBrains Mono, or Lucide.

## Photos the shell does not decode

HEIC, TIFF, and PDF are not opened as stills. There is no `libheif` feature and no claim of HEIC decode. A video tile uses a sampled frame, not a bundled codec pack beyond what OpenCV already links.

## Python dependencies

Runtime pins are in `pyproject.toml` and `requirements.txt`. Optional extras are not installed by the base environment.

| Package | Role | Licence (upstream) |
|---|---|---|
| onnxruntime | ONNX execution | MIT |
| opencv-python-headless | Image, YuNet, SFace, geometry | Apache-2.0 |
| numpy | Arrays | BSD-3-Clause |
| pillow | Still decode | HPND |
| onnx | ONNX protobuf helpers | Apache-2.0 |
| scipy | Numerics | BSD-3-Clause |
| scikit-image | Image helpers | BSD-3-Clause |
| requests | HTTP used by an explicit pack install | Apache-2.0 |
| tqdm | Progress | MIT and MPL-2.0 |
| PySide6-Essentials / Addons | Production UI (`semblon shell`) | LGPL-3.0 |
| pytest | Tests only | MIT |
| pytesseract | Optional OCR bridge | Apache-2.0 |
| open-clip-torch | Optional | MIT |
| torch / torchvision | Optional | BSD-3-Clause |
| transformers | Optional naming extra | Apache-2.0 |
| mediapipe | Optional pose | Apache-2.0 |
| argostranslate | Optional translation | MIT |

PySide6 is on the production install path (`pip install .[gui]`). The LGPL obligations of that wheel are not waived by this notice. Semblon does not use Qt WebEngine.

There is no `cargo deny` allow-list. CI runs `pip-audit` for known vulnerabilities. That is not a licence scan.

To dump the environment you actually installed:

```bash
python -m pip install pip-licenses
pip-licenses --format=markdown
```

Compare that output with this table before a release. A generated dump does not close gate L.
