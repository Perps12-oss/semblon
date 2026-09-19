# SEM-ARCH — North star and planned work

**Status:** Architecture Reset V1. **This file is the source of truth** for what Semblon is and how it grows. Drawing board only — no code, no columns.  
**Date:** 2026-09-19

| File | Job |
|---|---|
| `docs/PRODUCT.md` | Frozen v1 — what the user can do now |
| `docs/CONTRACTS.md` | Schema / CLI / runtime |
| **This file** | North star + planned work |
| `docs/SEMBLON_MATURITY_BLUEPRINT.md` | Earned history + absorb + measure |
| `docs/FACE-GATES.md` | Closed FACE-002→005 validation index |

`docs/ARCHITECTURE.md` and `docs/ROADMAP-RECONCILE.md` are pointers here. Do not grow a second plan in those files, the blueprint, or slice evidence docs.

There is no `SEMBLON_IMPLEMENTATION_PLAN.md`. This file is not one.  
There is no OBS / SIM / VISION clock and no successor FACE queue. `ARCH-*` layers below **are** the planned-work sequence.

Does not replace PRODUCT v1 or CONTRACTS. Does not authorize detectors, parked §20 libraries, or schema columns.

**Architecture may anticipate the future. Implementation must earn it.**

---

## 0. How to read this

The face gates proved the identity engine and exposed the limits of a face-centric *plan*. They are closed evidence, not the shape of the next work.

```text
RESET, not rewrite
  KEEP     the identity engine, the golden, the firewall, the review loop
  ADAPT    planned work so faces are the first capability, not the centre
  DEFER    every new observer until the generic contracts exist
  REJECT   a giant model farm, a graph database, an LLM, a cloud Lens clone
           FACE-n → OBJECT-n as the way we grow
```

```text
CORE → PROVIDERS → OBSERVATIONS → CONNECTIONS → MEMORY
```

PRODUCT v1 stays the stills CLI (`docs/PRODUCT.md`).  
CONTRACTS stay the schema authority. Do not add `kind` / `space` / `payload` / track / relationship / event columns to satisfy this board.

If a later slice needs a column, that is a contract revision with a named slice and tests. Not this file.

---

## 1. The decision at the top of the board

> Semblon is not a face-recognition application.  
> Semblon is a **local visual intelligence system**.

Faces are the first mature intelligence capability. They are not the centre of the architecture.

```text
                         SEMBLON
                            │
                  LOCAL VISUAL INTELLIGENCE
                            │
       ┌────────────────────┼────────────────────┐
       │                    │                    │
     OBSERVE              CONNECT              SEARCH
       │                    │                    │
       └────────────────────┼────────────────────┘
                            │
                         REMEMBER
                            │
                    ┌───────┼───────┐
                    │               │
                 EXPLORE         REVIEW
```

The system takes one person's visual collection and turns it into something queryable and understandable.

Not only: *Who is in this photo?*

Also, eventually: *What is in this photo? Have I seen this before? Where else did this appear? What is associated with it? What happened around it? Show me everything related to this.*

v1 still only ships the face slice of that sentence. The plan must be able to hold the rest without a redesign every time a new capability is added.

---

## 2. Semblon observes. Semblon connects. Semblon does not pretend to know.

Put this in huge letters:

```text
A model can say:     "I detected this."
Semblon can say:     "These observations appear related."
A human can say:     "Yes. That is the same person / object / event."
```

That separation is the identity lesson, generalized.

| Already proven (faces) | General rule |
|---|---|
| `cluster ≠ person` | `group ≠ entity` |
| STRONG ≠ person until `name` | a tight group is not a confirmed thing until a human decision |
| Unknown is valid | refusal is a feature in every modality |
| Wrong identity > unknown | wrong entity > unknown |
| False merge > false split | unjustified merge is worse than an extra group |
| `compare()` is a primitive | similarity is not identity and not truth |
| Decision rows are evidence | confirmation is recorded, not silently trained back into the model |
| Identity firewall | no second space silently votes on identity |

Withdrawn forever: “another signal agrees, so identity confidence may rise.”  
Body similarity, clothing, objects, scene, and temporal continuity may be **shown** as evidence and **queried explicitly**. They must not silently change `compare()`, DBSCAN membership, or ACCEPT.

---

## 3. Five concepts, then five more

