# Architecture

**Operating model — frozen 2026-09-12.** Do not reopen.

| Doc | Job |
|---|---|
| `docs/PRODUCT.md` | what the current user can actually do (v1 frozen) |
| `docs/CONTRACTS.md` | what the implementation must guarantee |
| `docs/SEMBLON_MATURITY_BLUEPRINT.md` | what Semblon can eventually become (S0–S9) |
| `docs/SEMBLON_CAPABILITY_DISCOVERY_BLUEPRINT.md` | scavenge useful behaviour (not install every donor) |
| `docs/SEMBLON_ENGINEERING_OBSERVATORY.md` | did this build get better? Not a development gate |

```
BUILD → SCAVENGE → MEASURE → KEEP/ADAPT/DEFER/REJECT → GOLDEN (if justified) → PROMOTE → NEXT STAGE
```

`review.html` is evidence. Use it to decide whether DBSCAN survives; it does not automatically kill an algorithm.

Observatory answers “did S3→S4 actually get better?”, not “may we experiment today?”

Do not remap stage names. Do not start a GUI because S8 exists on paper.

Current engineering: 0.4 name/merge/split code exists (S3). Dump-gate (FACE-001) remains on the owner's Windows machine; observatory is not a gate. Authorized queue is unchanged: dump-gate → FACE-002 → FACE-003 → FACE-004 → FACE-005.

The frozen block above is the **operating model**. The rest of this file is the **architectural North Star** (system structure). It does not reopen S0–S9, amend PRODUCT v1, or authorize implementation of future boxes.

---

# Architectural North Star

**Status:** System-structure North Star. Not a product rewrite. Not a schema. Not a ticket list.  
**Date:** 2026-09-13  
**Principle:** Architecture may anticipate the future. Implementation must earn the future.

`docs/PRODUCT.md` remains the frozen v1 product.  
`docs/CONTRACTS.md` remains schema / CLI / runtime authority.  
`docs/SEMBLON_MATURITY_BLUEPRINT.md` remains the S0–S9 capability-generation clock.  
FACE / build 0.x remain the only engineering clock.  
This file does **not** create an OBS / SIM / VISION numbering system.

Do not implement a capability because it appears below. Do not add a dependency, package, schema, CLI command, UI, or service solely to make the diagram look complete.

---

## 1. Trajectory (destination, not backlog)

```text
SEMBLON
│
├── Source adapters
│     ├── folder          ← current birth environment
│     ├── video           ← later
│     ├── live            ← later
│     └── future sources
│
├── One decode / normalization path
│
├── Observation engine
│     ├── FaceKit — identity observations          ← current
│     ├── geometry observers (landmarks, hands, pose)   ← future
│     ├── appearance / quality observers                ← future
│     ├── object / region observers                     ← future
│     └── semantic observers                            ← future
│
├── Separate representation spaces
│     ├── identity
│     ├── geometry
│     ├── appearance
│     └── semantic
│
├── Space-specific comparison / grouping
├── Explicit relationship queries   ← never silent identity fusion
├── Human review
├── Human meaning (person / gallery assignment)
├── Identification
├── Later: video / live
├── Later: public-information enrichment
└── Last: ACC as a client
```

Long-term growth is visual observation, then **separate** similarity spaces, then explicit relationships, then review and human meaning, then identification, then later sources and integrations.

Implementation still proceeds from validated value:

```text
folder → FaceKit → conservative clustering → review → persons → identification
       → hardening → only then broader observation
```

---

## 2. Current product remains narrow

v1 / current build is not the whole diagram. It is this slice:

```text
folder of still images
        ↓
decode
        ↓
FaceKit detection
        ↓
filter
        ↓
FaceKit embedding
        ↓
identity comparison (same pack_id only)
        ↓
conservative clustering
        ↓
HTML inspection / export
        ↓
human review
        ↓
named persons
        ↓
person gallery
        ↓
1:N identification
        ↓
unknown when evidence is insufficient
```

The current product does **not** require hands, pose, generic objects, scene understanding, CLIP, public web search, video, live camera, ACC, a vector database, cloud services, semantic clustering, or composite identity scoring.

Those belong to the trajectory unless a FACE ticket separately authorizes them.

---

## 3. Capability map

Status is architectural, not a sprint board. **Current roadmap** means already on the FACE / 0.x path. **Future / later / last** means not authorized to implement now.

