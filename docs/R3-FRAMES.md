# R3 frames — test assets (not shipping UI)

**Authority:** `docs/R3-BRIEF.md` §7–§8.  
**Gate:** `hierarchy_frames` / `SEMBLON_GATE_HIERARCHY_FRAMES` (`semblon/gates.py`).  
**Code catalog:** `tools/r3_frames/catalog.py` (`generate_catalog()`).  
**Policy:** these are **TEST ASSETS**, not product chrome. Do not ship them as Home, `review-ui`, or a second shell. No GUI required to own the catalog.

---

## What a “frame” is

A frame is a side-by-side (or stepped) comparison that falsifies a visual / interaction rule. Reviewer hesitation on a pair = the rule or the render fails. Frames are not a design system and not a substitute for the state matrix.

| Frame set | Role | Brief |
|---|---|---|
| **Collision ledger pairs** | Distinguish confusable states | §7 + §8.3 (~15 comparison frames) |
| **State-triple grid** | Keep ingest × analysis × identity channels separate | §7 + §8.4 (30 cards) |
| **Hierarchy frames** | Clickable nesting / IA the matrix cannot express | §8.6 — **last** |

---

## §8 order (locked)

Do **not** promote hierarchy frames ahead of earlier artifacts:

1. Complete state matrix (17 components)  
2. Interaction spec (5 identity display × 7 processing)  
3. Collision ledger as comparison frames  
4. State-triple grid  
5. Toolkit bake-off (`docs/R3-BRIEF.md` §6)  
6. **Clickable hierarchy frames — LAST**

Wrong order (e.g. polish hierarchy chrome before collision frames) is a process fail even if screenshots look good.

---

## Collision ledger pairs (from §7)

Minimum pairs that must remain distinguishable. Each pair → one side-by-side comparison frame (catalog ids `collision-*`):

| Pair | Why it collides |
|---|---|
| **Disabled vs Unknown vs Processing** | Three inert-looking states; must never converge (§2) |
| **Possible vs Confirmed** | Evidence vs human affirmation |
| **Ruled out vs Ignored** | Durable reject vs deferred leave-observation |
| **Paused vs Unknown** | Static partial ring vs dashed unresolved notch |
| **Failed vs Cancelled** | Gap+`!` vs hollow+slash |

Additional confusable pairs fill out the §8.3 budget of ~15 frames (see catalog). Ellipsis in the brief is intentional — add pairs when a new control grammar risks collapse.

---

## State-triple grid (§8.4)

Every rendered asset exposes three channels:

```text
ingest status  ×  analysis status  ×  identity display notch
```

Grid size: **5 ingest × 6 analysis** cards, identity notch stepped through **5** display values → **30** cards (`triple-*` in catalog). A confusable pair that differs only by which channel changed = wrong channel assignment.

UI that collapses channels (one badge meaning “busy or unknown or ignored”) fails this set.

---

## Hierarchy frames (§8.6 — last)

Clickable frames that test information architecture and nesting the state matrix cannot express (Library vs observation layer, Group Inspector evidence vs action split, Compare progressive entry, Unknown as nested triage). Catalog ids `hierarchy-*`.

**§8.6 is last.** Attach to the R3 decision packet only after APP-1 C.3 + R2 and after collision + triple sets are walked. Wire only after human VERIFY (`docs/GATES-WIRE-PLAYBOOK.md`).

---

## Explicit non-goals

- Not shipping UI; not Tk Home polish; not a revived PySide product shell on `main` (#54).  
- Not identity conclusions — visual state must never imply an identity claim the evidence does not support.  
- Does not invent schema columns or change FaceKit compare.
