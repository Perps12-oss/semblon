# SEMBLON — Capability Discovery & Product-Value Blueprint V1

**Status:** Companion to Maturity Blueprint V1. Operating discipline.  
**Date:** 2026-09-12  
**Does not replace:** `docs/SEMBLON_MATURITY_BLUEPRINT.md`, `docs/PRODUCT.md`, `docs/CONTRACTS.md`, FACE stage gates.

This file answers: **how does Semblon continuously discover, evaluate and absorb better capabilities while protecting accuracy, speed, privacy and simplicity?**

The maturity blueprint answers: **what is Semblon, and how does it mature?**

Together they are the project's operating system. They are two documents on purpose.

---

## 0. Decision: companion, not merge

Incorporating this into the North Star would mix **destination** with **process**, reopen Maturity V1, and make S0–S9 unreadable.

| File | Question | Role |
|---|---|---|
| Maturity Blueprint V1 | Where are we going? | North Star |
| **This file** | What could make *this stage* better, and may we absorb it? | Discovery OS |
| PRODUCT.md | What does v1 ship? | Frozen product |
| CONTRACTS.md | Schema / CLI / runtime | Frozen until contract revision |
| FACE / 0.x | What to code next | Staging |

**Do not remap maturity stage numbers.** A draft of this material used S4 = “visual intelligence”, S5 = “video”, S6 = “search”. Those labels are **wrong**. Canonical names stay in the maturity blueprint:

| Canonical | Name | Discovery focus (this file) |
|---|---|---|
| S0 | Born | Runtime / inference |
| S1 | Aware | Folder, cluster, review |
| S2 | Disciplined | Models, thresholds, eval |
| S3 | Learning | Review workflows, decisions as evidence |
| S4 | Recognising | Gallery, identify, unknown, exemplars |
| S5 | Useful | Incremental, quality, duplicates, inbox |
| S6 | Remembering | Time, place, together, extra evidence *channels* |
| S7 | Temporal vision | Video / track / live / RTSP |
| S8 | Conversing | Search, evidence UI, later multimodal query |
| S9 | Mature | Fusion, extensions, clients |

Clothing / body / scene / OCR do **not** become S4. They are candidate **evidence channels** from S6+, behind the accuracy firewall. They must not silently vote on identity.

---

## 1. Purpose

Semblon should not grow by accumulating features.

It should grow like a capable system:

```
observe → investigate → test → learn → integrate → measure → mature
```

At every maturity stage, examine (without copying):

- existing mature applications
- competing algorithms and new models
- alternative workflows
- performance techniques
- user-interaction patterns and failure modes
- privacy / security approaches
- video and temporal approaches
- multimodal / visual analysis
- storage and indexing

**Objective:** find what already works, understand why, test whether it improves *this* Semblon, absorb only what survives evidence.

Not: copy Facet / Immich / CompreFace.

---

## 2. Combined operating system

```
             MATURITY BLUEPRINT V1
             "Where are we going?"
                       │
                       ↓
                CURRENT STAGE
                       │
          ┌────────────┴────────────┐
          ↓                         ↓
     BUILD CURRENT              SCAVENGE
          │                    products, models,
          │                    techniques, UX
          │                         ↓
          │                      TEST
          └────────────→      EVALUATE
                                  ↓
                    KEEP / ADAPT / EXPERIMENT /
                         DEFER / REJECT
                                  ↓
                           GATE (stage exit)
                                  ↓
                            NEXT STAGE
```

This prevents both:

- building the original plan blindly, and
- chasing every interesting discovery.

The original plan is the North Star, **not a prison**. Semblon is allowed to change its mind when evidence says so. Changing its mind is not an excuse to skip the dump-gate or reopen `cluster = person`.

---

## 3. Product-value framework

Every meaningful capability must contribute to one or more of:

