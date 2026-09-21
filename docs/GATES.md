# Semblon feature gates

**Module:** `semblon.gates`  
**Policy:** CODE NOW scaffolds ship behind flags. All gates default **OFF**. Human verify authorizes wiring (flipping defaults / Home entry).

Import helpers — do not invent parallel env checks:

```python
from semblon.gates import enabled, require_human_note, LIVE_OVERLAY

if not enabled(LIVE_OVERLAY):
    raise RuntimeError(require_human_note(LIVE_OVERLAY))
```

## Flags

| Env | Constant | Purpose | When a human may flip |
|---|---|---|---|
| `SEMBLON_RULED_OUT` | `RULED_OUT` | Ruled-out review scaffold | After reject-vs-ignore semantics verify |
| `SEMBLON_LIVE_OVERLAY` | `LIVE_OVERLAY` | Live multi-person overlay lab/CLI | After real webcam/RTSP 2-person verify |
| `SEMBLON_WIRE_HOME_LIVE` | `WIRE_HOME_LIVE` | Home → live overlay entry (stronger) | **Only after** overlay verify passes |
| `SEMBLON_MODALITY_PRODUCT` | `MODALITY_PRODUCT` | Non-identity modality as product UI | After honesty verify (no identity vote) |
| `SEMBLON_BAKEOFF_WINNER` | `BAKEOFF_WINNER` | R3 bake-off winner selected | Human-named only — **must not auto-set** |

Truthy values: `1`, `true`, `yes`, `on` (case-insensitive). Anything else / unset → OFF.

## API

- `enabled(name) -> bool` — fail-closed; unknown names are False.
- `require_human_note(name) -> str` — human-verify text; unknown names raise `KeyError`.

## Agent contract

- Wire scaffolds to `enabled(...)`; leave product defaults OFF.
- Do not rewrite `live.py` / `observers.py` / `review.py` just to import gates unless a tiny gate check is essential.
- Do not auto-set `SEMBLON_BAKEOFF_WINNER` from bake-off runners or CI.
- Flipping a default or adding Home entry is a **human** authorization step, not an agent merge.
