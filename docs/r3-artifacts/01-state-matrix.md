# Artifact 1 — Full state matrix (17 × 9)

**Status:** CANONICAL (owner paste 2026-09-21)  
**Authority:** supersedes the abbreviated seed in `docs/R3-BRIEF.md` §3 for component inventory and treatments.  
**Roadmap:** `docs/SEM-ARCH-V1.4.md` · visual contract `docs/R3-BRIEF.md`.  
**Rule:** Any shipped component state absent from this matrix is a **bug**, not a feature.  
**Rule:** A state that cannot justify its existence is a state that will be abused — see **Why** columns.

## Notation

| Token | Meaning |
|---|---|
| `W:0A` | white at ~10% alpha (dark theme) |
| `W:14` / `W:1F` / `W:24` | white overlays at hex alpha |
| `B:12` / `B:08` | black overlays; light theme inverts `W:0A` → `B:08` |
| `S0`–`S3` | surface tokens |
| `ring` | focus treatment — adaptive dual-ring (Artifact 2 / brief) |
| `·` / N/A | state does not apply to this component |

Interaction columns (9): Default · Hover · Press · Focus · Selected · Disabled · Loading · Error · Destructive.

---

## Component inventory (17)

| # | Component | Role |
|---|---|---|
| 1 | Sidebar item | Library / People / Work nav row |
| 2 | Person card | Named / hypothesized person tile |
| 3 | Face card | Face observation tile |
| 4 | Media card | Library still/video tile |
| 5 | Face box | Canvas overlay observation |
| 6 | Candidate row | Person/link candidate in Inspector |
| 7 | Primary action | Dominant confirm / submit |
| 8 | Secondary action | Non-dominant action |
| 9 | Merge | Inspector verb |
| 10 | Split | Inspector verb |
| 11 | Name | Inspector verb (inline field, not modal) |
| 12 | Ignore | Inspector verb (deferral) |
| 13 | Compare cell | Compare mode tile |
| 14 | Inspector (panel) | Container; children carry interactive state |
| 15 | Progress | Status strip + Activity surface (shape grammar) |
| 16 | Toast | Undo / transactional / warning feedback |
| 17 | Dialog / confirmation | Only outside undo horizon |

---

## 1. Sidebar item

| State | Treatment | Why |
|---|---|---|
| Default | text-2, no fill, 32px | |
| Hover | `W:0A` fill, text-1 | |
| Press | `W:14` fill | |
| Focus | 2px **inset** ring (flush to sidebar edge) | external ring would clip |
| Selected | `W:1F` fill + 2px left rule at x=0 | rule is the persistent marker; fill is reinforcement |
| Disabled | 40% opacity, cursor default, no hover | navigation is never disabled — this state exists only for permission-gated surfaces (none currently) |
| Loading | count badge → 12px spinner | preserves label position |
| Error | not applicable | |
| Destructive | not applicable | |

---

## 2. Person card

| State | Treatment | Why |
|---|---|---|
| Default | S2, 1px hairline, cover face, name text-2, count text-3 | |
| Hover | hairline → `W:24`, name → text-1, cover scales 1.02 @140ms | the scale tells you the card is a thing you'll open |
| Press | `B:12` fill, scale returns to 1.0 | |
| Focus | 2px ring around card, 2px offset | |
| Selected | `W:1F` + 2px inset rule + check notch (top-right) | |
| Disabled | not applicable | |
| Loading | skeleton: name as 60%-width bar, cover as blurred low-res | |
| Error | cover failed → neutral avatar silhouette; name intact | an unnamed person still has a name slot |
| Destructive | armed: card outline `#E5484D`, content unchanged | red targets the object, not the button |

---

## 3. Face card

| State | Treatment | Why |
|---|---|---|
| Default | crop, hairline | |
| Hover | hairline → `W:24` | |
| Press | `B:12` | |
| Focus | ring | |
| Selected | `W:1F` + inset rule + check | |
| Disabled | not applicable | a face is an observation; observations are never unavailable |
| Loading | blurred placeholder at detection resolution | |
| Error | broken image glyph | |
| Destructive | rule-out mode (X held): `≠` mark, no red | rejection is not destruction |

---

## 4. Media card

| State | Treatment | Why |
|---|---|---|
| Default | S2, hairline, correct-aspect thumbnail, metadata strip hidden | |
| Hover | 1px lift, hairline → `W:24`, metadata strip slides up @140ms | the strip is the reward for attention |
| Press | settle, `B:12` | |
| Focus | ring around card | |
| Selected | 2px inset rule + notch | |
| Disabled | not applicable | |
| Loading | skeleton shimmer; no motion if `prefers-reduced-motion` | shimmer is the one place motion carries information |
| Error | broken-image glyph + reason string in hover strip | reason is mandatory — "can't decode HEVC" ≠ "file missing" |
| Destructive | armed: outline red | |

---

## 5. Face box (canvas overlay)

| State | Treatment | Why |
|---|---|---|
| Default | per evidence axis: halo + semantic stroke + notch | three-layer, media-adaptive |
| Hover | stroke +0.5px, label appears above | label gives identity + evidence type |
| Press | not applicable | the box is not the control; selection is |
| Focus | 2px ring on box, 2px offset | |
| Selected | halo (external glow), not fill | fill would obscure the face — the thing being judged |
| Disabled | not applicable | |
| Loading | not applicable | |
| Error | not applicable | |
| Destructive | not applicable | |

Face box is the only component with four N/As. That's the point: it's an **observation**, not a control. Give it control states and the language collapses.

Identity display grammar (evidence × decision) still applies to the default stroke/notch — see `docs/R3-BRIEF.md` §1 and Artifact 2 notch aggregation.

