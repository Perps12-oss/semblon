# Identity pack owner evidence (YuNet + SFace)

**Rule:** Semblon does **not** download YuNet/SFace. Missing or unaccepted packs fail closed.  
**Historical note:** This file formerly covered buffalo_l / FaceKit. That engine is retired from production.

## Pack location

Default: `%USERPROFILE%\.semblon\models\yunet_sface`  
Override: `SEMBLON_FACE_PACK` or workflow input `pack_dir`.

Required files: see `docs/IDENTITY-PACK.md`.

## Commands

```powershell
semblon lab pack-accept
semblon lab models
python tools/facekit_owner_evidence.py --pack-dir "%USERPROFILE%\.semblon\models\yunet_sface" --out facekit-owner-evidence.json
```

Workflow: `.github/workflows/facekit-owner.yml` (`workflow_dispatch`).

## Redistribution

Still **UNAVAILABLE** until L PASS. MSI must not contain `.onnx`.