| Value | Question |
|---|---|
| Accuracy / Trust | Does Semblon make fewer wrong conclusions? |
| Speed / Time | Does it get *useful* results faster? |
| Cognitive relief | Does it reduce manual work or uncertainty? |
| Capability | Does it allow something previously difficult or impossible? |
| Efficiency | Does it reduce CPU, RAM, storage, network, or cost? |
| Privacy / Control | Does the user retain control of sensitive visual data? |
| Connection / Discovery | Does it help discover relationships, memories, or patterns? |

**Priority rule.** Accuracy and trust are non-negotiable foundations.

- Speed that materially degrades identity accuracy is a **regression**.
- Accuracy that multiplies complexity or resource use must **prove the gain is worth the cost**.
- “It’s cool” is not a value.

### Five questions (must all be asked; at least one of 1–4 yes, and 5 yes)

1. Does it improve accuracy / trust?  
2. Does it save the user time?  
3. Does it reduce cognitive effort?  
4. Does it create a genuinely useful new capability?  
5. Is the benefit worth the complexity / resource / privacy cost?

---

## 4. The scavenging loop (every stage)

Not “research everything before development.”

```
STAGE
 │
 ├── Current implementation
 ├── Stage-specific scavenging
 ├── Benchmark (three levels)
 ├── Build what the stage already committed
 ├── Measure
 ├── Gate (maturity exit)
 └── Update next-stage candidates (this file + maturity §16 verbs)
```

Scavenging **scope** changes with the stage. S1 does not scavenge clothing transformers. S7 does not reopen pack_id.

---

## 5. Classify everything found

Nothing enters Semblon from a screenshot. Every discovery gets one class:

| Class | Meaning |
|---|---|
| Engine | Potential technical component |
| Workflow donor | Behaviour worth reproducing |
| Algorithm candidate | Alternative to benchmark |
| UX pattern | Interaction worth investigating |
| Performance technique | Speed / RAM / storage |
| Capability candidate | Possible later feature |
| Comparator | External baseline |
| Research lead | Interesting, immature |
| Noise | Interesting, irrelevant |

“Interesting” ≠ “build.”

---

## 6. Evidence card (required before roadmap)

```
Capability:
Source:
Version / date:
What it does:
Why users might care:
Problem it solves:
Current Semblon equivalent:
Potential accuracy impact:
Potential speed impact:
Potential RAM / storage impact:
Privacy implications:
Dependencies:
Platform implications (Windows x64 / ARM64 native vs emulated):
Evidence available:
How Semblon would test it:
Canonical stage (S0–S9, maturity names):
Classification (engine / workflow / …):
Decision: KEEP | ADAPT | EXPERIMENT | DEFER | REJECT
```

| Decision | Meaning |
|---|---|
| **KEEP** | Evidence supports adoption — *eligible* for the named stage, not “build today” |
| **ADAPT** | Idea is valuable; Semblon implements it in its own architecture |
| **EXPERIMENT** | Prototype allowed; not production architecture |
| **DEFER** | Wrong stage (or wrong evidence) |
| **REJECT** | Evidence or philosophy argues against it |

KEEP is not a ticket. It is eligibility.

---

## 7. Donors are not specifications

If Facet does something useful: investigate the **behaviour**.  
Do not say: “Semblon must work like Facet.”

If Immich handles people well: study **why**.  
Do not import Immich’s schema or “cluster is a person.”

If CompreFace has useful verification semantics: test the **concept**.  
Do not inherit its thresholds.

If PhotoPrism refuses to mix SFace 128 with FaceNet 512: that is a **pack_id lesson**, not a model to vendor.

**Semblon invariants always win** (maturity §3). Especially: `cluster ≠ person`, unknown is valid, evidence before confidence, local-only default, `compare()` keys off `pack_id`.

`docs/REFERENCES.md` already says donors are not ground truth. This file is the process that makes that stick.

---

## 8. Benchmarking — three levels

### Level 1 — Observation

Run or read the external product. Record merges, splits, unknowns, review feel, speed, RAM, useful behaviours, obvious failures. **No conclusions yet.**

### Level 2 — Reproduction

Implement the *behaviour*, not the product, inside Semblon’s architecture.