---

## 6. Candidate row

| State | Treatment | Why |
|---|---|---|
| Default | text-2, 40px height, score right-aligned tabular | |
| Hover | `W:0A`, text-1 | |
| Press | `W:14` | |
| Focus | inset ring | |
| Selected | `W:1F` + check | |
| Disabled | 40% opacity + reason string on hover | silent disabled is the most common a11y failure in pro tools |
| Loading | inline 12px spinner replacing the score | layout doesn't shift |
| Error | warning glyph + retry affordance inline | never a toast for a row-level failure |
| Destructive | not applicable | a candidate cannot be destroyed — it can be ruled out, which is a decision |

---

## 7. Primary action

| State | Treatment |
|---|---|
| Default | inverted pill: bg `#F2F2F3` / text `#1B1B1D` (dark) — inverts in light |
| Hover | lighten 6% |
| Press | darken 8% |
| Focus | 2px ring, 2px offset |
| Selected | not applicable |
| Disabled | 40%, no ring, no hover, reason in tooltip |
| Loading | label → spinner, width locked |
| Error | returns to default; failure surfaces as warning toast. A button that holds its own error is a button nobody trusts. |
| Destructive | primary is **never** destructive — that's what the segmented pair exists for |

---

## 8. Secondary action

Same grammar as primary, with **hairline + text-1** base.

Difference: secondary may sit next to a destructive sibling (e.g. Cancel next to Delete). In that case secondary stays **achromatic**; the destructive sibling carries the red.

---

## 9–12. Merge · Split · Name · Ignore

Inspector verbs — not generic buttons. They share primary/secondary grammar with surface-specific rules:

| Verb | When primary | When disabled | Reason shown |
|---|---|---|---|
| **Merge** | ≥2 items, same cluster | <2 items | "Select 2 or more items" |
| **Split** | a cluster is selected | single face selected | "Select a cluster to split" |
| **Name** | a face or cluster is selected | nothing selected | — |
| **Ignore** | never primary | never disabled | deferral is always available |

**Name** opens an **inline field**, not a modal. Enter commits, Esc cancels, no dialog.

`Merge observations` ≠ `Assign to person` (separate actions; see brief §4 Group Inspector).

---

## 13. Compare cell

| State | Treatment |
|---|---|
| Default | S2, subject fills |
| Hover | 1px lift |
| Press | `B:12` |
| Focus | ring |
| Selected | not applicable — inclusion is the toggle, not selection |
| Included | 100% opacity, toggle visible |
| Excluded | 25% opacity, toggle still visible, border dashed |
| Disabled | not applicable |
| Loading | video cells only: scrubbing spinner in footer |
| Error | representative frame broken → fallback to first detected frame |
| Destructive | not applicable |

Visible exclusion is the feature. If an excluded cell vanished, the user couldn't audit their own reasoning.

---

## 14. Inspector (panel)

| State | Treatment |
|---|---|
| Default | S1, 1px left hairline |
| Hover / Press / Focus / Selected / Disabled | not applicable — the panel is a container; children carry state |
| Loading | skeleton blocks for evidence grid |
| Error | "Evidence unavailable" block, one line, retry link |
| Destructive | not applicable |

---

## 15. Progress (status strip + Activity surface)

Shape-based, never hue-based:

| State | Glyph | Motion |
|---|---|---|
| Queued | hollow ring | none |
| Processing | partial ring, sweep | yes |
| Paused | partial ring, static, pause bar | none |
| Completed | solid ring | none |
| Failed | ring with gap + `!` | none |
| Cancelled | hollow ring + slash | none |
| Stale | dotted ring | none |

Every state survives grayscale and reduced-motion.

Progress glyph and identity notch are **different channels** (Artifact 2). Solid ring (Completed) ≠ solid face border (Confirmed).

---

## 16. Toast

| State | Treatment |
|---|---|
| Default | S3 + shadow, text-1, action button, auto-dismiss 6s (info) |
| Hover | dismiss timer pauses |
| Press / Focus / Selected | not applicable at the toast level; the action button carries them |
| Disabled | not applicable |
| Loading | not applicable |
| Error | warning glyph left-aligned, no auto-dismiss |
| Destructive-confirming | action required, no auto-dismiss, manual close only |

---

## 17. Dialog / confirmation surface

Only for operations **outside the undo horizon** — currently: deleting source files, clearing caches, resetting the identity graph. **Never** for identity operations (those are inline + transactional undo).

| State | Treatment |
|---|---|
| Default | S3 + scrim `B:60`, 480px, centered |
| Hover / Press / Focus | children carry them |
| Selected | not applicable |
| Disabled | not applicable |
| Loading | confirm button → spinner, width locked |
| Error | inline, above the buttons, never a second dialog |
| Destructive | confirm button is destructive-armed (red text), target object named explicitly (e.g. "Delete Maya R. and 14 face assignments?") |

---

## Normative notes

1. Destructive is never red until **armed**. Red on the **object**, not chrome (Artifact 3 rule 3).
2. Disabled controls that exist must show a **reason** (tooltip / hover string).
3. Failed ingest is **not** a Library media card — it lives in Activity (brief §4).
4. Counts on Library / People are materialized; badges follow Sidebar loading/selected rules when shown.
5. Durable **Ruled out** as a product ship claim remains SEM-ARCH §I.5 last; visual grammar here is authorized for shell chrome work.

## Related artifacts

- Artifact 2 — state triple: `02-state-triple.md`
- Artifact 3 — collision ledger: `03-collision-ledger.md` (+ frames HTML)
- Artifact 4 — bake-off criteria: `05-bake-off-checklist.md`
