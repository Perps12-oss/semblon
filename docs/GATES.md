# Semblon feature gates

**Module:** `semblon.gates`  
**Status:** **WIRED** 2026-09-21 (human verify). Product defaults are **ON**.  
**Opt out:** set env to `0` / `false` / `no` / `off`.

```python
from semblon.gates import enabled, require_human_note, LIVE_OVERLAY

if not enabled(LIVE_OVERLAY):
    raise RuntimeError(require_human_note(LIVE_OVERLAY))
```

## Flags

| Env | Constant | Default | Purpose |
|---|---|---|---|
| `SEMBLON_RULED_OUT` | `RULED_OUT` | **ON** | Ruled out review verb (not Ignore) |
| `SEMBLON_LIVE_OVERLAY` | `LIVE_OVERLAY` | **ON** | Live overlay lab/CLI |
| `SEMBLON_WIRE_HOME_LIVE` | `WIRE_HOME_LIVE` | **ON** | Home **Live…** button (explicit click; no auto-webcam) |
| `SEMBLON_MODALITY_PRODUCT` | `MODALITY_PRODUCT` | **ON** | Productized optional OCR/CLIP/pose: Settings rich status + probe-gated ingest defaults |
| `SEMBLON_BAKEOFF_WINNER` | `BAKEOFF_WINNER` | **ON** | Authorize R3 shell decision path — does **not** invent WinUI vs Qt |

Bake-off runners and CI must never write `SEMBLON_BAKEOFF_WINNER`. Human still names the toolkit in SEM-ARCH.

## API

- `enabled(name) -> bool` — unset → ON; explicit falsy → OFF; unknown → False.
- `require_human_note(name) -> str` — wiring note; unknown raises `KeyError`.
- `wired_default() -> bool` — always True after human wire.

See `docs/HUMAN-VERIFY-THEN-WIRE.md` for the verify record.
