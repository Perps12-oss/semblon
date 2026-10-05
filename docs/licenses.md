# SEMBLON — Licence record

InsightFace code is typically MIT. buffalo_l weights often research/non-commercial.
FACE-000–003 = internal evaluation only. Not commercial permission.
Shipping weights needs a separate licence/pack decision. Fallback: YuNet + SFace.
Do not block FACE-000 on that decision.
Do not bundle buffalo_l into a frozen installer until that decision exists. `tools/install-windows.ps1` and the WiX **code MSI** (`packaging/msi`, `tools/msi/build-msi.ps1`) install **application code only**. Stage/build scripts refuse `buffalo_l` / `*.onnx` in the payload (`tools/msi/assert-no-weights.py`). First real ingest may still download buffalo_l via InsightFace into `%USERPROFILE%\.insightface\models\buffalo_l` — that is not Semblon redistribution.

## Inventory (2026-09-19)

| Component | Role | Licence note | Redistribute? |
|---|---|---|---|
| Semblon application code | product | repository licence | yes (code) |
| numpy / opencv-python-headless / onnxruntime | runtime | typical Apache/MIT/BSD — confirm at release | code deps yes |
| insightface | identity engine | typically MIT **code**; weights separate | code yes; **weights no** until pack licence |
| buffalo_l ONNX | identity weights | often research/non-commercial | **no** |
| pytest | dev | MIT | not shipped |
| PySide6 | production UI extra `.[gui]` (`semblon shell`). Windows installer installs it. S8 spike stays research | LGPL. Not required for the headless engine or the legacy Tk clients | required on the production install path; not a headless dependency |
| OpenCV local visual understanding | open-vocab VisualSegment default provider | already a Semblon runtime dep | yes (code path) |
| open_clip / CLIP weights | optional concept ranking | model licences separate; Semblon does not bundle | **no weights** |
| SAM 2 (`SAM-2` 1.0 from `facebookresearch/sam2`) | optional class-agnostic spatial discovery | code Apache-2.0; checkpoints are Meta weights, not Semblon redistribution | **no checkpoints** |
| SAM3 | not integrated | verify before any pack decision | **no** |

Future candidates (MediaPipe, CLIP/successors, other packs) need a separate code **and** model licence check before they enter the plan as more than a name. A licence veto beats a technically attractive model.

PySide6 / Qt 6: **LGPL**. Dynamic link from extra `.[gui]`. That extra is the production shell (`semblon shell`). The Windows installer installs it. It is not a headless-engine dependency. The S8 spike remains research. Do not statically link Qt without a separate licence pass. See `docs/ARCHITECTURE.md`, `docs/S8-TOOLKIT.md`.
