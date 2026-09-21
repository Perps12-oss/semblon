# Artifact 2 — The state triple

**Status:** CANONICAL (owner paste 2026-09-21)  
**Authority:** asset model for Library / grid cards. Complements Artifact 1 (components).  
**Rendered test:** `04-state-triple-grid.html` (30 cards).  
**Rule:** Any UI that renders an asset without three channels is collapsing layers.

## The model

```text
Asset state = (Ingest, Analysis, Identity)
```

| Layer | Values | Owned by | Rendered as |
|---|---|---|---|
| **Ingest** | ok · failed · missing | the file system | **center glyph** |
| **Analysis** | queued · running · paused · done · failed · stale | the job system | **border / ring** |
| **Identity** | aggregate across faces: none · unknown · possible · confirmed · mixed | the identity system | **corner notch** |

## The three-channel rule

Each layer owns a distinct spatial channel on the card. **No channel carries two layers. No layer uses two channels.**

Why this is load-bearing: if identity and analysis both used the border, then paused and unknown would collide. If ingest and identity both used the center glyph, then failed and unknown would collide. The moment two layers share a channel, every pair of their states becomes an ambiguity.

```text
┌─────────────────────────┐
│ ▢ notch (identity)      │  ← corner, 6px, shape-encoded
│                         │
│                         │
│          ⚠              │  ← center glyph (ingest/error only)
│                         │
│                         │
│  [metadata strip]       │  ← hover, carries counts + reason strings
└─────────────────────────┘
  ↑ border/ring (analysis)
```

## Why identity is aggregated at the card level

A media card can contain 0, 1, or 14 faces. The notch reports the **worst unresolved** state across all faces in the asset:

| Aggregate | Notch |
|---|---|
| No faces detected | empty outline, dim |
| All faces ignored | empty outline, dim |
| Any face unknown | dashed, 6/4 |
| Any face possible | dashed, 3/2 |
| All faces confirmed | solid |
| Mixed confirmed + ruled-out | solid with `≠` sub-mark |

"Worst unresolved" is the rule because the Library grid is a **work queue**, not a status dashboard. The card's job is to say "there is something here worth opening." Once opened, the Inspector shows per-face state.

Per-face identity display (Unknown / Possible / Confirmed / Ruled out / Ignored) remains Artifact 1 §5 / brief §1.

## Transition rules

When does a card animate a state change?

| Source | Animation | Why |
|---|---|---|
| User action on this card | 160ms | the user is looking |
| User action on another card, this one visible | 160ms | peripheral reinforcement |
| Background analysis, this card selected | 160ms | the user is looking |
| Background analysis, this card visible but unselected | none | 200 cards animating is noise |
| Background analysis, this card not visible | none | it hasn't rendered yet |

When a background job completes silently:

1. Status strip pulses once (200ms, opacity 0.6→1.0)
2. Sidebar count badge increments (120ms, numeral swaps)

That is the entire notification. **No toast, no animation cascade.**

## Test grid

`04-state-triple-grid.html`: 5 ingest × 6 analysis cards × identity notch stepped through values → **30 cards**. If any two cards are confusable, channel assignments are wrong.

## Related

- Artifact 1 matrix: `01-state-matrix.md`
- Artifact 3 collisions that depend on channels: `03-collision-ledger.md`
- Identity × processing co-presentation (observation vs job): `02-interaction-cross-product.md`