This is the most important architectural change. Ten primitives. None of them are tables until a contract revision earns them.

### 3.1 MEDIA

The actual thing the user owns.

```text
Photo · Video · Frame · Document/image
```

Semblon never alters the original. Files stay put. SQLite + originals are authoritative. Export folders are views.

Today: `media` (`sha256` unique, `path` first-seen, `source_type` ∈ `folder` | `video` | `live`).

### 3.2 OBSERVATION

Something a model actually detected or measured. Evidence. Not interpretation.

```text
Face · Object · Body · Text · Scene · Animal · Landmark
Clothing · Colour · Pose · Activity · Visual feature
```

Those names are a **capability map**, not an install list. A name here does not authorize a library. Same rule as blueprint §1.3.

```text
PHOTO 1234
  Observation #81   type=face     bbox=…  embedding=…
  Observation #82   type=object   class=backpack  bbox=…
  Observation #83   type=text     content=…  bbox=…
```

Today: `observations` is a **source/frame slot** (`media_id`, `frame_id`, `run_id`). It is not a typed multi-kind record. A face observation lives in `faces` (bbox, embedding, quality, `cluster_id`, `person_id`). Do not add `kind` / `space` / `payload` columns to satisfy this section.

**Rule:** a detector produces an observation. It does not produce an entity.

### 3.3 ENTITY

Semblon's attempt to represent something recurring. A hypothesis that can become human-confirmed.

```text
Face A ─┐
Face B ─┼──► PERSON HYPOTHESIS  ──► (human name) PERSON
Face C ─┘

Object observations ──► similarity / temporal / visual evidence ──► OBJECT HYPOTHESIS
```

`Hypothesis ≠ truth.`

Today: the only confirmed entity type is `persons` after `name`. `clusters` are face-observation groups, not people.

### 3.4 EVIDENCE

Every inference has a trail.

```text
Person hypothesis P17
  Evidence
    ├── face observation #81
    ├── face observation #103
    ├── face observation #151
    ├── body similarity          (shown; does not vote on identity)
    ├── temporal continuity      (shown; does not vote on identity)
    └── human confirmation       (decision row)
```

Semblon can explain *why* it thinks two things are related. That is stronger than a black-box match.

Today (partial): `decisions` (scores, margin, kind), cluster `min_intra`, export JSON evidence block, review actions. No general evidence graph. Do not invent one in DDL from this paper.

### 3.5 RELATIONSHIP

Observations are not independent bags of labels.

```text
Person
  ├── wearing     → Jacket
  ├── carrying    → Bag
  ├── standing_near → Car
  └── located_at  → Building
```

Conceptually:

```text
OBSERVATIONS → ENTITIES → RELATIONSHIPS → EVENTS / CONTEXT → VISUAL MEMORY
```

Not necessarily a graph database. That is an implementation decision for much later (parked §20 still parked).

Today: S6 `memory together` / `events` derive person × time / co-appearance from owned metadata. No relationship table. Time/place must not change identity scores.

### 3.6 The other five (same discipline)

| Primitive | Meaning | Today |
|---|---|---|
| **Embedding** | A typed vector with modality, provider/`pack_id`, dim, normalisation, version | `faces.embedding` + run `pack_id`. No envelope table. |
| **Track** | Temporal association of observations across frames | Not a table. S7a writes frame slots only. `observation ≠ tracklet ≠ person`. |
| **Hypothesis / group** | “These observations appear related under a specified model/config” | `clusters` for still faces only. Video held out of product DBSCAN. |
| **Event** | A hypothesized episode (time + place + recurring entities + media proximity) | S6 crude events from timestamps/folders. No event entity. |
| **Decision** | Human confirmation, correction, or refusal | `decisions`. Name/merge/split/ignore/note/identify. |

**Critical rule for the whole board:**

> A detector produces an **observation**.  
> A grouping produces a **hypothesis**.  
> A human **decision** can establish an identity / confirmation.

---

## 4. Intelligence engines are capabilities, not one giant AI

Do not build one mega-engine. Build a capability architecture.

```text
                    SEMBLON CORE
                         │
          ┌──────────────┼──────────────┐
          │              │              │
       DETECT         EMBED          READ
          │              │              │
     Face Object Body  Visual        Text Document
                      similarity
```

Specialist capabilities (future, unequal, not all scheduled):

