# R3 §8.1 — Complete state matrix (17 components)

**Authority:** `docs/R3-BRIEF.md` §3 (seed) + §4 IA.  
**Rule:** Any shipped component state absent from this matrix is a bug.  
**Notation:** `·` = N/A for that component. Tokens `W:0A` / `W:14` / `W:1F` / `B:12` are achromatic white/black overlays at hex alpha (brief seed).

Interaction columns (9):

| Col | Meaning |
|---|---|
| Default | Rest |
| Hover | Pointer over |
| Press | Active / down |
| Focus | Keyboard focus |
| Selected | Included in session selection |
| Disabled | Unavailable (reason on hover where noted) |
| Loading | In-flight work on this control |
| Error | Control-local failure |
| Destructive | Armed destructive path (red only when armed) |

---

## Component inventory (17)

| # | Component | Role |
|---|---|---|
| 1 | Sidebar item | Library / People / Work nav row |
| 2 | Nav section label | LIBRARY / PEOPLE / WORK heading |
| 3 | Search field | Global search |
| 4 | Media card | Library still/video tile |
| 5 | Virtualized thumb cell | Dense grid cell (10k path) |
| 6 | Face box | Observation overlay on media |
| 7 | Candidate row | Person/link candidate in inspector |
| 8 | Evidence block | Expandable evidence for a candidate |
| 9 | Primary action | Dominant confirm / submit |
| 10 | Secondary action | Non-dominant action |
| 11 | Destructive action | Split / delete / rule-out arming |
| 12 | Segmented pair | Mutually exclusive primary pair |
| 13 | Compare cell | Compare mode tile |
| 14 | Progress glyph | Job/process shape grammar |
| 15 | Inspector section header | Identity · Actions · Evidence |
| 16 | Banner | System / Compare overflow notice |
| 17 | Toast | Undo / transactional feedback |

---

## Matrix

| Component | Default | Hover | Press | Focus | Selected | Disabled | Loading | Error | Destructive |
|---|---|---|---|---|---|---|---|---|---|
| **1 Sidebar item** | text-2, no fill | `W:0A` fill | `W:14` fill | 2px ring, 2px offset | `W:1F` + 2px left rule | 40% opacity | inline 12px ring | red dot, right | · |
| **2 Nav section label** | text-3 caps, no fill | · | · | · | · | · | · | · | · |
| **3 Search field** | S2 hairline, text-2 placeholder | hairline 2× | · | ring, 2px offset | · | 40%, no caret | inline spinner trailing | reason string under field | · |
| **4 Media card** | S2, hairline | lift 1px, hairline 2× | settle, `B:12` | ring **around card** | 2px inset + notch | · | skeleton shimmer | broken-image + reason on hover | · |
| **5 Virtualized thumb** | same as media card, no lift | hairline 2× | `B:12` | ring around cell | 2px inset | · | skeleton | broken glyph | · |
| **6 Face box** | per evidence×decision display | stroke +0.5px | · | ring on box | halo, not fill | · | · | · | · |
| **7 Candidate row** | text-2 | `W:0A` | `W:14` | ring | `W:1F` + check | 40% + *reason string* | inline spinner | warning + retry | · |
| **8 Evidence block** | collapsed chevron + title | `W:0A` on header | · | ring on header | expanded = open | · | skeleton lines | “evidence unavailable” | · |
| **9 Primary action** | inverted pill | lighten 6% | darken 8% | ring, 2px offset | · | 40%, **no ring, no hover** | label → spinner, width locked | · | · |
| **10 Secondary action** | hairline, text-1 | `W:0A` | `W:14` | ring | · | 40% | inline spinner | · | · |
| **11 Destructive** | text-2 (**not red**) | text-1 | text-1 | ring | · | 40% | · | · | **armed:** text `#E5484D`, target outlined red |
| **12 Segmented pair** | two hairline cells, one active `W:1F` | inactive `W:0A` | settle | ring around pair | active cell = selected | 40% whole pair | spinner in active cell | · | · |
| **13 Compare cell** | S2 | lift | · | ring | included 100% / excluded 25%, toggle visible | 40% | · | · | · |
| **14 Progress glyph** | processing grammar (§2) | · | · | ring optional | · | · | = Processing state | Failed glyph | · |
| **15 Inspector section** | text-3 + hairline rule | · | · | · | · | · | · | · | · |
| **16 Banner** | S2 + left rule, text-2 | · | · | · | · | · | · | error banner: rule `#E5484D` | · |
| **17 Toast** | S2 elevated, text-1 + Undo | · | · | focus on Undo | · | · | · | · | · |

---

## Component notes (normative)

1. **Face box** has no disabled/loading/error — it is an observation, not a control. Identity display uses the five-state grammar only.
2. **Destructive** is never red until **armed** (long-press or second click). Red on the **object**, not chrome.
3. **Nav section label** and **Inspector section** are non-interactive chrome; no hover/press/focus.
4. **Media card** has no Disabled column — failed ingest is not a Library row (Activity). Ignored media stays in Library at full card chrome; observation-layer leave is identity **Ignored**, not card Disabled.
5. **Progress glyph** and **identity notch** are different channels. Solid ring (Completed) ≠ solid face border (Confirmed).
6. **Toast** Undo is the only focusable child by default; toast body is not a selection target.
7. **Banner** Compare overflow is informational; dismiss is secondary action inside the banner if present.
8. **Search** Error is query/backend failure, not “no people found” (empty is Default + empty state copy).
9. **Candidate row** Disabled always shows a reason string (e.g. “Select a face first.”).
10. **Virtualized thumb** must meet bake-off criterion 5 when implemented; this matrix only locks chrome states.

---

## Gaps called out (do not invent schema here)

- Durable **Ruled out** as distinct from Ignore/`reject` remains a **CONTRACTS** slice before the shell ships that decision verb.
- Counts on Library / People are materialized; matrix does not define count badges as a 18th component — badges follow Sidebar item / Media card Selected rules if shown.
