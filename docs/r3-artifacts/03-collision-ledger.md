# Artifact 3 — Collision ledger

**Status:** CANONICAL (owner paste 2026-09-21)  
**Authority:** test plan for visual language.  
**Rendered frames:** `03-collision-frames.html` (15 side-by-side pairs).  
**Rule:** Reviewer hesitation on any pair = the rule is wrong or the rendering is.

Every pair of states that could be confused, and the rule that separates them. **Test against the frames, don't only read the table.**

| # | Ambiguous pair | Why they collide | Rule that separates them |
|---|---|---|---|
| 1 | Disabled vs Unknown | both are inert, desaturated | Disabled has **no border**. Unknown has a **border**. Silhouette, not color. |
| 2 | Unknown vs Processing | both are unresolved | Unknown is **static**. Processing **animates** (or is explicitly paused, with a pause bar). |
| 3 | Processing vs Possible | both carry partial information | Processing is a **border** state. Possible is a **notch** state. Different channel. |
| 4 | Paused vs Failed | both are stopped mid-operation | Paused is **symmetric**. Failed has a **gap + !**. |
| 5 | Paused vs Unknown | both are "waiting" | Paused is a **ring**. Unknown is a **notch**. |
| 6 | Failed (analysis) vs Missing (ingest) | both mean "can't proceed" | Analysis failed = **ring gap**. Ingest missing = **center glyph**. |
| 7 | Ignored vs Disabled | both are "not active" | Ignored has 35% opacity + no border. Disabled has 40% + no border. Nearly identical — so: **ignored assets never appear in a grid where disabled controls appear**. Separate surfaces. |
| 8 | Ruled out vs Unknown | both are "no identity" | Unknown is dashed. Ruled out is dashed + `≠`. The mark is mandatory. |
| 9 | Ruled out vs Possible | both are dashed | Possible is dash **3/2** with half-fill notch. Ruled out is dash **6/4** with empty notch + `≠`. |
| 10 | Confirmed vs Selected | both are strong | Confirmed is a **notch**. Selected is an **inset rule**. Never the same channel. |
| 11 | Stale vs Unknown | both are "not fresh" | Stale is a **dotted ring**. Unknown is a **dashed notch**. |
| 12 | Destructive-armed vs Error | both use red | Destructive red appears on the **target object**. Error red appears as a **glyph**, never a border, never on a button. |
| 13 | Primary vs Selected | both are high-contrast | Primary is an **inverted pill** (a shape). Selected is a **fill + rule** (a container). Different silhouettes. |
| 14 | Possible vs Stale | both are "mid" states | Different channels: **notch** vs **border**. |
| 15 | Mixed identity (solid + ≠) vs Ruled out (dashed + ≠) | both carry ≠ | Mixed is **solid**. Ruled out is **dashed**. The ≠ is a suffix, not the state. |

## Six governing rules

1. **No layer shares a channel with another layer.** (Artifact 2)
2. **No two states share a silhouette.** (Disabled / Unknown / Processing)
3. **Red is never chrome.** (Destructive vs Error)
4. **Dashed frequency is semantic.** 6/4 = undecided or rejected; 3/2 = uncertain-but-active; solid = decided; dotted = stale.
5. **Shape is the carrier; color is redundant.** If a state fails in grayscale, it fails.
6. **Marks are suffixes, not states.** `≠` and `!` modify; they don't define.

## Related

- Frames HTML: `03-collision-frames.html`
- State triple channels: `02-state-triple.md`
- Component treatments: `01-state-matrix.md`