| Capability | Space | Role | Status |
|---|---|---|---|
| Face detection | identity | locate candidate faces | **Current** |
| Face embedding | identity | identity representation | **Current** |
| Face comparison | identity | identity similarity | **Current** |
| Face clustering | identity | conservative grouping | **Current** |
| Human review | human meaning | resolve clusters | **Current roadmap** |
| Person gallery | identity / human meaning | named identities | **Current roadmap** |
| 1:N identification | identity | identify against gallery | **Current roadmap** |
| Face landmarks | geometry | facial structure | Future |
| Hands | geometry | hand / keypoint observations | Future |
| Pose | geometry | body / keypoint observations | Future |
| Colour | appearance | image / region attribute | Future |
| Sharpness / brightness | appearance / quality | evidence quality | Future |
| Objects | object / semantic | object observations | Future |
| Regions / segmentation | semantic / geometry | region observations | Future |
| Semantic image representation | semantic | visual semantic similarity | Future |
| Per-space similarity | space-specific | similarity queries | Future |
| Relationship queries | cross-space, explicit only | discover relationships | Future |
| Video | source | temporal observations | Later |
| Live | source | real-time observations | Later |
| Public information | enrichment | external context | Much later |
| ACC | integration | external client | Last |

Do not turn this table into tickets. Map work into FACE / 0.x / S0–S9 when a stage actually authorizes it.

---

## 4. Candidate technology map — not authorization

Names are **candidate providers**, not mandatory dependencies. A name here does not authorize install, schema, or CLI.

| Capability | Candidate | Architectural role |
|---|---|---|
| Identity | InsightFace / FaceKit | identity only |
| Face / hand / pose geometry | MediaPipe Tasks | future geometry observer |
| Image measurements | OpenCV / conventional CV | appearance / quality |
| Semantic representation | CLIP or successor | semantic space |
| Objects / regions | specialist models | future observers |
| Vector retrieval | vector index / DB if justified | infrastructure only |

Selection, when a stage authorizes it, must still pass accuracy, Windows x64 / ARM64 native (emulated labelled as such), licensing (code **and** model), dependency footprint, CPU / memory, offline operation, maintainability, and existing contracts.

`docs/backlog-libraries.md` remains the parked list. Do not add a library because this table mentions it.

---

## 5. FaceKit is the identity authority

FaceKit is Semblon's **identity engine responsibility**. The current provider is InsightFace `buffalo_l` (internal evaluation only; see `docs/licenses.md`).

```text
source.folder → decode → FaceKit detect → filter → FaceKit embed
             → compare() → identity clustering → review.html → export
             → human review → person gallery → identify
                    ├── top-1
                    ├── top-2
                    ├── margin
                    └── unknown
```

Do not replace this path with dlib / `face_recognition`, CLIP, MediaPipe, whole-image clustering, or a generic multimodal vector.

`compare()` remains a primitive keyed by `pack_id`. No cross-pack identity comparison, even when dimensions match.

---

## 6. MediaPipe is future observation infrastructure

MediaPipe is a **candidate for a future observation layer**, not a second identity detector and not a FaceKit replacement.

```text
Image
  ↓
FaceKit
  ↓
accepted identity observation
  │
  └──── optional future enrichment
             ↓
        MediaPipe geometry
        landmarks / hands / pose / other supported tasks
```

If MediaPipe is eventually used to enrich an accepted face:

- preserve observation provenance and the link to the FaceKit observation;
- do not replace the FaceKit identity embedding;
- do not silently modify identity clustering;
- a MediaPipe face that FaceKit rejected must not become a valid identity observation.

Do not implement MediaPipe unless an authorized FACE stage says so.

---

## 7. CLIP, vector stores, and exploratory leftovers

Correct classifications:

| Thing | Is | Is not |
|---|---|---|
| CLIP (or successor) | candidate **semantic** representation provider | landmark detector; identity engine; person clusterer |
| Vector DB (Qdrant, Milvus, FAISS, …) | optional future **retrieval infrastructure** | an observation layer; intelligence |
| dlib / `face_recognition` | historical / donor comparison | selected Semblon identity architecture |
| MediaPipe legacy solutions | obsolete material until Tasks is evaluated | production identity |
| Whole-image semantic vector | semantic space, if ever authorized | an identity embedding |
| FastAPI / SearXNG / network fallbacks | later / isolated / off by default if ever | current core |

Exploratory or generated examples that used those names are not production architecture. Classify them as experiment, misleading prototype, future candidate, obsolete, or contradiction — do not promote them by installing the dependency.

---

## 8. Separate representation spaces

Semblon must not become one giant feature-vector system.

