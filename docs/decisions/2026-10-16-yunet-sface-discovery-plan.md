# Plan: Unlock YuNet + SFace for archive discovery (not a People dashboard)

**Date:** 2026-10-16  
**Status:** Current — plan + **slice A authorised** (Focus face → similar photos)  
**Branch:** `grok/yunet-sface-discovery-plan`  
**Related:** `docs/IDENTITY-PACK.md`, `docs/decisions/2026-10-16-identity-stack-eval-order.md`, `docs/PRODUCT.md`, `docs/ROADMAP.md`, `docs/BUILD-STATUS.md`  

**Code:** slice A lands separately; evidence in `docs/BUILD-STATUS.md`. Slices B–E still need approval.

---

## Verdict

YuNet + SFace are building blocks for **looking into the archive from a face**, not for renaming Semblon as a face-recognition product.

| YuNet + SFace can | YuNet + SFace cannot |
|---|---|
| Find faces and landmarks | Name a person |
| Produce comparable face embeddings | Understand the whole scene |
| Support candidate groups and review | Recognise objects or landscapes |
| Seed “same person?” retrieval | Replace colour-histogram Similar |

Semblon’s advantage is **several independent lenses on one local archive**. Face recognition must stay one lens. It must not become the centre of the product or a second shell.

---

## Product north star (this plan)

**Select a face → discover related photographs → recover surrounding memory → decide what to keep.**

Do **not** build another People dashboard. Prefer Focus → results → Time/context → human decision, reusing the production PySide6 archive (`semblon shell` → `Application`).

---

## Six capabilities (ordered for Semblon)

### 1. Find the same person across the archive

**Intent:** A face in Focus becomes a route to other photos with similar face embeddings; the user confirms identity.

**Built from:** YuNet detect + SFace embed + same-`pack_id` ANN/brute search + human review.  
**Exists today (partial):** ingest embeds faces; `identify` / `search --face` vs **named persons**; clustering hypotheses.  
**Gap:** “Similar faces from this face” as a first-class Focus action with honest labels (not colour-histogram Similar; not auto-name).

### 2. Discover possible people groups

**Intent:** Surface candidate groups without declaring them people. Split / merge / reject / confirm. Preserve `cluster ≠ person`.

**Built from:** embedding similarity + DBSCAN hypotheses + `review_board` / `review.py` decisions.  
**Exists today (partial):** `cluster_run`, People desk, name/merge/split.  
**Gap:** Q-calibrated SFace operating point; clearer “hypothesis / unknown” UX; no silent auto-person.

### 3. Follow a person through time

**Intent:** From a **confirmed** person, open their photos, dates, and neighbouring stills for those days (People ↔ Time lens).

**Built from:** `faces.person_id` + media dates + `openFocusInContext` day scope.  
**Exists today (partial):** day context from Focus; People board.  
**Gap:** “This person’s days” as an explicit navigation path from a named person into Field/calendar.

### 4. Find overlooked faces

**Intent:** Queue small / group / newly detected / uncertain faces for review.

**Built from:** det_score + size_band + unassigned/low_quality faces + inbox-style review.  
**Exists today (partial):** status `ok` / `low_quality` / `rejected`; inbox.  
**Gap:** dedicated “new detections / uncertain” queue in the shell; honest limits (pose, blur, occlusion, tiny faces).

### 5. Search from a face inside any photo

**Intent:** Select a face in Focus → ranked face-embedding matches across the archive (parallel to whole-image / region Similar).

**Built from:** face-region pick + SFace query embedding + ranked stills.  
**Exists today (partial):** region Similar is **colour histogram** (`appearance/rgb8@1`) and must stay labelled as such.  
**Gap:** face-modality query path that refuses cross-pack compare and never mislabels histogram results as face matches.

### 6. Find near-duplicate portraits

**Intent:** Repeated shots of the same face; help pick the better frame. Combine face similarity with whole-image similarity and capture metadata.

**Built from:** face sim + existing near-duplicate / appearance signals + mtime.  
**Exists today (partial):** near-duplicate tooling; appearance Similar.  
**Gap:** combined ranking UI; face embeddings alone must not claim “same photograph.”

---

## Bigger opportunity: other local models (later)

Connect through **one archive**, not separate tools. Each row is its own model, licence, eval, and availability state.

