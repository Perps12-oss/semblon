# SEMBLON — Licence record

## Identity engine (2026-10-16 cutover)

Production identity path: **YuNet** (detect) + **SFace** (recognise) via OpenCV Zoo ONNX files.  
InsightFace **code** and **buffalo_l weights** are **retired from the production runtime** (historical docs/S1 evidence only).

| Component | Role | Licence note | Redistribute in MSI? |
|---|---|---|---|
| YuNet ONNX (`face_detection_yunet_*.onnx`) | detector | Zoo directory claims **MIT** ([LICENSE](https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE)) | **no until L PASS** — BYO |
| SFace ONNX (`face_recognition_sface_2021dec.onnx`) | recogniser | Zoo directory claims **Apache-2.0** ([LICENSE](https://github.com/opencv/opencv_zoo/blob/main/models/face_recognition_sface/LICENSE)) | **no until L PASS** — BYO |
| OpenCV / opencv-python-headless | runtime | Apache-2.0 (library) | code dep yes; **does not clear model weights** |
| buffalo_l ONNX | retired | research/non-commercial (historical) | **no** |
| insightface Python package | retired from deps | typically MIT **code**; weights separate | **not a runtime dep** |

**Gate L status:** **OPEN / BYO only.** Source-directory licence labels are recorded; commercial redistribution of the exact weight bytes is **not** claimed until legal sign-off files local SHA-256 pins + NOTICE packaging. The code MSI / WiX path (`packaging/msi`, `tools/msi/assert-no-weights.py`) fails closed on any `.onnx`.

Exact install + hashes: `docs/IDENTITY-PACK.md`. Evaluation order: `docs/decisions/2026-10-16-identity-stack-eval-order.md`.  
Notice copies: `docs/notices/yunet-MIT.txt`, `docs/notices/sface-APACHE-2.0.txt`, `docs/notices/nanodet-APACHE-2.0.txt`.

Unresolved before L PASS:

1. Confirm SFace Apache-2.0 text applies to the **exact** `face_recognition_sface_2021dec.onnx` bytes at a pinned Zoo commit (not only the directory README).
2. Confirm YuNet MIT applies to the chosen `2023mar` / `2026may` file at that commit.
3. Record local SHA-256 after owner download; keep copies of LICENSE files with the release NOTICE plan.
4. Decide whether MSI may ever bundle (separate product approval) or remain permanent BYO.

## Object detection (NanoDet BYO)

| Component | Role | Licence note | Redistribute in MSI? |
|---|---|---|---|
| NanoDet ONNX (`object_detection_nanodet_2022nov.onnx`) | COCO-80 detector | Zoo directory claims **Apache-2.0** ([LICENSE](https://github.com/opencv/opencv_zoo/blob/main/models/object_detection_nanodet/LICENSE)) | **no until L PASS** — BYO |
| Contour regions (`opencv-contour`) | geometry only | OpenCV runtime | code path yes; **not** detector labels |

**Gate L status (objects):** **OPEN / BYO only.** Exact SHA-256 unrecorded until owner download evidence in `docs/OBJECT-PACK.md`. MSI `assert-no-weights.py` refuses `.onnx` and NanoDet names.

## OCR (Tesseract BYO)

| Component | Role | Licence note | Redistribute? |
|---|---|---|---|
| Tesseract binary | OCR | Apache-2.0 (upstream) | **OS/BYO** — not MSI-bundled unless separately approved |
| pytesseract | optional Python bridge | Apache-2.0 | code dep optional |

## Other inventory

| Component | Role | Licence note | Redistribute? |
|---|---|---|---|
| Semblon application code | product | repository licence | yes (code) |
| numpy / onnxruntime | runtime | typical Apache/MIT/BSD — confirm at release | code deps yes |
| pytest | dev | MIT | not shipped |
| PySide6 | production UI extra `.[gui]` | LGPL | required on production install path |
| OpenCV local visual understanding | open-vocab VisualSegment | already a runtime dep | yes (code path) |
| open_clip / CLIP weights | optional | model licences separate; Semblon does not bundle | **no weights** |
| SAM 2 | optional | code Apache-2.0; checkpoints not redistributed | **no checkpoints** |

A licence veto beats a technically attractive model. FACE-000–005 historical buffalo_l runs are not commercial permission for that pack.