Example: donor shows ambiguous groups first → Semblon already sorts REVIEW REQUIRED by worst `min_intra`. Measure whether a different priority would help **on the dump**, not on their UI.

### Level 3 — Adversarial comparison

Does Semblon’s version outperform, or at least justify itself, against the donor **on Semblon’s values** (accuracy, unknown, privacy, simplicity)?

If not: kill or ADAPT. This prevents competitor worship.

Do not treat donor clusters as labels.

---

## 9. Accuracy firewall

```
                 NEW ENGINE
                     │
                     ↓
              Independent test
                     │
              ┌──────┴──────┐
              ↓             ↓
          Evidence       Failure
              │             │
              ↓             ↓
        May inform       Must not
        a decision       override
              │
              ↓
         Evidence fusion
              │
              ↓
        confidence / UNKNOWN
```

No new model silently makes identity decisions because it looks impressive.

**Convergent evidence, not unanimous vote.**

```
Face: A · appearance: A · track: consistent  →  confidence may rise
Face: A · appearance: B · context: unknown   →  uncertainty must rise
```

Disagreement increases UNKNOWN. It does not trigger majority-vote identity.

---

## 10. Performance firewall

Every capability reports at least:

- accuracy impact (or “not an identity claim”)
- latency
- peak RSS

and where relevant: storage, network, startup.

Objective is **not** maximum benchmark FPS.  
It is **maximum useful capability per unit of resource without violating the accuracy floor.**

Native vs emulated stays honest. x64-on-ARM64 is never “native.”

---

## 11. Feature lifecycle

```
DISCOVER → CLASSIFY → OBSERVE → BENCHMARK → HYPOTHESIS
  → PROTOTYPE → ADVERSARIAL TEST → VALUE TEST → PERFORMANCE TEST
  → DECISION
       KEEP | ADAPT | EXPERIMENT | DEFER | REJECT
```

KEEP still means: eligible for the **named canonical stage**.

A capability may later be: added, removed, replaced, promoted, demoted, split, superseded, or made unnecessary — **if evidence supports it** (maturity §16 verbs).

---

## 12. Stage-specific scavenging (canonical S0–S9)

Scavenge **inside** the current stage. Do not pull S8 search into S1.

### S0 — Born · runtime

**Look for:** InsightFace / ORT configs, native ARM64, load time, CPU/GPU/NPU, RSS, pack hashing.

**Question:** can the foundation run honestly on the target machines?

**Primary comparators:** InsightFace docs, ORT execution providers.  
**Out of scope:** clustering UX, clothing models.

### S1 — Aware · folder intelligence *(current)*

**Look for:** ingest, hash/dedup, contact sheets, clustering, face quality, review priority, resume, export.

**Primary workflow donors:** Facet, FaceSorter.  
**Supporting:** Immich / LibrePhotos / PhotoPrism *as comparators*, not schemas.

**Already in Semblon (measure before replacing):** sha256 skip, det_score / min-side filters, DBSCAN `1−dot`, worst-pair, REVIEW REQUIRED first.

**Dump-gate still wins.** Scavenging does not skip opening `review.html` on a real folder.

### S2 — Disciplined · recognition quality

**Look for:** detectors, embedders, alignment, threshold calibration, hard negatives, quality, pose, age, lookalikes, uncertainty, NIST-style FMR/FNMR thinking.

**Objective:** trustworthy before clever.  
**Reject:** printing precision off confirmatory sets; mixing packs.

### S3 — Learning · person-shaping review *(not galleries yet)*

**Look for:** merge / split / reject UX, correction history, ambiguous queues, undo, “did this merge reveal a clustering failure?”

**Donors:** FaceSorter review strip, Facet merge suggestions, PhotoPrism “report bad match.”  
**Retain:** cluster ≠ person. STRONG is not a name.

**Person galleries themselves are S4.** Do not smuggle them into 0.4 as identity.

### S4 — Recognising · gallery and identify

