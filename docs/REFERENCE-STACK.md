# Semblon reference stack

**Status:** companion authority (product/UX reference layer)  
**Date:** 2026-10-03  
**Slice:** docs-only — `grok/reference-stack`

## Authority and boundaries

Governing hierarchy (higher wins):

```text
PRODUCT.md
    ↓
SHELL-IA.md / ATMOSPHERE.md
    ↓
SEM-ARCH-V1.4.md
    ↓
GUI-TARGET-ARCHITECTURE.md
    ↓
REFERENCE-STACK.md
```

This file **cannot** override any document above it.

### Repository reconciliation (2026-10-03)

This branch is rebased onto `grok/atmosphere`, so `docs/SHELL-IA.md` / `docs/ATMOSPHERE.md` and the PRODUCT Model D Home-shell IA sentence are present. Chrome authority for this companion is Model D; this file does not reopen it.

Until atmosphere lands on `main`, `main`’s `docs/UI-EXPOSURE-MAP.md` may still describe a sidebar-shaped target IA — that is an integration lag, not permission for REFERENCE-STACK to authorize a permanent MAIN sidebar.

### It is

- a feature → external-reference map
- a UX research synthesis
- a product-pattern reference
- a source-selection guide for excavation
- a record of useful external precedent
- a frontend interaction synthesis under locked Model D

### It is not

- architecture authority
- implementation plan
- ticket queue
- maturity roadmap
- migration plan
- shell redesign
- identity-policy override
- technology-selection document

**Rule:** references provide proven interaction patterns. Semblon’s core architecture decides where those patterns live. Evidence and design guidance ≠ architecture inheritance.

```text
Smriti ─┐
Lap ────┤
digiKam ┤
Czkawka ├── proven interaction patterns
Prism ──┘
             ↓
       Semblon synthesis
             ↓
       Observations · Connections · Memory
       Identity firewall
             ↓
        Semblon UX
```

Not:

```text
Semblon = Smriti + Lap + digiKam + Czkawka + Prism
```

---

## Reference-stack roles (unequal weight)

| Role | Reference | Learn | Do not copy |
|---|---|---|---|
| Library philosophy / local-first semantic model | **Smriti** (PhotoVault) | Filesystem-as-library, optional AI, people discovery, memories, low-friction first useful state | Tauri / Rust / React / IPC / backend architecture |
| Everyday UX + scale | **Lap** | Folder-first browsing, density, culling, comparison, map-in-context, large-library responsiveness | Internal architecture |
| Mature metadata / control | **digiKam** | Inspector depth, tags, ratings, geolocation, import, correction/management, advanced search | Overall IA / configuration density |
| Computational cleanup / integrity | **Czkawka** | Exact/near-exact duplicates, similar images/videos, broken media, scan cache, CLI/job patterns | Cleanup-as-product-centre |
| Multimodal retrieval specialist | **Prism** | Text→image, OCR→media, multimodal composition, result presentation | Overall product model |
| Observation / Lens / memory synthesis + identity firewall | **Semblon** | Region observations, evidence-backed hypotheses, human identity decisions | — |

### Repositories

