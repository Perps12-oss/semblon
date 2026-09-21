"""Optional modality status (honesty)

Optional OCR / CLIP / pose observers are **observation / retrieval only**. They never vote on identity (`faces.person_id`, `embeddings.modality='face'`, `compare()`, DBSCAN). FaceKit remains the only identity engine.

`optional_status()` (CLI: `lab providers`; Home Settings) must match what the call path needs — not a bare `import`.

| Flag | Ready only when | Probe |
|---|---|---|
| `ocr` | `pytesseract` imports **and** `tesseract` is on `PATH` | `probe_ocr_status` |
| `clip` | `open_clip` + `torch` import **and** local `ViT-B-32` / `openai` weights exist | `probe_clip_status` / `find_local_clip_weights` (no download) |
| `pose` | `mediapipe.solutions.pose` exists (API used by `pose_landmarks`) | `probe_pose_status` |

Missing pieces → `False` plus a `notes[<key>]` string starting with `unavailable:`. Do not claim production-ready when probes fail.

## Product path (gated `SEMBLON_MODALITY_PRODUCT`, default ON)

Wire module: `semblon.gates.MODALITY_PRODUCT`.

1. **Settings UX** — Home Settings (Inspector) shows honesty booleans + `notes` via `modality_product_settings_lines()`.
2. **Optional ingest** — `resolve_product_observers()` / Home `resolve_home_observers()` appends `ocr` / `clip` / `pose` **only when** the matching probe is ready. Base remains `face,color,object`.
3. **Identity firewall** — optional items write `observation_items` / non-face `embeddings` only. Never `faces.person_id` or `embeddings.modality='face'`.

When the gate is opted out (`SEMBLON_MODALITY_PRODUCT=0`), Settings still lists probe results but product ingest stays on the base observer list.

## Human verify (before claiming extras on a machine)

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

Clean `install-windows.ps1` installs without binaries/weights correctly report unavailable; product defaults do not invent readiness.

## Out of scope here

Bake-off artifacts, Ruled-out lists, live overlay UI. Identity firewall unchanged.