```text
                 OBSERVATIONS
                      │
       ┌──────────────┼──────────────┐
       ↓              ↓              ↓
   identity        geometry       appearance
       │              │              │          (+ semantic)
       ↓              ↓              ↓
 identity sim     geometry sim    appearance sim
       │              │              │
       └──────────────┴──────────────┘
                      │
                 explicit query
                      │
                      ↓
                 relationships
```

Each space has its own representation, provenance, comparison semantics, thresholds, validation, and failure modes. There is no single global distance metric.

The current `observations` row in SQLite is a **source / frame slot** for the identity path (`media_id`, `frame_id`, `run_id`). It is not a typed multi-kind observation schema. Do not add `kind` / `space` / `payload` columns to satisfy this diagram. Introduce concrete observation abstractions only when an authorized stage requires them.

---

## 9. Identity firewall

Identity space is isolated.

Only explicitly authorized identity representations (FaceKit embeddings under a `pack_id`) may affect:

- identity clustering
- identity thresholds
- DBSCAN parameters
- person assignment
- gallery assignment
- 1:N identification

The following must **not** silently influence identity:

face landmarks · hands · pose · colour · sharpness · brightness · object detections · scene similarity · CLIP / semantic embeddings · arbitrary composite feature vectors

Hard rules:

1. Do not create a composite similarity score and use it as a new identity threshold.
2. Do not use geometry, appearance, object, or semantic similarity to glue together identity false splits.
3. Extra spaces may later support **explicit** relationship queries or sit beside review as human-visible context. They must not vote on identity, raise identity confidence, or override UNKNOWN.
4. A false split is preferable to an unjustified false merge.

Discovery's older "convergent evidence → confidence may rise" wording is **withdrawn for identity**. Disagreement in other spaces increases caution / UNKNOWN. It does not raise identity ACCEPT.

---

## 10. Cluster ≠ person · unknown is valid

```text
cluster  ≠  person

FaceKit observations → identity clusters → human review → person
```

A cluster is an algorithmic grouping. A person is a human-reviewed semantic assignment. Never label an automatic cluster as a person because the thumbnails look similar. STRONG is a hypothesis label on `min_intra`, not a name.

Prefer **unknown** over an unjustified identification.

```text
wrong identity  >  unknown
false merge     >  false split
```

Do not relax thresholds to make groups look cleaner.

---

## 11. Composite similarity is explicit or it does not exist

A future command might conceptually request `related --spaces geometry,appearance`.

That is **not**:

```text
identity = weighted(identity + geometry + appearance)
```

Cross-space relationships must be explicitly requested. They must never become identity clustering.

---

## 12. Sources, storage, scale

Long-term source model: thin adapters (`folder`, `video`, `live`, later) into **one** decode path and **one** observation engine. Do not grow a separate engine per source unless evidence requires it. Folder is the birth environment. Video / live stay later (PRODUCT v1 out; maturity S7).

Storage stays local-first: originals stay put; SQLite + files are authoritative; pack / run / platform / timing provenance remains. No cloud store. No network in the core. No vector database because future retrieval might like one. No unrestricted N×N identity compare as architecture. FAISS / HDBSCAN / Qdrant / Milvus stay parked until scale evidence exists (`docs/backlog-libraries.md`).

Platform: Windows x64 native and Windows ARM64 native first-class; x64-on-ARM64 is `emulated` only. Linux / macOS later. GPU optional. CPU is a valid baseline. Conservative workers until evidence.

Licence veto: code licence, model licence, redistribution, commercial use, offline restrictions. Attractive and unlicensed is rejected.

---

## 13. Current implementation queue (unchanged)

Three clocks only:

```text
PRODUCT v1     frozen stills CLI through reviewed persons + identify
BUILD 0.x      FACE tickets
MATURITY S0–S9 capability generations
```

Authorized engineering sequence:

```text
dump-gate → FACE-002 → FACE-003 → FACE-004 → FACE-005
```

Only after the current face-maturity work is genuinely closed may broader observation be considered, still without a new ticket taxonomy:

```text
observation experiments → geometry → appearance / quality → semantic
  → per-space similarity → explicit relationships
  → video / live → public information → ACC
```

Do not invent OBS-000 / SIM-000 / VISION-000.

This document does **not** authorize MediaPipe, CLIP, hands, pose, objects, semantic clustering, video, live capture, public-information enrichment, ACC integration, a vector database, or online fallback infrastructure.

---

## 14. Changelog

| Ver | Date | Note |
|---|---|---|
| — | 2026-09-12 | Operating model frozen. |
| A1 | 2026-09-13 | Architectural North Star: spaces, identity firewall, candidate tech, current vs future. No implementation. |
