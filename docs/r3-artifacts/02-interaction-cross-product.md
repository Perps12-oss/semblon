# R3 §8.2 — Identity display × processing grammar (cross-product)

**Authority:** `docs/R3-BRIEF.md` §1 (five display states) × §2 (seven processing states).  
**Purpose:** Full 5×7 = 35 cells. Mark legal co-presentation vs illegal (must not paint).  
**Rule:** Visual state must never imply an identity conclusion the evidence does not support. Processing is **shape**; identity is **notch + stroke texture**.

## Axes

### Identity display (5)

| State | Border | Notch |
|---|---|---|
| Unknown | dashed 6/4 | empty outline |
| Possible | dashed 3/2 | half-filled |
| Confirmed | solid | solid |
| Ruled out | dashed 6/4 + `≠` | empty + slash |
| Ignored | none, 35% opacity | none |

### Processing (7)

| State | Glyph |
|---|---|
| Queued | hollow ring |
| Processing | partial ring, animated (or marked “anim”) |
| Paused | partial ring, static + pause bar |
| Completed | solid ring |
| Failed | ring with gap + `!` |
| Cancelled | hollow ring + slash |
| Stale | dotted ring |

---

## Cross-product

Legend:

- **OK** — may appear together (identity on observation; processing on job/control).
- **SEP** — legal only if channels stay spatially separate (e.g. progress on toolbar, notch on face). Same widget must not merge them.
- **NO** — illegal co-presentation; would smuggle identity into processing or collapse Disabled/Unknown/Processing.

| | Queued | Processing | Paused | Completed | Failed | Cancelled | Stale |
|---|---|---|---|---|---|---|---|
| **Unknown** | SEP | SEP | SEP | SEP | SEP | SEP | SEP |
| **Possible** | SEP | SEP | SEP | SEP | SEP | SEP | SEP |
| **Confirmed** | SEP | SEP | SEP | SEP | SEP | SEP | SEP |
| **Ruled out** | SEP | SEP | SEP | SEP | SEP | SEP | SEP |
| **Ignored** | SEP | SEP | SEP | SEP | SEP | SEP | SEP |

All 35 cells are **SEP**, not **OK-merged**. There is **no** cell where one glyph means both identity and processing.

### Explicit NO patterns (even if someone “simplifies”)

| Pattern | Verdict | Why |
|---|---|---|
| Hollow ring alone as Unknown | **NO** | Queued/Cancelled are hollow; Unknown needs dashed border + empty notch |
| Solid ring as Confirmed | **NO** | Completed ≠ Confirmed |
| Opacity-only face as Disabled control | **NO** | Ignored is 35% observation leave; Disabled is control unavailability |
| Paused partial ring without pause bar as Unknown | **NO** | Paused vs Unknown must share no visual property |
| Failed `!` ring as Ruled out `≠` | **NO** | Different marks, different channels |
| Stale dotted ring as Ignored | **NO** | Stale = analysis freshness; Ignored = human deferred |
| Processing animation on face box implying Possible | **NO** | Face box has no Loading column |

### When both channels show on one card

Typical **state triple** (see §8.4): ingest status × analysis status × identity notch.  
Processing grammar maps to **ingest** and/or **analysis** channels; identity notch is only the third channel.

| Channel | Uses |
|---|---|
| Ingest | Queued / Processing / Paused / Completed / Failed / Cancelled (job door) |
| Analysis | Queued / Processing / Completed / Failed / Stale (detect/embed/cluster) |
| Identity | Unknown / Possible / Confirmed / Ruled out / Ignored |

Paused on ingest does not change the identity notch. Failed analysis does not auto-paint Ruled out.

---

## Evidence-ack note (Enter)

Confirming Possible → Confirmed via `Enter` is a **decision** transition, not a processing glyph change. Processing may still show Completed on the ingest job independently.
