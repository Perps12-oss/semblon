# FaceKit owner workflow

**Tracker:** `docs/BUILD-STATUS.md` issue 06.  
**Workflow:** `.github/workflows/facekit-owner.yml` (`workflow_dispatch` only).  
**Rule:** Semblon does **not** download `buffalo_l`. Missing or unaccepted packs fail closed.

## Prerequisites

1. Windows machine (or `windows-latest` runner) with the accepted ONNX pack already on disk.
2. Python 3.12 matching the release baseline (`docs/decisions/2026-10-16-python-support-policy.md`).
3. Only `opencv-python-headless` (no `opencv-python` / contrib) — `tools/assert_one_opencv.py` must exit 0.
4. Pack opted in and hash-pinned via `semblon lab pack-accept`.

## Accepted pack

- Family: `buffalo_l` under the InsightFace home used by `semblon.engine.face_pack_dir`.
- Pin file: `semblon-pack-pin.json` (written by `pack-accept`) with `opt_in` and per-file SHA-256 digests.
- Redistribution of these weights remains **UNAVAILABLE** until a separate licence decision (`docs/licenses.md`, `docs/decisions/2026-10-16-identity-engine-redistribution.md`).

## Exact commands (owner machine)

```powershell
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pip uninstall -y opencv-python opencv-contrib-python
python -m pip install --force-reinstall --no-deps opencv-python-headless==5.0.0.93
python tools/assert_one_opencv.py
semblon lab pack-accept
python -c "from semblon.engine import assert_face_pack_ready; print(assert_face_pack_ready())"
```

GitHub: Actions → **facekit-owner** → Run workflow (fails with an actionable message if the pack is missing on the runner).

## Expected outputs

- `assert_one_opencv.py` prints `opencv ok: …`
- `assert_face_pack_ready()` returns the pinned file digest map
- Workflow step “Require a pinned local pack” exits 0

## Failure reasons

| Symptom | Cause |
|---|---|
| `owner pack missing or unpinned` | No ONNX files or no valid pin |
| Mixed OpenCV refuse | `opencv-python` installed beside headless |
| Download attempted / blocked | Weight downloader must stay patched; do not weaken acceptance |

## Status rule

A green owner run requires recorded commit, Python version, and pin digest list. Until that evidence exists, issue 06 stays **BLOCKED** or **IN PROGRESS** — never VERIFIED by documentation alone.
