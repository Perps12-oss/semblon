# R3 Brief v2 — production shell visual + interaction contract

**Status:** APPROVED (owner review 2026-09-21)  
**Authority:** visual / interaction language. Does **not** replace `docs/ARCHITECTURE.md` or `docs/SEM-ARCH-V1.4.md`.  
**Shell:** production UI is the completed PySide6 baseline (2026-10-05). This brief does not authorize a second shell.  
**Sequencing:** R2 IPC probe DONE · Artifacts 1–4 CANONICAL · human gates (C.3 / bake-off / §8.7 / Ruled-out) **CLOSED / DONE** (`SEM-ARCH-V1.4` §I.5) → architecture migration **COMPLETE**.  
**Still refused:** schema columns from this brief alone; Electron / Tauri / permanent Tk AppShell / CustomTkinter; promoting `review.html` to product UX; promoting `tools/s8_toolkit_spike` to the product shell.

Governing constraints:

> Visual state must never imply an identity conclusion the evidence does not support.

> The UI must be able to say *no* as clearly as it says *yes*, and it must remember having said it.

---

## 1) Two orthogonal axes (not one ladder)

v1 collapsed identity into `UNKNOWN → POSSIBLE → CONFIRMED`. That smuggles an evidence claim into a decision slot. Semblon has **two axes**:

| Axis | Question | Values | Source of truth |
|---|---|---|---|
| **Evidence** | What does the system observe? | none · detected · similar · clustered | the machine |
| **Decision** | What has the human ratified? | undecided · affirmed · rejected · deferred | the person |

### Display matrix (five display states)

| | Human undecided | Human affirmed | Human rejected | Human deferred |
|---|---|---|---|---|
| **No evidence** | **Unknown** | — (impossible) | — | **Ignored** |
| **Weak / similar** | **Possible** | **Confirmed** | **Ruled out** | **Ignored** |
| **Strong / clustered** | **Possible** | **Confirmed** | **Ruled out** | **Ignored** |

- Keep adjectival **Possible** (not noun “Candidate”). Label the **link**: e.g. `Possible: Maya R. (0.71)`.
- **Ruled out** is first-class: durable negative decision. Without it, dismissed and never-considered are the same bit.
- **Ignored** is deferred / leave observation layer; media stays in Library.
- Today’s store: `decisions` + Ignore as `reject`+policy (`docs/CONTRACTS.md`). **Ruled out** named CONTRACTS slice: `docs/CONTRACTS-RULED-OUT.md` (`kind=reject` + `action=rule_out`; gate default ON via `semblon.gates`, opt out `=0`; product chrome **WIRED** on Home Inspector + review-ui; **ship claim CLOSED / DONE** — `SEM-ARCH-V1.4` §I.5). Do not invent columns from this brief alone.
### Visual grammar (identity display)

| State | Border texture | Notch |
|---|---|---|
| Unknown | dashed, 6/4 gap | empty outline |
| Possible | dashed, 3/2 gap | half-filled |
| Confirmed | solid | solid |
| Ruled out | dashed 6/4 + `≠` | empty + slash |
| Ignored | none, 35% opacity | none |

Validate at the **smallest rendered face size**, not in a design frame.

### Three-layer media-adaptive overlay

Overlays sit on uncontrolled media color. Per-box stroke:

```text
outer halo  — 1.5px · inverse luminance of local crop mean
semantic    — 1.5px · state color (reinforces; not load-bearing)
notch/shape — primary carrier (texture + mark)
```

---

## 2) Disabled ≠ Unknown ≠ Processing

Three inert-looking states must never converge:

| | Looks like | Carries | Distinguisher |
|---|---|---|---|
| **Disabled** | 40% opacity, no affordance | unavailable | silent, inert, **no border** |
| **Unknown** | dashed neutral, notch | unresolved, asking | **bordered, notched, textured** |
| **Processing** | partial ring | working | **shape-based**, animated or explicitly paused |

Disabled controls carry a **reason** on hover (e.g. Merge → “Select 2 or more items.”).

### Processing grammar (shape, not hue)

| State | Glyph |
|---|---|
| Queued | hollow ring |
| Processing | partial ring, animated sweep |
| Paused | partial ring, static + pause bar · `Paused · 37%` |
| Completed | solid ring |
| Failed | ring with gap + `!` |
| Cancelled | hollow ring + slash |
| Stale | dotted ring |