| Reference | Repository |
|---|---|
| Smriti / PhotoVault | [ChivukulaVirinchi/photovault](https://github.com/ChivukulaVirinchi/photovault) |
| Lap | [julyx10/lap](https://github.com/julyx10/lap) |
| digiKam | [KDE/digikam](https://github.com/KDE/digikam) |
| digiKam docs | [KDE/digikam-doc](https://github.com/KDE/digikam-doc) |
| Czkawka | [qarmin/czkawka](https://github.com/qarmin/czkawka) |
| Prism | [VardhmanSurana/Prism](https://github.com/VardhmanSurana/Prism) |
| LocalLens (demoted) | [ashesbloom/LocalLens](https://github.com/ashesbloom/LocalLens) |

**Primary implementation references while building:** Lap + Smriti + Czkawka + digiKam.  
**Specialist:** Prism (multimodal search).  
**Not equal weight:** LocalLens — historical/comparative evidence for local face workflows only; not a peer UX or architecture authority.

### Technology stacks are non-authoritative metadata

Smriti’s Tauri/Rust/React stack is **not** a reason to adopt that stack. Stacks may be evaluated independently later under Semblon’s own constraints and evidence. They are neither rejected as inherently bad nor accepted because a reference uses them. See also shell refusals in `docs/SHELL-IA.md` / `SEM-ARCH-V1.4` (Electron / Tauri / permanent Tk AppShell / CustomTkinter for product Home).

---

## Identity firewall (absolute)

Preserved from PRODUCT Level 1, CONTRACTS, FACE-GATES, and SEM-ARCH:

- false merge is worse than false split
- UNKNOWN is a valid state
- similarity is not identity
- cluster is not identity
- Track is not identity
- embedding neighbourhood is not identity
- detector output is not identity
- automatic semantic inference is not identity
- only human confirmation establishes the durable person/entity relationship
- `person_id` remains behind the identity decision boundary
- FACE-GATES remain authoritative; do not retune frozen identity thresholds here

Aligns with CONTRACTS frozen rule:

```text
detector → observation → grouping/hypothesis → human decision → entity
cluster ≠ person · group ≠ entity · Unknown is valid
```

Never:

```text
Similarity → person_id
```

Conceptual placement:

```text
                 OBSERVATIONS
                      │
          ┌───────────┴───────────┐
          │                       │
      Similarity              Context
          │                       │
          └───────────┬───────────┘
                      ↓
                HYPOTHESIS
                      ↓
                  EVIDENCE
                      ↓
             HUMAN DECISION
                      ↓
                   ENTITY
```

---

## Semantic identity hypotheses (Semblon-native discovery)

**Status:** future / product capability concept. **Not implemented by this documentation slice.** No DDL, tickets, or threshold changes authorized here.

**Definition:** a system-generated hypothesis that multiple observations may correspond to the same underlying entity, based on visual similarity and contextual evidence, **pending human confirmation**.

Normative distinction:

```text
AUTOMATIC SEMANTIC IDENTITY HYPOTHESIS
                    ≠
AUTOMATIC IDENTITY ASSIGNMENT
```

Intended flow (extends the existing spine; does not replace FaceKit for face identity compare):

```text
Observation
    ↓
Similarity / Context / Co-occurrence / Attributes
    ↓
Identity Hypothesis
    ↓
Evidence
    ↓
Human Decision
    ↓
Entity / person_id
```

The system may communicate, in effect:

> These observations appear to represent the same underlying thing.

It must not silently convert that hypothesis into an identity.

### Evidence inputs (not identity authority)

Potential evidence sources (illustrative, not a schema list):

- visual similarity
- region similarity
- temporal proximity
- spatial proximity
- repeated co-occurrence
- metadata
- surrounding observations
- object/scene context
- existing confirmed relationships

Keep these layers distinct in product language:

```text
Evidence → Hypothesis → Decision → Identity
```

**Reconciliation note:** CONTRACTS already maps Hypothesis/group → today’s face `clusters`, Decision → `decisions`, Entity → `persons` after `name`. Semantic identity hypotheses generalize that *concept* beyond face clusters (objects, regions, multimodal co-evidence). Landing store shape remains SEM-ARCH / CONTRACTS territory — not this file.

---

## Three similarity systems (mandatory separation)

Do not collapse these into one generic “similar photos” surface.

### A — Exact / near-exact similarity

**Purpose:** duplicates, near-duplicates, file/image integrity, cleanup.  
**Primary reference:** Czkawka.

```text
file → hash / perceptual signature → duplicate or near-duplicate set → compare → user action
```

### B — Semantic whole-image similarity

**Purpose:** “find images like this”; visual concept retrieval; image→image semantic relationships.  
**References:** Lap + Prism.

```text
photo → visual embedding → ANN/index → similar visual concepts → results
```

### C — Region similarity

**Purpose:** select a person/object/visual region; find related regions; Lens-style exploration.  
**Authority:** Semblon-native (region/observation architecture). Prism/Lap may inform result UX only.

```text
photo → hover/drag region → region observation → region embedding → similar regions/photos
```

**UI rule:** selection ≠ identity. Never imply “this is John” when the system only knows “this region looks similar to these regions.”

---

## People architecture (reference split)

```text
                 PEOPLE
                   │
          ┌────────┴────────┐
          │                 │
       Smriti            digiKam
          │                 │
  discovery model     correction/control
          │                 │
          └───────┬─────────┘
                  ↓
          SEMBLON IDENTITY
                  │
       human confirmation only
                  │
             person_id
```

| Concern | Reference | Study |
|---|---|---|
| Discovery | Smriti | unknown groups, person-oriented browsing, candidate discovery, person → library |
| Correction / management | digiKam | explicit correction, tagging/management, controlled metadata mutation |
| Identity semantics | Semblon | hypothesis → evidence → human review → decision → `person_id` / Entity |

```text
Face / Observation
       ↓
Candidate grouping
       ↓
Identity hypothesis
       ↓
Evidence
       ↓
Human review
       ↓
Decision
       ↓
person_id / Entity
```

The system may become more intelligent at generating **evidence and hypotheses**. It must not become more autonomous at assigning identity.

Frontend distinction (product language, not internal jargon soup):

```text
UNKNOWN GROUP → HYPOTHESIS → REVIEW → NAMED ENTITY
```

---

## Feature → reference map (by domain)

Columns: Semblon capability | Primary | Secondary | What to excavate.

### Library

| Semblon capability | Primary | Secondary | What to excavate |
|---|---|---|---|
| Local library setup | Smriti | Lap | First launch → choose folder → indexing → usable library |
| Timeline browsing | Smriti | Lap | Date hierarchy, chronological navigation, return to library |
| Folder browsing | Lap | digiKam / Smriti | Filesystem-oriented browsing, not AI-first navigation |
| Large-library browsing | Lap | Smriti / Czkawka | Grid density, progressive load, 100k+ patterns |
| Library persistence / portable library | Smriti | Lap | Library remains meaningful when drive moves |
| Offline / local-first model | Smriti | Lap | No server/cloud dependency; local processing UX |
| Filesystem authority | Smriti | Lap | DB/index vs real files; non-destructive model |
| Import / ingest | Lap | digiKam | Import flow, duplicates, folder organization, progress |
| Incremental rescanning | Smriti | Lap | New files without full rebuild |
| Watch folders | Lap | Smriti | Incremental discovery / sync semantics |
| Native desktop workflow | Lap | digiKam | Desktop interaction patterns |

### Media / metadata

| Semblon capability | Primary | Secondary | What to excavate |
|---|---|---|---|
| Photo / media inspection | Smriti | digiKam | Contextual metadata + navigation continuity |
| Metadata / EXIF extraction | digiKam | Smriti | Breadth, inspector presentation, filtering |
| Tags / labels | digiKam | Lap | Hierarchy and bulk organization |
| Ratings / flags | digiKam | Lap | Culling and filtering workflow |
| Geolocation metadata | digiKam | Smriti | GPS/EXIF presentation and location filtering |
| Media integrity / bad/corrupt media | Czkawka | Smriti | Broken files, invalid media, scan/report |
| Empty / missing / invalid FS objects | Czkawka | Lap | Library integrity tooling |
| RAW / large-media workflow | digiKam | Lap | Pairing, previews, format handling |
| Editing basics | Lap | digiKam | Crop/rotate/resize — lower Semblon priority |
| Live Photos / motion media | Lap | — | Future media-model reference |
| Technical / professional controls | digiKam | — | Depth without wholesale complexity copy |
| Bulk operations | digiKam | Lap | Multi-select, batch tag, move/copy/delete |
| Export / organization | digiKam | Lap | Controlled batch export |
| Collections / albums | Lap | digiKam | Virtual organization without destroying FS structure |
| Smart albums / saved searches | Lap | digiKam | Rule-based views over existing media |
| Backup | Smriti | digiKam | Local-first backup + metadata preservation |

### Search / retrieval

| Semblon capability | Primary | Secondary | What to excavate |
|---|---|---|---|
| Semantic text search | Prism | Smriti | Text→image retrieval, indexing, result UX |
| OCR search | Prism | digiKam | Text inside images → searchable results |
| Metadata filtering | digiKam | Lap / Smriti | Combine dates, folders, tags, ratings, etc. |
| Search-result UX | Prism | Smriti | Query → result → exploration continuity |
| Image → similar images (semantic) | Lap / Prism | Czkawka | Whole-image similarity interaction (not cleanup) |
| Region → similar regions | Semblon-native | Prism / Lap | Region observation → results; keep separate from A/B |
| Multimodal search | Prism | Lap | Text + visual query composition |
| Saved searches | Semblon-native | digiKam / Lap | Persistent views; prefer Semblon command/capability model |
| Search result → inspector → return | Smriti | Lap / digiKam | Navigation continuity |

### People / identity UX

| Semblon capability | Primary | Secondary | What to excavate |
|---|---|---|---|
| Face detection presentation | Smriti | digiKam | Pipeline and presentation (not identity assignment) |
| Face clustering / people discovery | Smriti | digiKam | Unknown → groups → human naming |
| People page | Smriti | digiKam | Person-centric navigation into the library |
| Person → photo history | Smriti | digiKam | Person as bridge into media |
| Human identity confirmation | Smriti | digiKam | Review/correction — Semblon keeps stricter firewall |
| Face correction / merge / split | digiKam | Smriti | Mature correction UX; verify current behavior before copying |
| Photo → person → other photos | Smriti | digiKam | Semantic bridge |

### Visual intelligence / Lens

| Semblon capability | Primary | Secondary | What to excavate |
|---|---|---|---|
| Visual similarity (whole-image) | Lap | Prism | Image→similar UX |
| Lens / region similarity | Semblon-native | Prism / Lap | Query region → similar; Semblon architecture authoritative |
| Photo/region → Lens → name/save/group | Semblon-native | Prism / Lap | Differentiation surface |
| Optional AI setup | Smriti | digiKam | Models as optional enrichment, not library prerequisite |
| Model management | digiKam | Smriti | On-demand acquisition, capability availability |
| Local-only / privacy UX | Smriti | Lap | Local processing without feeling like an engineering tool |

### Cleanup / culling

| Semblon capability | Primary | Secondary | What to excavate |
|---|---|---|---|
| Duplicate detection | Czkawka | Lap | Exact duplicate algorithm, grouping, reclaimable space |
| Similar-image detection (perceptual) | Czkawka | Lap | Perceptual near-dup, not semantic AI similarity |
| Similar-video detection | Czkawka | — | Extending similarity beyond stills |
| Culling / comparison | Lap | digiKam | Side-by-side decision velocity |
| Four-image comparison | Lap | digiKam Light Table | Selecting among similar candidates |
| Photo → similar → compare → keep/discard | Lap + Czkawka | — | Major Semblon workflow candidate |
| Failure / integrity reporting | Czkawka | Smriti | Damaged / missing / unreadable media |
| Fast repeated scans | Czkawka | Lap | Cache/index strategy |
| CLI automation | Czkawka | digiKam | Powerful operations remain scriptable |

### Location / memories / operations

| Semblon capability | Primary | Secondary | What to excavate |
|---|---|---|---|
| Map / geolocation browsing | Lap | digiKam | Map filtered by current library context |
| Photo → location → other photos | Lap | digiKam | Semantic bridge |
| Memories / resurfacing | Smriti | — | Conceptual model; deeper excavation still required |
| Activity / background jobs | Smriti | Lap | Queued work, completion, human-readable status |
| Cancellation / interruption | Smriti (concept) | Lap | Inspect real implementations before copying |
| Resume / recovery | Smriti (concept) | Lap | Same caveat — evidence before copy |

---

## Additional candidate product capabilities

Recorded from reference-stack review. **Candidates only** — not tickets, not SEM-ARCH slices, not authorized implementation in this branch.

### Observation-driven discovery

```text
Observation → Similar → Related observations → Hypothesis → Entity
```

### Contextual memory

Memory is not only chronological “On This Day” cards. Conceptually connect Media, Observation, Person, Object, Location, Time, Similarity, and Event into a reusable memory graph. Landing remains SEM-ARCH / S6 territory.

### Region-first exploration

User may select whole image **or** visual region and continue exploration from that selection (aligned with `docs/VISUAL-REGIONS.md` / Canvas work; product chrome still avoids “Lens” as a MAIN destination per `SHELL-IA.md`).

### Evidence-backed organization

Machine-derived groupings (beyond Folder / Album / Tag) may appear as **hypotheses** the user can accept, reject, split, merge, or leave unknown — never silent durable identity.

### Discovery loops

```text
Result → Inspector → Observation → Similar / Related → New result set → Inspector
```

Core Semblon interaction pattern for search and visual intelligence surfaces.

---

## Frontend blueprint (synthesis under Model D)

Shell chrome is governed by **`docs/SHELL-IA.md` (LOCKED Model D)**. Destinations such as Library, People, Activity, Collections, and Settings are **contextual / compact**. They are **not** a permanent MAIN sidebar, even when a reference app uses one.

Mental map of destinations (not a chrome wireframe):

```text
Library · Photos · Groups · People · Objects · Places · Collections · Activity · Settings
```

Product structure remains:

```text
Capability Stage → Memory Canvas dissolve → contextual discovery
```

### Layers

```text
PRODUCT SHELL
      ↓
WORKSPACE
      ↓
DOMAIN OBJECTS
      ↓
COMMAND LAYER
      ↓
APPLICATION CORE
      ↓
PROVIDERS / LOCAL STORAGE
```

Conceptual domain objects (product language may differ): Media, Observations, Tracks, Groups, Entities.

### Surfaces to synthesize

| Surface | Synthesis intent | Primary references |
|---|---|---|
| Library | Timeline / Folders / Collections / Search results — same media, no duplication | Smriti + Lap + digiKam |
| Media grid | Viewport virtualisation + interaction; consumes a ViewModel, not DB/detectors | Lap (+ Czkawka density lessons) |
| Canvas | Interaction surface (hover → region → observation → similar), not a passive viewer | Semblon + Prism (result UX) |
| Inspector | Media / Observations / Metadata / Similarity / Identity evidence — context shifts with selection | digiKam + Smriti |
| Search | One surface: Text / Image / Region (+ Metadata / OCR conceptually) | Prism + Smriti |
| People | Named vs Unknown groups → review → Entity | Smriti + digiKam |
| Similarity | Three kinds (A/B/C) communicated differently | Czkawka + Lap/Prism + Semblon |
| Culling | Keyboard-first decision velocity over candidate groups | Lap + Czkawka |
| Activity | Human-readable background work; library stays usable | Smriti (+ desktop job patterns) |
| Empty states | Next useful action, not “No data” | Smriti + Semblon first-run Stage |
| Settings | Capability-oriented coverage; aggressively simplified vs digiKam | digiKam (coverage only) |

### Media grid ViewModel boundary

Grid receives display state (e.g. media id, thumbnail, dimensions, timestamp, selection, observation badges). It must not own detector/filesystem/database calls. That separation matters once observations, tracks, and visual search intensify.

### Inspector as primitive

Selecting media may expose people, objects, places, similar, text, technical metadata, source. Selecting an observation shifts semantic context (e.g. “red bicycle” → found-in counts, similar observations, first seen) without dumping internal pipeline names into chrome.

### Command path (existing direction — do not reopen)

```text
User intent → Interaction → UI command → Existing registry → Application core → Domain/provider → UI state
```

Cite: `docs/GUI-TARGET-ARCHITECTURE.md`, `docs/GUI-REGISTRY-IMPLEMENTATION.md`.  
Do not invent a fourth catalogue. Do not reopen registry migration in this slice.

### Frontend capability → reference (excavation guide)

| Semblon frontend capability | Primary | Secondary | What to excavate |
|---|---|---|---|
| First-run / Stage | Smriti | Lap | Shortest path to first useful state (under Model D Stage) |
| Timeline | Smriti | — | Visual memory browsing |
| Folder browser | Lap | digiKam | Filesystem-first navigation |
| High-density grid | Lap | Czkawka | Rapid visual scanning |
| Photo Inspector | Smriti | digiKam | Contextual metadata + navigation |
| People | Smriti | digiKam | Cluster → review → identity (LocalLens demoted) |
| Semantic search | Prism | Smriti | Query → result → exploration |
| OCR search | Prism | digiKam | Text → media |
| Similarity UX | Prism / Lap | Czkawka | Keep semantic vs perceptual vs region distinct |
| Duplicate groups | Czkawka | Lap | Candidate grouping + decision |
| Culling | Lap | Czkawka | Keyboard / high-speed comparison |
| Metadata | digiKam | Smriti | Inspection / editing |
| Tags / collections | digiKam | Smriti / Lap | Persistent organization |
| Maps | Lap | digiKam | Location → media in library context |
| Memories | Smriti | — | Temporal / contextual discovery |
| Visual region interaction | Semblon | Prism | Region → observation → search |
| Background activity | Smriti | Lap | Asynchronous enrichment without engineering dashboard |
| Settings | digiKam | — | Capability coverage, not density |
| Error / recovery | digiKam / Czkawka | Smriti | Explicit failure states |
| Keyboard UX | Lap | Czkawka | High-throughput operation |
| Native desktop shell feel | Lap / Smriti | digiKam | Feel only — chrome remains Model D |

---

## Hard non-copies

| Forbidden inheritance | Why |
|---|---|
| Smriti Tauri / Rust / React / IPC / backend | Interaction lessons ≠ stack inheritance |
| Lap internal architecture | UX/performance patterns only |
| digiKam overall IA / settings density | Mine workflows, not navigation architecture |
| Czkawka as product centre | Cleanup is a subsystem, not Semblon’s identity |
| Any reference’s face clustering or semantic match → silent `person_id` | Hypothesis → human decision → Entity is mandatory |
| Permanent MAIN sidebar because a reference has one | Model D locked in `SHELL-IA.md` |
| Collapsing A/B/C similarity | Distinct purposes and UX |

---

## Acceptance questions (this document)

1. **What can Semblon learn from each reference?**  
   Smriti → semantic/local-first library · Lap → speed/browsing/culling · digiKam → metadata/control · Czkawka → computational cleanup · Prism → multimodal retrieval.

2. **What does Semblon add that is specifically its own?**  
   Observations · Connections · Memory · Lens/region interaction · Evidence-backed hypotheses · Semantic identity hypotheses · Human identity decisions.

3. **How does the frontend synthesize those patterns?**  
   Shell → Workspace → Domain object → Inspector → Command → Application core → Result → Discovery loop — under Model D chrome.

4. **What must Semblon not copy?**  
   Reference architecture · reference shell · reference identity semantics · reference product centre.

Future implementation may excavate from this map. This file is not the implementation work.