| Capability | Typically produces | Notes |
|---|---|---|
| Face | observation + identity embedding + bbox + quality | **Current.** FaceKit / InsightFace only. |
| Object | observation + class + confidence + bbox + optional embedding | Future. Not authorized. |
| Body | observation + geometry / embedding | Future. Must not vote on identity. |
| Pose | geometry | Future. Parked MediaPipe until earned. |
| Text / OCR | observation + content + bbox | Future. |
| Scene | semantic class / embedding | Future. CLIP parked. |
| Landmark / animal / clothing / colour / activity | class, attribute, or embedding | Future. Names ≠ install. |

The architecture must accommodate semantic classifications, embeddings, geometry, relationships, and metadata **without** letting any of them become a silent second identity engine.

---

## 5. The universal observation pipeline

The existing pipeline is the foundation. It is not thrown away.

Current (identity slice):

```text
source → decode → detect → filter → embed → compare → cluster → review
```

Evolved (destination; implementation earns each box):

```text
SOURCE
  │
INGEST / DECODE
  │
MEDIA OBSERVATION
  │
  ├──────── ANALYZE ────────┐        METADATA
  │   Face  Object  Text    │            │
  │         Scene   …       │            │
  └────────────┬────────────┘            │
               ▼                         │
          OBSERVATIONS ◄─────────────────┘
               │
          EMBEDDINGS
               │
        SIMILARITY ENGINE
               │
        GROUPING / LINKS
               │
           HYPOTHESES
               │
         HUMAN REVIEW
               │
         CONFIRMATION
               │
          MEMORY INDEX
```

FaceKit remains the identity engine on the face branch of ANALYZE. Other branches, when earned, get their own comparison spaces (blueprint §1.4). Never one global distance.

---

## 6. Video is a temporal stream, not a JPEG storm

S7a taught this. It is now an architectural requirement, not a video-UI annoyance.

Wrong:

```text
500 frames → 500 faces → 500 review rows
```

Right:

```text
VIDEO
  ├── temporal stream
  ├── observations          (per sampled frame; evidence)
  ├── tracks
  │     ├── Track 1
  │     ├── Track 2
  │     └── Track 3
  └── identities / hypotheses
```

```text
Frame 001 → face observation
Frame 002 → face observation
Frame 003 → face observation
       ↓
   TRACK #17
       ↓
 possible Person A
```

One person on screen for 600 frames is not 600 things to review. A car, a dog, an object can be a track the same way.

Dump evidence that forced this onto the board: run `20260917T161452Z-a012c0fe` — 2 videos, 231 samples @ 1 Hz, 434 ok faces, 0 product clusters (holdout). `unassigned=434` is an **observation** count, not an identity count. Do not “fix” it by enabling stills DBSCAN on video.