**Look for:** trusted exemplars, top-1/top-2/margin, unknown inbox *as identify output*, verification vs identification (CompreFace distinction), person merge/split/retire, incremental identify of *new stills*.

**Donors:** Immich people actions (name, merge, feature photo) as *workflow*, not as “clusters are people.” CompreFace 1:1 vs 1:N.

**Firewall:** extra attributes (clothes, body) may be *recorded* but must not drive ACCEPT.

### S5 — Useful · unattended stills

**Look for:** cached / incremental scans (FaceSorter), watchers, resume, burst/near-dup, exemplar quality, resource scheduling.

**Watcher:** DEFER here relative to v1 (PRODUCT rejects it). Eligible to re-open at S5 only.

### S6 — Remembering · memory and extra evidence channels

**Look for:** timeline, GPS, co-appearance, event grouping from time/folder/burst — first as **discoveries, not identity claims**.

**Candidate engines (independent test, then maybe inform — never override face identity):**

- clothing / colour / accessories
- body appearance
- pose
- objects / scenes
- image similarity

```
              OBSERVATION
                   │
       ┌───────────┼───────────┐
       ↓           ↓           ↓
     FACE        BODY        SCENE
   identity    appearance    context
       └───────────┼───────────┘
                   ↓
             EVIDENCE MODEL
                   ↓
          USER-RELEVANT CONCLUSION
          (or UNKNOWN)
```

Proven independently before influencing a decision. Disagreement → more UNKNOWN.

### S7 — Temporal vision

**Look for:** tracking, track quality, shot detection, frame selection, re-id, selective embedding, temporal voting, identity persistence, unknown tracks, presence intervals.

**Rule:** same observation / identity engine. Not a second recogniser.  
**Sub-scavenge:** S7a files · S7b tracklets · S7c webcam · S7d RTSP — different constraints (seek vs latency).

### S8 — Conversing · search and interrogation

**Look for:** person/time/together queries, evidence surfaces, interactive review.

**Later multimodal (only once evidence is reliable):** OCR, captions, speech, scene text, semantic retrieval, NL query sugar over *owned* structured memory.

Example: “John, outdoor, dark jacket” = person + clothing channel + scene + time — **after** those channels pass the firewall.

Generic photo chatbot: REJECT as core.

### S9 — Mature · fusion and clients

**Look for:** isolated extensions, ACC as client, licensed packs, optional encryption, explicit external lookup.

**More engines ≠ more certainty.** Fusion remains conservative.

```
 FACE · BODY · OBJECT · VIDEO · SCENE · OCR
                  ↓
           OBSERVATION MODEL
                  ↓
           EVIDENCE / CONTEXT
                  ↓
          CONFIDENCE + UNKNOWN
                  ↓
            USER / CLIENT
```

---

## 13. What this does *not* do

- Does not modify FACE-000 / 0.2 / 0.3 contracts.  
- Does not move 0.4 earlier.  
- Does not promote clothing or CLIP into S1–S4.  
- Does not create a research backlog that blocks the dump.  
- Does not authorise FAISS, FastAPI, or dashboards because a donor has them.

**Current stage (S1) scavenging, if any:** Facet / FaceSorter / PhotoPrism *review and clustering behaviour*, measured against our `review.html`. That is observation (level 1). Implementation wait until the dump says DBSCAN is wrong.

---

## 14. Relationship to maturity §16

Maturity §16 verbs (KEEP / MERGE / PROMOTE / DEFER / REPLACE / REMOVE / REJECT) are **what happens to the North Star**.

This file’s KEEP / ADAPT / EXPERIMENT / DEFER / REJECT are **what happens to a scavenged candidate**.

A candidate KEEP here may become a maturity ADD/PROMOTE at the **named stage**, never a silent insert into the current ticket.

---

## 15. Changelog

| Ver | Date | Note |
|---|---|---|
| V1 | 2026-09-12 | Companion OS. Canonical S0–S9 mapping. Convergent evidence. Firewalls. |

---

*Find what works. Test it. Absorb only survivors. The baby may change its mind; it may not skip growing up.*
