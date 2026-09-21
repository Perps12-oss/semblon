# Optional modality status — PRODUCTIZED (optional)

Optional OCR / CLIP / pose observers are **productized as optional extras**. They never vote on identity (`faces.person_id`, `embeddings.modality='face'`, `compare()`, DBSCAN). FaceKit remains the only identity engine.

**Gate:** `SEMBLON_MODALITY_PRODUCT` (default **ON** after human verify). Opt out with `=0`.

`optional_status()` (CLI: `lab providers`; Home Settings) must match what the call path needs — not a bare `import`.

| Flag | Ready only when | Probe |
|---|---|---|
| `ocr` | `pytesseract` imports **and** `tesseract` is on `PATH` | `probe_ocr_status` |
| `clip` | `open_clip` + `torch` import **and** local `ViT-B-32` / `openai` weights exist | `probe_clip_status` / `find_local_clip_weights` (no download) |
| `pose` | `mediapipe.solutions.pose` exists (API used by `pose_landmarks`) | `probe_pose_status` |

Missing pieces → `False` plus a `notes[<key>]` string starting with `unavailable:`.

## Product wiring (when gate ON)

| Surface | Behaviour |
|---|---|
| Home Settings | Rich status via `modality_product_settings_lines()` — ready/unavailable + effective observers |
| Home ingest | `resolve_home_observers()` → `resolve_product_observers()` appends `text` / `clip` / `pose` only when probes are true |
| CLI `ingest` / `process` / `watch` | Default observers = `face` + ready optionals (explicit `--observers` wins) |
| Search | `search --text` (OCR payload substring, RO); `search --similar ITEM` (CLIP/appearance; refuses face); Home Search falls back to OCR text when no person hit |
| Clean install | No OCR/CLIP/pose packages in product `requirements.txt` / `install-windows.ps1`; probes false → base observers only |

Probe key `ocr` maps to observer token `text` (CONTRACTS `--observers` list).

## Human verify (machine-local)

```text
.\.venv\Scripts\python.exe -m semblon lab providers
```

1. **OCR** — `observers.ocr` is `true` only if `tesseract` is on PATH (`where.exe tesseract`).
2. **CLIP** — `observers.clip` is `true` only if open_clip + torch import **and** weights are already on disk (status never downloads).
3. **Pose** — `observers.pose` is `true` only if `mediapipe.solutions.pose` exists.

## Identity firewall

Geometry / appearance / objects / OCR / CLIP / pose must not silently change identity scores or cluster membership. Product defaults include ready optionals for **observation and retrieval only**.

## Out of scope here

Bake-off artifacts, Ruled-out lists, live overlay UI, new schema columns.