Today: S7a writes `observations.frame_id` / `t_ms`. S8 Reviewability on `main` (PR #28) can seek `path`+`frame_id`+`bbox` at render time. Tracklets are still not a table and still not this paper's implementation.

`observation ≠ tracklet ≠ person` remains.

---

## 7. Search is a major subsystem — later

Google Lens is a clue, not a clone target. Semblon search is against **owned visual memory**, local-only.

```text
SEARCH
  ├── IMAGE
  ├── TEXT
  └── ENTITY
        │
   SEMBLON INDEX
  ├── similarity
  ├── semantics
  └── relationships
        │
     RESULTS
```

Eventually: drop an image (“find visually similar things”), select an object (“find this elsewhere”), select a person (“show appearances”), select text (“find images containing this”).

Today: no product search. Blueprint S8 still says search is last among the shell slices. This board **raises the destination**, not the ticket.

Do not add a vector database because this section exists. Exact compare remains until scale evidence says otherwise.

---

## 8. Intelligence Canvas is a consumer, not the architecture

The existing shell idea still fits. It becomes more powerful when the canvas can represent more than faces.

```text
Sidebar → Workspace → Intelligence Canvas → Inspector
```

Opening a photograph: overlays for whatever observations exist; Inspector lists entities and counts; click an entity → that entity's visual history; click a relationship → media where that relationship occurs.

Canvas modes (destination): Photo · Person · Object · Event · Relationship · Search result · Video track · Collection.

Today: `review-ui` is the shipping vertical. PySide6 spike is presentation-only (`docs/S8-TOOLKIT.md`). Full shell remains deferred. GUI must not own intelligence and must not import FaceKit.

---

## 9. Events are hypotheses about what happened

People care about episodes more than raw observations.

```text
EVENT "Trip to X"          EVENT "Birthday"
  ├── 4 people               ├── people
  ├── 2 vehicles             ├── cake
  ├── 1 hotel                ├── restaurant
  ├── 3 locations            ├── decorations
  ├── 187 photos             └── photographs
  └── 22 minutes of video
```

Signals (eventually): time + location + visual similarity + recurring entities + video tracks + folder context + metadata.

Again: **event hypothesis, not automatic truth.** No LLM titles as architecture. S6 first pass stays structured signals.

---

## 10. The board, reduced

```text
SEMBLON
                 │
          ┌──────┴──────┐
          │             │
        MEDIA       METADATA
          │
     ┌────┴────┐
     │         │
  IMAGES     VIDEO
     │         │
     └────┬────┘
          │
   OBSERVATION ENGINE
          │
  DETECT · EMBED · READ
          │
     OBSERVATIONS
          │
   ┌──────┴──────┐
   │             │
TEMPORAL      SIMILARITY
TRACKING        ENGINE
   │             │
   └──────┬──────┘
          │
      HYPOTHESES
          │
   ┌──────┴──────┐
   │             │
RELATIONSHIPS   GROUPS
   │             │
   └──────┬──────┘
          │
       EVENTS
          │
   VISUAL MEMORY
          │
 SEARCH · EXPLORE · REVIEW
          │
      GUI / CLI / API
```

Wall diagram (same system, user nouns):

```text
            SEMBLON
               │
     ┌─────────┴─────────┐
     │                   │
  OBSERVE             SEARCH
     │                   │
 PEOPLE  OBJECTS  WORLD  │
     │                   │
 OBSERVATIONS            │
     │                   │
 SIMILARITY + TEMPORAL   │
     │                   │
  HYPOTHESES             │
     │                   │
 ENTITIES  LINKS  EVENTS │
     │                   │
     └──► MEMORY ◄───────┘
            │
     HUMAN CONFIRMATION
            │
      VISUAL HISTORY
```

---

## 11. What this reset will not do

Do not immediately implement:

- 15 new AI models
- a giant knowledge graph or graph database
- an LLM chatbot
- Google Lens cloning
- cloud AI APIs
- a vector database
- a massive rewrite of the face pipeline
- MediaPipe, CLIP, hands, pose, objects, semantic clustering
- new schema columns
- ACC, public lookup, live, FastAPI, CustomTkinter, watchdog

That would destroy the advantage already earned.

Instead: make the architecture general first. Add intelligence capabilities one at a time. Face stays the reference implementation.

---

## 12. Planned work

`ARCH-001` … `ARCH-010` are the order Semblon grows. They are not FACE-006… and not OBJECT-001. Blueprint S0–S9 remain earned history; they are not the future ticket shape.

| Layer | Name | Job | Now? |
|---|---|---|---|
| **ARCH-001** | Core observation model | Name the primitives and the detector / group / decision rule | **Next slice** (docs only) |
| **ARCH-002** | Capability / provider boundary | `ObservationProvider` declares what it produces; shared execution | After ARCH-001. No new providers. |
| **ARCH-003** | Universal similarity | Embedding envelope; never compare incompatible spaces | After ARCH-001. Face `pack_id` remains the identity key. |
| **ARCH-004** | Grouping / hypothesis | `ObservationGroup` = related under a model/config, not “the same thing” | Vocabulary first. Do not retune `eps`. |
| **ARCH-005** | Temporal intelligence | Frame → observation → track → track-level hypothesis | After contracts. Sampled-video evidence already exists. Tracks not opened by this paper. |
| **ARCH-006** | Relationship engine | Explicit links with evidence, bounds, provider, confirmation | After a second observer exists or face-only links are earned. |
| **ARCH-007** | Event intelligence | Media + entities → event hypotheses | After relationships or a thinner time/place pass. |
| **ARCH-008** | Visual search | Image / text / entity into owned memory | After observation + similarity layers. |
| **ARCH-009** | Visual memory | Durable index = media + observations + entities + relationships + events + decisions + time | After the layers it indexes. |
| **ARCH-010** | Intelligence Canvas | GUI consumes the architecture | After there is more than faces to show, or as a thin consumer of today's store. |

```text
CORE → PROVIDERS → OBSERVATIONS → CONNECTIONS → MEMORY
```

Individual AI capabilities become interchangeable modules behind that spine.

---

## 13. What happens to the face work

We do not throw it away. We promote it.

```text
Existing FACE system
        │
        ▼
Reference implementation
        │
        ▼
Generic observation architecture
```

FaceKit / InsightFace is the first mature `ObservationProvider`.

| Face fact | Architectural reading |
|---|---|
| S1 PASS on `20260913T153515Z-1e915abe` | Detection + embed + conservative grouping work. Do not retune `eps=0.40`. |
| FACE-002 confirmatory 22 pairs, FAR 0/11 FRR 1/11 at 0.60 | Measure trustworthiness of *identity* observations. Not a 10k claim. |
| FACE-003 decisions | Human judgement is structured evidence. STRONG ≠ person. |
| FACE-004 identify vs persons | 1:N against confirmed entities, never against groups. |
| FACE-005 incremental + inbox | Media identity is `sha256`; unknowns have a place. |
| S6 memory | Time/place/co-appearance without touching identity scores. |
| S7a holdout | Frame-level face observations are not identity. |
| S8 Reviewability (PR #28) | An observation must be inspectable from `path`+`frame_id`+`bbox`. |
| Identity firewall | The first provider must not be polluted by later ones. |

Problems discovered become requirements:

- Review scale on video → tracks are first-class (ARCH-005), not “cluster the frames.”
- `observations` as a frame slot → do not pretend it is already a typed observation.
- `pack_id` as compare key → every future embedding space needs the same honesty.
- Cluster ≠ person → group ≠ entity, everywhere.

---

## 14. Revised development sequence

This changes **planned work**, not PRODUCT v1, not the golden, not CONTRACTS.

```text
PHASE A   Architecture foundation
          contracts · evidence/provenance · embedding envelope
          provider interfaces · generic grouping language
                │
PHASE B   Adapt FACE into that architecture
          existing detect / embed / cluster / name / review
          (adapter + vocabulary; not a rewrite; no eps retune)
                │
PHASE C   Performance / execution
          bounded workers · CPU/GPU providers · EP selection
          truthful run evidence
          (still blocked on PERF P1 — docs/PERF-P1-ARM64.md)
                │
PHASE D   Temporal intelligence
          sampling (S7a KEEP) · tracking · track identities
          track-level review
                │
PHASE E   Second visual capability — OBJECTS (when chosen)
                │
PHASE F   Text / OCR + semantic search
                │
PHASE G   Relationships
                │
PHASE H   Events
                │
PHASE I   Visual search / Lens-like workflows (local)
                │
PHASE J   Visual memory
                │
PHASE K   Intelligence Canvas
```

We do **not** decide today that Object is the second provider. We design so that answer can change without damaging the core.

Phase C does not jump the P1 block. Native ARM64 OpenCV is still not loadable in the P1 venv (`opencv_geometry500.dll` hang). Do not open workers / EP / batch until P1 unblocks. Do not silently swap S1's x64 `cv2`.

---

## 15. Disposition of earned work

Verb set: KEEP / ADAPT / DEFER / REJECT. This is not a FACE-ticket queue.

| Item | Verb | Note |
|---|---|---|
| PRODUCT v1 stills CLI | KEEP | Not redefined. |
| CONTRACTS V1.1-corrected | KEEP | No columns from this paper. |
| FaceKit identity path | KEEP | First ObservationProvider. |
| S1 golden / `eps=0.40` | KEEP | Do not retune. Do not re-ingest `20260913T153515Z-1e915abe`. |
| FACE-002…005 evidence | KEEP | `docs/FACE-GATES.md`. |
| S6 `memory` | KEEP | Narrow person × time slice of later visual memory. |
| `review-ui` | KEEP | Shipping human-decision surface. |
| S8 Reviewability (`path`+`frame_id`+`bbox` seek/crop) | KEEP | On `main` (PR #28). Pattern for inspectable observations. |
| S7a sampled video ingest + DBSCAN holdout | KEEP | Continue evidence. Do not expand to S7b from this paper. |
| S8 toolkit spike | KEEP | Presentation only. Does not replace `review-ui`. |
| PERF P0 | KEEP | Frozen. |
| PERF P1 native ARM64 | KEEP / BLOCKED | Do not open workers/EP. |
| Progress `on_event` | KEEP | |
| Video tracklets | DEFER | ARCH-005 / Phase D. After contracts + inspectability. |
| Webcam / RTSP | DEFER | |
| Identify / inbox UI + POSSIBLE | DEFER | |
| Full shell / search | DEFER | Canvas is ARCH-010 / Phase K. Search is ARCH-008 / Phase I. |
| Objects / OCR / body / scene / CLIP / MediaPipe | REJECT as current work | Phase E+ and only after ARCH-001…004 exist. |
| Vector DB / graph DB / LLM / cloud APIs | REJECT | |
| Video product DBSCAN to shrink `unassigned` | REJECT | |
| Parallel OBS / SIM / VISION tickets | REJECT | |
| `SEMBLON_IMPLEMENTATION_PLAN.md` | REJECT | |

---

## 16. SEM-ARCH-001 — Observation Architecture (first slice, when opened)

**Immediate objective (when the owner opens it):**

> Make Semblon capable of accepting different kinds of observations without redesigning the core every time a new vision capability is added.

**This drawing-board PR does not open that slice.** When opened, it is **docs / conceptual contracts only**.

In scope then:

1. Write the ten primitives as contracts: Media, Observation, Embedding, Evidence, Hypothesis, Track, Entity, Relationship, Event, Decision.  
2. Map each onto today's store or mark **not in store**.  
3. Freeze the rule: detector → observation; grouping → hypothesis; human → decision.  
4. Define the embedding envelope conceptually: modality, provider/`pack_id`, dimensions, normalisation, version. State that incompatible spaces never compare.  
5. Sketch `ObservationProvider` as an interface: inputs, outputs, execution declaration (CPU/GPU belongs here later, not a new runtime per model).  
6. Sketch `ObservationGroup` semantics from today's `clusters` without retuning DBSCAN.

Out of scope then (and now):

- New DDL / columns / tables  
- Refactor of `ingest` / `cluster` / `identify`  
- A second detector  
- Tracklet implementation  
- GUI / search / Canvas  
- Workers / EP  
- Any parked §20 library  

Face vocabulary is *adapted to the nouns*. The face universe is not preserved as a special parallel architecture.

---

## 17. Provider sketch (ARCH-002, not now)

```text
ObservationProvider
        │
 ┌──────┼────────┬────────┬────────┐
 ▼      ▼        ▼        ▼        ▼
Face  Object    OCR     Scene    Body
```

Each provider declares what it produces.

```text
FaceProvider        (exists, not yet wrapped)
  → face observation
  → face embedding
  → bounding box
  → quality metrics
  → pack_id

ObjectProvider      (does not exist)
  → object observation
  → class
  → confidence
  → bounding box
  → optional embedding
```

Shared execution (workers, EP, device) lives behind this boundary so the next model cannot invent its own runtime. That work is Phase C and is still gated on PERF P1.

---

## 18. Similarity sketch (ARCH-003, not now)

Today we think: face embedding → cosine.

The architecture becomes:

```text
Embedding
  ├── modality
  ├── model / provider
  ├── dimensions
  ├── normalisation
  ├── version
  └── vector
```

Legal: face↔face, object↔object, image↔image, clothing↔clothing, scene↔scene — each inside its own space.

Illegal: silently comparing incompatible embedding spaces; silently mixing spaces into identity `compare()`.

`pack_id` (family + versions + weight hashes) remains the identity compare key. `buffalo_l` remains a family name, not the key.

---

## 19. What this paper authorizes

**Authorizes**

- Treating this file as the **one source of truth** for north star and planned work.  
- Naming ARCH-001 (contracts, docs only) as the next slice — not OBJECT-001, not FACE-006.  
- Reading the sampled-video 434-face holdout as an architectural requirement for tracks.  
- Keeping all face gates, the firewall, and v1.

**Does not authorize**

- Code.  
- Schema changes.  
- Opening S7b, objects, OCR, relationships, events, search, or Canvas.  
- Retuning clustering.  
- Swapping S1 OpenCV.  
- A Cursor Cloud Agent on the owner's Windows dump-gate.

---

## 20. Changelog

| Ver | Date | Note |
|---|---|---|
| V1 | 2026-09-19 | Architecture Reset. This file is the north star and planned-work source of truth. Faces are the first ObservationProvider. No FACE-n successor queue. No code, no columns. |
