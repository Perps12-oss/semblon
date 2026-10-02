# Semblon Atmosphere & Motion System

Product contract for visual identity on the existing Tk Home / Canvas architecture.
Opaque Tk — no Windows Mica/Acrylic APIs. “Mica Dark” is a palette atmosphere.

## Pipeline

```text
Atmosphere → InteractionState → VisualTokens → AtmosphereRenderer
```

Owner modules: `semblon/atmosphere.py`, `semblon/atmosphere_render.py`.
Prefs: single `appearance.json` `theme` key (`semblon/ui_prefs.py`).

## Atmospheres

| Id | Role |
|---|---|
| `light` | Compatibility light |
| `mica_dark` | Default dark — quiet slate / sapphire |
| `cyber_obsidian` | Near-black / electric cyan |
| `neon_ember` | Warm darkroom / amber |
| `tokyo_synth` | Ink-violet / magenta + emerald dual-tone |

Stored modes: `system`, `light`, `dark` (alias → `mica_dark`), plus the four atmosphere ids.
`system` + OS dark → `mica_dark`. Unknown OS theme → `light`.

## InteractionState

| State | Semantics |
|---|---|
| `RESTING` | Quiet; no glow; no continuous motion |
| `HOVER` | Local illumination; clears on leave |
| `SELECTED` | Persistent accent edge / aura; survives leave |
| `PROCESSING` | Only continuous-motion-justified state |
| `DISABLED` | Recedes; no glow / elevation |

Hover and selected must never be visually conflated.

## Visual hierarchy

```text
PHOTO / MEDIA
  → SELECTED REGION
  → CONTEXTUAL ACTION
  → APPLICATION CHROME
  → AMBIENT ATMOSPHERE
```

## Governing product structure (LOCKED — Model D)

Bound to `docs/SHELL-IA.md`. Atmosphere is not decoration; it follows shell IA:

```text
Stage  →  Transition (dissolve)  →  Memory Canvas  →  contextual discovery
```

| Phase | Atmosphere purpose |
|---|---|
| **Stage** | Expressive capability illumination and interaction (empty / first-run / brand return) |
| **Transition** | Atmosphere dissolves with the Stage into Memory — not a hard page swap |
| **Memory Canvas** | Media dominates; application chrome becomes submerged |
| **Hover** | Local illumination (`HOVER`) |
| **Selection** | Elevation / bloom (`SELECTED`) — never conflated with hover |
| **Processing** | Ambient system state (`PROCESSING`) while busy only |
| **Contextual discovery** | Focused visual response on region / action / result |

Stage must not merely navigate to Library. The dissolve is the product moment: Semblon introduces itself; then visual memory *is* the application.

## Capability levels

| Level | When | Behavior |
|---|---|---|
| `full` | Motion allowed | Spotlight rings, pulse/sweep, dual-tone step, theme lerp, preview demo |
| `reduced` | OS/user reduced motion | Static token swaps; no continuous pulse; theme snap |
| `static` | Tests / headless | Tokens only; deterministic |

Probe: `semblon.atmosphere_render.detect_capability()`.

## Effect contracts

### Radial spotlight

**Contract:** cursor (x,y) → local atmospheric illumination → surfaces/regions under influence → intensity by InteractionState.

**Owner:** `atmosphere_render.Spotlight`

**Tk implementation:** concentric Canvas ovals / soft disk (alpha rings). Radius and intensity from atmosphere tokens.

**Blocked by Tk:** true GPU bloom, acrylic blur, sub-pixel shaders.

**Fallback:** opaque layered fills + alpha ring approximation (same contract).

**Acceptance:** moving the pointer over chrome/region brightens only the local area; idle has no spotlight.

### Processing pulse / dual-tone

**Contract:** while processing, footer and initiating control show restrained motion; Tokyo alternates accent A/B; stops when idle → Ready.

**Owner:** `atmosphere_render.ProcessingCue`

**Tk:** `after()` tick with atmosphere `processing_period_ms`.

**Reduced-motion:** static processing tint + copy only.

**Acceptance:** pulse runs only while busy; no perpetual animation after completion.

### Theme interpolation

**Contract:** current atmosphere → short transition → target; ~250ms starting target.

**Owner:** `atmosphere_render.transition_to`

**Tk:** lerp interpolable hex fields via `after` steps; fonts/radii snap.

**Reduced-motion:** immediate `publish`.

**Acceptance:** Appearance change does not hard-flash when motion is allowed.

### Appearance preview theatre

**Contract:** each atmosphere tile uses the same `resolve()` + renderer demo cycle (rest → hover → selected → processing + region glyph).

**Owner:** `atmosphere_render.PreviewTheatre` + Home Settings Appearance.

**Acceptance:** selecting a tile applies that atmosphere via `transition_to`; preview is not a fake hex swatch.

## Tk-constrained approximations (not a polish backlog)

| Intended | Blocked | Fallback | Owner | Acceptance |
|---|---|---|---|---|
| Windows Mica/Acrylic blur | No WinUI material in opaque Tk | Layered opaque surfaces + mist mixes | `atmosphere.py` tokens | Depth readable without system backdrop |
| HDR neon bloom | No GPU bloom | Accent alpha rings | `Spotlight` / region paint | Selection/hover readable, not blown out |
| Shader spotlight | No fragment shaders | Concentric disk rings | `Spotlight` | Local illumination follows pointer |

## Performance

Pointer path: existing region lookup → id → state → visual response. No model / DB work on hover.
No global animation loop unless a processing cue or transition is active.