Survives grayscale. `Paused` and `Unknown` share no visual property.

---

## 3) State matrix (canonical — Artifact 1)

Component × interaction states. Full treatments live in **`docs/r3-artifacts/01-state-matrix.md`** (owner paste; **supersedes** the abbreviated seed formerly in this section). `·` = N/A. Any shipped component state absent from that matrix is a bug.

### Component inventory (17)

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

Interaction columns (9): Default · Hover · Press · Focus · Selected · Disabled · Loading · Error · Destructive.

Notes:

1. Face box has **no** disabled/loading/error — it is an observation, not a control.
2. Destructive is never red until **armed** (long-press or second click). Red on the **object**, not chrome.
3. Treatments for all **17 components** are locked in Artifact 1; do not invent chrome states outside that matrix.

**State matrix = spec. Clickable frames = test.** Hierarchy is mostly what the matrix cannot express.

---

## 4) Information architecture (kept)

```text
┌─ SEMBLON ──────────────────────── Search ─ ⚙ ─┐
│ LIBRARY       │  WORKSPACE / INTELLIGENCE CANVAS │
│  Home         │  media or person surface         │
│  Photos       │  ─────────────────────────────── │
│  Videos       │  INSPECTOR (on selection)        │
│ PEOPLE        │  identity · actions · evidence   │
│  People       │                                  │
│  Unknown      │  (nested triage destination)     │
│ WORK          │                                  │
│  Activity     │                                  │
└───────────────┴──────────────────────────────────┘
```

**Kept from v1:** achromatic chrome · semantic palette with L\* correction · Compare as canvas mode · Unknown as nested triage · nav structure · opaque media surfaces · no identity modals · no second Review app · no Tk AppShell · bulk naming · keyboard-first review.

### Library vs observation layer

> **Library is the source-media layer. People/Unknown is the identity-observation layer derived from it.**

- `All media` = every successfully ingested file, **including** zero-face files.
- Videos = **one asset**, many observations.
- Failed ingest lives in Activity, not as a Library row.
- Ignored media stays in Library; it leaves the observation layer.

Counts: **materialized**, incrementally maintained after committed mutations. Never recomputed per render.

### Group Inspector — never merge person and cluster

**Evidence relationship** (machine): similarity · cluster membership · candidate person · existing human decision  

**Proposed action** (human): Merge observations · Assign to person · Create person · Split · Rule out · Ignore  

`Merge observations` ≠ `Assign to person`. Separate buttons. Never imply “Semblon knows this is the same person.”

---

## 5) Interaction rules

### Evidence-acknowledged confirmation

`Enter` confirms the top candidate **only if** one of:

1. Evidence block expanded at least once this session for this person, **or**
2. Candidate row focused ≥ 900 ms, **or**
3. Face box hovered at least once (similarity reason shown).

Otherwise `Enter` opens evidence. Second `Enter` confirms. Encodes: wrong identity > unknown.

Candidate row always shows: name · evidence type · score **and margin to #2** · one-line reason.

### Compare — progressive entry

- `C` with ≤ 8 → enter Compare.
- `C` with > 8 → enter with first 8; banner *“N items not shown — adjust selection.”* Prune in place.
- Cross-surface selection allowed (face crops + person clusters).
- Selection is session-level; survives navigation.
- Video representatives freeze at entry; frame change is explicit.
- Excluded cells stay visible at 25% (audit own reasoning).

### Undo — transactions

`Ctrl+Z`. Unit = **one user gesture**, not one row. Merge of 14 faces restores atomically: prior decision states, cluster memberships, target person existence/value, candidate lists. Promise = **50 gestures**. Bulk create labels scope: `Create person from 14 selected faces` → toast with Undo.

### Primary actions

At most one dominant control; mutually exclusive actions may be a **segmented pair**. Dual-ring adaptive focus.

### Mica

Surface 0 defines target tonal range. Mica where OS supports it; opaque achromatic fallback. Deterministic.

---

## 6) Toolkit bake-off (six criteria — measure, don’t prefer)

Pass/fail before choosing WinUI / Qt / other:

1. Fully suppress OS accent in every native control (focus, selection, toggle, progress).
2. Opaque achromatic surface over Mica without bleed.
3. < 16 ms frame time on 4K/60 video scrub.
4. WCAG AA on all custom controls, both themes.
5. 10k-thumbnail virtualized grid without jank.
6. Native accessibility tree on custom-drawn surfaces (face boxes, compare cells).