| Capability | Adds | Identity firewall |
|---|---|---|
| Face embeddings | Likely same person | Authoritative for face compare only |
| OCR | Text in photos / screenshots | Must not vote on identity |
| Object detection | Photos containing an object | Must not vote on identity |
| Image embeddings | Similar scenes / places | Must not vote on identity |
| Segmentation | Precise region select | Must not vote on identity |
| Date / location metadata | When / where | Must not change identity scores |

OCR and object search are **after** the core face→archive discovery path is reliable.

---

## Architecture (unchanged shell)

```text
One local archive (paths · dates · SQLite)
        │
        ├─ Face engine: YuNet + SFace   (pack_id isolated)
        ├─ Visual search: image / region similarity (honest basis labels)
        ├─ Text / objects: optional providers (unavailable ≠ identity miss)
        └─ Context: Time + neighbouring photos
                │
                ▼
One discovery experience
  Point → find related memories → explore context → decide
```

Production chrome stays Model D / timeline Field + Focus (`docs/TIMELINE-VIEW.md`). No second application path.

---

## What to build first (implementation order)

| Step | Slice | Acceptance sketch | Depends on |
|---|---|---|---|
| **A** | Face → similar photos | From Focus face, ranked same-`pack_id` face hits; basis label says face embedding; unknown/empty honest | BYO pack; provisional threshold documented |
| **B** | Reviewable person discovery | Candidate groups; merge/split/reject/confirm; cluster ≠ person | A + Q calibration plan |
| **C** | Person → context | Named person → photos → day neighbours | B + existing day context |
| **D** | Unified results experience | Face hits, histogram Similar, region Similar share one results chrome with distinct basis labels | A + Gate A Similar |
| **E** | OCR / objects | Optional providers only after A–D | Separate L/Q/P per model |

### Threshold note (binding)

SFace Zoo demo cosine ≈ `0.363` is a **demo starting point**, not a Semblon clustering/identify threshold.  
Active provisional values live in `semblon/identity_config.py`. Historical buffalo_l S1 values stay in `semblon/identity_buffalo_frozen.py` and must not transfer.  
Any production threshold change needs Semblon corpus evidence (false merge / false split) — prefer false split.

---

## Preconditions and pushback

**Worth doing now (plan → then slice A):** Face→similar-photos on the existing shell; keep firewall and honest labels.

**Already done (do not rebuild):** YuNet+SFace runtime (`opencv/yunet_sface`); pack pin / no download; MSI fail-closed; Gate A archive/Similar/context honesty; People review loop primitives.

**Skip / defer:** New People dashboard; albums (milestone 4 deferred); AuraFace; semantic/CLIP identity; automatic naming; second identity engine; cloud.

**Pushback:**

1. Do not treat “face Similar” as a rebrand of colour-histogram Similar.  
2. Do not auto-assign `faces.person_id` from retrieval rank. Only `review.py` naming paths write persons.  
3. Do not rewrite `docs/PRODUCT.md` FaceKit wording in this plan slice — that needs a short product-truth decision now that YuNet+SFace is on `main`.  
4. Do not block archive work on Q PASS; do block **shipping** face-match claims without calibration evidence.

---

## Map to existing symbols (for implementers)

| Need | Start here |
|---|---|
| Detect + embed | `semblon/engine.py` (`FaceSession`, `embed_bgr`) |
| Pack / pin | `assert_face_pack_ready`, `docs/IDENTITY-PACK.md` |
| Cluster hypotheses | `semblon/cluster.py` + `identity_config.DEFAULT_EPS` |
| Name / merge / split | `semblon/review.py`, `semblon/review_board.py` |
| Identify vs persons | `semblon/identify.py` (persons only) |
| Whole / region Similar | `semblon/search.py`, `semblon/region_search.py` (histogram today) |
| Day context | `openFocusInContext` / Field day scope |
| Shell Focus / People | `semblon/native_shell/` QML + bridge |

---

## Status tracker impact

- This file is the **plan**. Status of delivered slices goes in `docs/BUILD-STATUS.md` when evidenced.  
- `docs/ROADMAP.md` may list discovery slices as follow-ons after milestones 1–3; it must not invent a parallel tracker.  
- Gates L / Q / P / product approval for weights remain as in the identity evaluation records.

---

## Approval gate for implementation

**Slice A — approved and implemented** (Focus face → same-pack similar photos; honest face-embedding label; no auto-name). Evidence: `docs/BUILD-STATUS.md`.

Next concrete slice (needs approval): **B — Reviewable person discovery** (candidate groups; merge/split/reject/confirm; cluster ≠ person).
