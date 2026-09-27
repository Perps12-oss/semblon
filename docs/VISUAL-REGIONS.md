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

Opening a photograph calls `on_image_open`. Pointer movement does not. Hover in `CanvasWorkspace` is a coordinate transform plus a cached row test. The highlight is a stippled mask on the existing tk canvas, plus a chip only when `selected_label` is set.

## Providers

`visual.discovery.sam2` is `UNAVAILABLE` until a local checkpoint is present (`SEMBLON_SAM2_WEIGHTS` or `~/.cache/semblon/sam2`). Nothing is downloaded. Classical colour regions are `PARTIAL` and do not invent names. SigLIP and VLM are `UNAVAILABLE`. Naming is propose → bind → abstain; abstain leaves the chip blank.

Stock box-NMS and containment-preserving dedupe are both implemented. Production default is containment. Thresholds live on `VisualConfig`.

## Not claimed

SAM2 quality on the owner’s Windows machine. Human scores on a real photo set (`semblon.visual.protocol`). GPU highlight compositing. A second GUI.
