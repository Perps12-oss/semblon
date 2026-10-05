# Semblon shell information architecture — LOCKED

**Superseded 2026-10-05 as the production shell IA** by the completed PySide6 migration (`docs/ARCHITECTURE.md`).

This document still locks Model D for the **legacy Tk Home client only**. It is not the production shell. New production UI work is Field + Focus on `semblon shell`, not another Model D implementation and not a permanent MAIN sidebar.

**Status:** LOCKED (2026-10-02) for Tk Home  
**Model:** **D — Memory-first Stage dissolve**  
**Scope:** legacy Tk client. Not the production architecture.

Authority companions: `docs/PRODUCT.md`, `docs/ATMOSPHERE.md`, `docs/UI-EXPOSURE-MAP.md`, `docs/CONTRACTS.md`. Production shell: `docs/ARCHITECTURE.md`.

Do **not** reopen sidebar-vs-stage unless implementation evidence shows a concrete technical or usability failure of Model D. Do **not** ship a persistent MAIN sidebar as a temporary scaffold.

**Implementation status (2026-10-02):** Tk Home on `grok/atmosphere` implements Stage + compact header chrome + Memory Canvas dissolve. Internal registry `nav` contributions remain for palette/shortcuts only — they must not be re-mounted as a MAIN sidebar.

---

## Product model

```text
Capability introduction  →  Memory Canvas  →  contextual discovery
       (Home Stage)            (media)         (modes over media)
```

Semblon is a local visual memory / visual discovery environment. Faces are a mature capability, not the product centre.

---

## Locked principles

### 1. First-run / empty state = capability Stage

The central Stage explains what Semblon can do:

- Explore visual memory
- Discover things inside media
- Organise people when useful
- Add a local folder as the **enabling** action (not the product definition)

Composition may be asymmetric (Explore dominant). Do not require a 2×2 grid. Activity is not a major Stage card.

### 2. Once media exists, the Stage dissolves

Memory Canvas becomes the primary experience. Media gets maximum visual space.

Do **not** leave a permanent capability dashboard underneath or beside the media.

Critical UX: Stage is **not** merely replaced by a Library route. It **dissolves into** Memory Canvas so the product feels:

> Semblon has introduced itself; now your visual memory is the application.

### 3. No permanent MAIN sidebar

Do **not** build Library / People / Activity as a persistent left-hand destination list.

Navigation is contextual and compact.

### 4. Discover is a capability, not a permanent “Lens” destination

Intended interaction:

```text
media → hover/region → select → contextual action → discovery/result
```

Do not expose implementation terminology such as **Lens** as a major product destination. Backend honesty may still say Lens internally; product chrome does not.

### 5. People remains secondary

People must remain discoverable. It must not visually imply Semblon is primarily a face-recognition application.

Copy direction: organise / name when useful. Unknown remains valid. Review badge / contextual entry — not peer weight with Explore.

### 6. Activity is operational context

Accessible and visible when relevant (pulse, sheet, busy cue). Does not compete with visual memory as a major Stage card or MAIN destination.

### 7. Settings remains a header utility

Settings is a first-class in-shell route when opened. It is not part of the core capability hierarchy (Explore / Discover / People).

---

## Capability hierarchy (rank is product signal)

| Rank | Surface | Role | Chrome weight |
|---|---|---|---|
| 1 | Explore / Memory | The visual memory itself | Default after library exists |
| 2 | Discover | Find across memory (region, similar, text, ask) | Compact control + contextual verbs |
| 3 | People | Organise when useful | Secondary mode + review badge |
| 4 | Activity | Imports / processing / soft history | Operational pulse / sheet |
| — | Settings | Prefs / library / advanced / diagnostics | Header utility |
| — | Add folder | Enabling action | Stage CTA; quiet add later |

---

## Shell / chrome rules (implementation contract)

These rules govern future Home chrome work. They do not change JobEngine, identity, persistence, or capability contracts.

### Permanent chrome (allowed)

- Brand mark (returns to Stage when the user wants the intent map)
- Search field (search memory — people + text fallthrough; not a separate Search app)
- Compact mode controls: Discover, People (with optional review count), Activity pulse when relevant
- Settings control (header)
- Footer status (Ready / busy / library counts — **not** face counts as scoreboard)
- Job controls when a job is active (Pause / Resume / Cancel) — job chrome, not MAIN nav

### Forbidden as permanent MAIN navigation

- Left-hand destination list: Library / People / Activity (or Photos / Videos / Lens / Unknown as peer rows)
- Always-visible capability dashboard beside or under Memory Canvas after media exists
- “Lens” as a top-level product destination label
- Equal visual weight for People vs Explore on Stage or in chrome

### Surfaces by library state

| State | Primary surface | Notes |
|---|---|---|
| Empty / first-run | Home Stage | Capability illumination; Add folder CTA; no empty destination sidebar |
| Media exists | Memory Canvas | Stage dissolved; media full-bleed; filters in-canvas (All / Photos / Videos) |
| User wants intent map | Stage (via brand) | Reachable; not the daily default once media exists |
| Selection / region | Contextual discovery | Inspector / results as focused response — media remains owned |
| Settings open | Settings route in-shell | Utility; leave Memory underneath when possible |

### Route compatibility

Internal route ids (`library`, `people`, `activity`, `lens`, `unknown`, `settings`, …) may remain for registry / keyboard / tests. Product chrome and copy must follow this IA. A route existing in code does **not** authorize a MAIN sidebar row.

### Secondary (unchanged class)

Review UI, Explore/Canvas overflow, Live/Watch remain **SECONDARY** / KEEP as today — not MAIN Stage peers. See `docs/UI-EXPOSURE-MAP.md`.

---

## Atmosphere & Motion — governing structure

`docs/ATMOSPHERE.md` is bound to this IA:

| Phase | Atmosphere purpose |
|---|---|
| **Stage** | Expressive capability illumination and interaction |
| **Transition** | Atmosphere dissolves with the Stage into Memory |
| **Memory Canvas** | Media dominates; chrome becomes submerged |
| **Hover** | Local illumination |
| **Selection** | Elevation / bloom |
| **Processing** | Ambient system state (busy only) |
| **Contextual discovery** | Focused visual response |

Atmosphere is product structure, not decoration. Hierarchy remains:

```text
PHOTO / MEDIA → SELECTED REGION → CONTEXTUAL ACTION → APPLICATION CHROME → AMBIENT
```

---

## Explicit non-goals (this lock)

- No second GUI / Electron / Tauri / CustomTkinter product Home
- No identity, JobEngine, persistence, or visual-search architecture changes
- No retune of clustering / FaceKit thresholds
- No persistent MAIN sidebar “until we polish Stage”

---

## Reopen criteria

Reopen only with written evidence of one of:

1. Concrete usability failure of Model D on Windows Home (owner dump-gate or scripted UX probe), or
2. Concrete technical blocker in Tk that makes Stage dissolve / compact chrome unworkable without a second GUI.

Preference or implementation convenience is not reopen criteria.

---

## Related companion

`docs/REFERENCE-STACK.md` records external feature and interaction references for excavation. It does **not** reopen or override Model D shell decisions.
