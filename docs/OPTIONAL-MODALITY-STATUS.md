# Optional modality status (honesty)

Optional OCR / CLIP / pose observers are **experimental**. They never vote on identity (`faces.person_id`, `embeddings.modality='face'`, `compare()`, DBSCAN). FaceKit remains the only identity engine.

`optional_status()` (CLI: `lab providers`; Home Settings line) must match what the call path needs — not a bare `import`.

| Flag | Ready only when | Probe |
|---|---|---|
| `ocr` | `pytesseract` imports **and** `tesseract` is on `PATH` | `probe_ocr_status` |
| `clip` | `open_clip` + `torch` import **and** local `ViT-B-32` / `openai` weights exist | `probe_clip_status` / `find_local_clip_weights` (no download) |
| `pose` | `mediapipe.solutions.pose` exists (API used by `pose_landmarks`) | `probe_pose_status` |

Missing pieces → `False` plus a `notes[<key>]` string starting with `unavailable:`. Do not claim production-ready. Do not change product defaults until a human verifies the binaries/weights on the target machine.

## Human verify (before Settings copy / product defaults)

Run on the machine that will run Semblon (quote paths; use the project venv):

```text
.\.venv\Scripts\python.exe -m semblon lab providers
```

Check the JSON:

1. **OCR** — `observers.ocr` is `true` only if `tesseract` is on PATH.
   - Install OS Tesseract OCR; confirm: `where.exe tesseract` (Windows) or `command -v tesseract`.
   - `pip install pytesseract` is not enough by itself.
2. **CLIP** — `observers.clip` is `true` only if open_clip + torch are importable **and** weights are already on disk.
   - Status never downloads. Expected URL cache file: `%USERPROFILE%\.cache\clip\ViT-B-32.pt` (or `OPENCLIP_CACHE_DIR`).
   - HF hub cache under `%USERPROFILE%\.cache\huggingface\hub\models--timm--vit_base_patch32_clip_224.openai\` also counts.
   - Deliberate first download (human only, not CI): a one-off `clip_embed` / open_clip `create_model_and_transforms("ViT-B-32", pretrained="openai")` after accepting the licence story in `docs/licenses.md`.
3. **Pose** — `observers.pose` is `true` only if `import mediapipe` exposes `mediapipe.solutions.pose`.
   - A mediapipe package without `solutions` (e.g. some 1.0 builds) must stay `false` with note `mediapipe.solutions.pose missing`.

## After verify — wiring (human / follow-up slice)

Once the three flags match reality on the owner machine:

- Home Settings may print `notes` when a flag is false (today it prints booleans only).
- Product docs / defaults may list OCR/CLIP/pose as optional extras **for that machine**, still Level 3 experimental, still non-identity.
- Do not flip defaults on for clean `install-windows.ps1` installs that lack the binary/weights.

## Out of scope here

Bake-off artifacts, Ruled-out lists, live overlay UI. Identity firewall unchanged.
