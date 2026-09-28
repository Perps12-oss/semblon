# Visual regions

Contract for the still-image hover slice. Not a plan, not a schema change, not an identity system.

## Firewall

A region may be labelled `person`, `face`, `hood`, or left unnamed. That label is not a `persons` row. FaceKit remains the only identity engine. This path does not write `faces`, `faces.person_id`, or `embeddings.modality='face'`.

Proper-name proposals are stored on the payload and are not enrolled.

## Store

No new columns.

| What | Where |
|---|---|
| VisualRegion | `observation_items` `kind='object'` `provider='visual.region'` |
| Geometry for hit-testing | `payload_json.rows` (derived owner map is not stored) |
| `contains` / `overlaps` | `relationships` `confirmed=0` |
| Revision, label, fate, provenance | `payload_json` |

`frame_id` on the existing `observations` row is how a later video frame reuses the same item shape. Track continuity is still `tracks`, and a track is not a person.

## Path

Expensive understanding runs in `JobEngine.submit_visual` (same single-job door as ingest, different kind). Home does not switch to the library-processing screen for that kind.

Opening a photograph paints first, then calls `on_image_open`. That submits `JobEngine.submit_visual` only when the single job door is free and this still has no `visual.region` rows yet. Pointer movement does not submit. The fitted photo size is the slice's view, so a speck that is not pointable on screen is dropped.

When SAM2 weights are present the job publishes a coarse map first, then replaces it with the precise pass. Cancel during the precise pass does not delete the coarse rows. Hover in `CanvasWorkspace` rebuilds the uint16 owner map from stored row-runs and looks up the pixel. The highlight is one cached mask overlay, with a chip only when `selected_label` is set. A visual face can still open the FaceKit inspector. It does not write a person.

## Providers

`visual.discovery.sam2` is `UNAVAILABLE` until a local checkpoint is present (`SEMBLON_SAM2_WEIGHTS` or `~/.cache/semblon/sam2`). Nothing is downloaded. A bad checkpoint becomes `FAILED` and does not take Home down. AMG uses `box_nms_thresh=0.95`; containment-preserving dedupe is still the product filter. Diagnostics keep `proposed` and `kept`. Classical colour regions are `PARTIAL` and do not invent names.

`visual.naming.siglip` is `UNAVAILABLE` without a local checkpoint (`SEMBLON_SIGLIP_WEIGHTS` or `~/.cache/semblon/siglip`) and a local `open_clip` or `transformers` install. Nothing is downloaded. Proposals are the hint list plus an optional `SEMBLON_NOUNS` file. A noun that does not beat an unnamed prompt stays off the chip. Proper names are not enrolled.

## Tests that need a window

Importing Home succeeds when Tk is missing. Opening the window does not. `libtk8.6` has to be present, and the pass that matters is production Home on Windows, not a headless suite.

- `tests/test_home_ui.py` (window tests; headless readers import once Tk's import error is caught)
- `tests/test_jobs.py` where a test constructs `HomeApp` or `ReviewApp`
- `tests/test_application.py` only if a test opens a window

`tests/test_visual_regions.py` does not need Tk. It does not prove a hand on a real photograph.

## Not claimed

SAM2 quality on the owner’s Windows machine. A filled sheet (`semblon.visual.protocol`). GPU highlight compositing. A second GUI.

The sheet starts blank: image, scene, what you expected to point at, whether that piece was proposed, kept, exposed, and whether the highlight matched. Too fragmented, too broad, a missing nested part, unnamed, and whether a word was right, are separate notes. Analysis time and a rendering note sit on the same row. One bad interaction gets one class: `DISCOVERY`, `LATTICE`, `SLICE`, `RENDERER`, or `NAMING`. Windows version, process architecture, native or emulated, torch, DirectML, checkpoint, and whether Home launched belong on `session_header()`, which is also blank until that machine fills it.
