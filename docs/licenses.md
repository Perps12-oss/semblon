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
| PySide6 | optional `.[gui]` — native `semblon shell` + S8 spike reference | LGPL; not required for Tk Home/review-ui | optional extra only |

Future candidates (MediaPipe, CLIP/successors, other packs) need a separate code **and** model licence check before they enter the plan as more than a name. A licence veto beats a technically attractive model.

PySide6 / Qt 6: **LGPL**. Dynamic link from optional extra `.[gui]` (native production shell `semblon shell`; S8 spike remains reference). Not a core dependency. Do not statically link Qt without a separate licence pass. See `docs/S8-TOOLKIT.md`, `docs/APPLICATION_API.md`.