Rejected still: Electron, Tauri, permanent Tk AppShell, CustomTkinter.

---

## 7) State triple + collision ledger (test assets)

**State triple (Artifact 2):** every rendered asset exposes three channels — ingest × analysis × identity. Spec: `docs/r3-artifacts/02-state-triple.md`. Rendered test: `docs/r3-artifacts/04-state-triple-grid.html` (30 cards). UI that collapses channels is wrong.

**Collision ledger (Artifact 3):** pairs that must remain distinguishable. Spec: `docs/r3-artifacts/03-collision-ledger.md`. Frames: `docs/r3-artifacts/03-collision-frames.html` (15 pairs). Reviewer hesitation = rule or rendering fails.

---

## 8) Artifacts (Artifacts 1–4 canonical; order locked)

1. ~~**Complete state matrix** for all 17 components.~~ **DONE / CANONICAL** — `docs/r3-artifacts/01-state-matrix.md` (Person card · Face card · Dialog / confirmation among 17; §3 abbreviated seed superseded)
2. ~~**State triple** — ingest × analysis × identity channels.~~ **DONE / CANONICAL** — `docs/r3-artifacts/02-state-triple.md` (+ grid `docs/r3-artifacts/04-state-triple-grid.html`)
3. ~~**Collision ledger** — distinguishable pairs + rules.~~ **DONE / CANONICAL** — `docs/r3-artifacts/03-collision-ledger.md` (+ frames `docs/r3-artifacts/03-collision-frames.html`)
4. ~~**Toolkit bake-off** against §6.~~ **CLOSED / DONE** (owner) — criteria at `docs/r3-artifacts/05-bake-off-checklist.md`; optional regression only.  
5. **Related (kept):** identity × processing cross-product — `docs/r3-artifacts/02-interaction-cross-product.md` (not deleted; not Artifact 2)
6. ~~**Clickable hierarchy frames** — test, not spec.~~ **DONE (TEST)** — `docs/r3-artifacts/06-hierarchy-frames.html` (Library / Workspace / Inspector IA from §4; not a product shell)
7. ~~**Shell decision packet.**~~ **CLOSED / DONE** — `docs/r3-artifacts/07-shell-decision.md` — native production shell authorized.

Index: `docs/r3-artifacts/README.md`. Human ship gates CLOSED / DONE: `docs/SEM-ARCH-V1.4.md` §I.5 · `docs/GATES.md`.

---

## 9) Explicit refusals

| Proposal | Verdict |
|---|---|
| Rename Possible → Candidate (noun) | **Refuse** — keep adjectival link label |
| Refuse Compare entry above 8 | **Refuse** — progressive entry |
| State matrix instead of frames | **Refuse** — matrix = spec; frames = test |
| Polish Tk Home into final shell | **Refuse** (SEM-ARCH-V1.4 §E) |
| Second product Home / revive PySide on `main` before R3 | **Refuse** |
| Schema columns from this brief alone | **Refuse** until named CONTRACTS slice |

---

## 10) Changelog

| Version | Date | Summary |
|---|---|---|
| v2.5 | 2026-09-21 | Owner closed C.3 / bake-off / §8.7 / Ruled-out ship claim (SEM-ARCH §I.5 CLOSED / DONE). Native shell authorized. |
| v2.3 | 2026-09-21 | Human bake-off / winner / live gates deferred to last per SEM-ARCH §I.5; development continues. |
| v2.2 | 2026-09-21 | §8.6 hierarchy test frames at `docs/r3-artifacts/06-hierarchy-frames.html` (TEST not SPEC). Human ship gates CLOSED via `docs/SEM-ARCH-V1.4.md` §I.5. |
| v2.1 | 2026-09-21 | §8.1–§8.4 artifacts landed under `docs/r3-artifacts/` (matrix, cross-product, 15 collision frames, 30-card state-triple grid). Human bake-off checklist at `05-bake-off-checklist.md` (no measurements). Next = toolkit bake-off runs. |
| v2 | 2026-09-21 | Owner-approved after critique. Two-axis identity; Ruled out; state matrix seed; processing grammar; adaptive overlays; evidence-ack Enter; Compare progressive entry; Group Inspector split; transactional undo; Library/observation split; toolkit bake-off criteria. |
