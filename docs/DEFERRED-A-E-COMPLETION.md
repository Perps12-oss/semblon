# Deferred A–E capability completion matrix

**Programme:** Semblon — A–E Deferred Capability Completion  
**Evidence date:** 2026-10-16 (programme implementation pass)  
**Branch:** `grok/yunet-sface-discovery-plan`  
**Authority:** `docs/PRODUCT.md` · `docs/BUILD-STATUS.md` · `docs/COMPLETION-MATRIX.md` · `docs/decisions/2026-10-16-yunet-sface-discovery-plan.md` · `docs/licenses.md` · `docs/IDENTITY-PACK.md` · `docs/OBJECT-PACK.md`

**Vocabulary:** LANDED · WIRED · PARTIAL · DEFERRED · BLOCKED · VERIFIED COMPLETE  
Do not treat UI presence, stubs, docs, or mock-only tests as VERIFIED COMPLETE.

---

## Phase 2 — Core discovery

| Item | Status | Location / evidence | Missing / blocker |
|---|---|---|---|
| Field + Focus workflows | **VERIFIED COMPLETE** (Gate A + journey tests) | `native_shell/`; `test_gate_a_*`, journey tests | Visible desktop residual optional |
| Region → Similar (natural) | **VERIFIED COMPLETE** | Drag release → `findSimilar` → strip | — |
| Whole / region vs real archive | **VERIFIED COMPLETE** (honesty/Unicode) | Gate A journey; `test_region_similar_*` | Not a semantic quality claim |
| Results navigation / follow-up | **PARTIAL** | Strip → `openFocusInContext`; basis labels (D); text/object Field | Combined face+near-dup ranking deferred |
| Time / neighbouring memories | **VERIFIED COMPLETE** | `openFocusInContext` day scope | — |
| Results → real media; optional models | **VERIFIED COMPLETE** | media_id strip; UNAVAILABLE paths | — |
| Combined face + near-duplicate “same photo” | **DEFERRED** | Near-dup tooling exists; no combined UI claim | Needs eval semantics |

## Phase 3 — People / identity

| Item | Status | Location / evidence | Missing / blocker |
|---|---|---|---|
| SFace Q calibration on Semblon corpus | **BLOCKED** | `identity_config.py` provisional | Owner corpus + eval harness evidence |
| Detect / align / embed / metric / thresholds | **PARTIAL** | Runtime wired; Q OPEN | Calibration evidence |
| Overlooked-faces / inbox navigable | **WIRED** | `openUnresolvedInbox`; unresolved line clickable | Desktop journey with real inbox residual |
| Tracks on People desk | **WIRED** | `_refresh_people` includes tracks; “Track (not a person)” | — |
| Person-only Field filter | **WIRED** | `showSelectedPersonOnly` / `clearPersonFieldFilter` | Day scope stays archive-wide until filter on |
| Focus→People beyond Review this group | **WIRED** | Prefers named person when face already named | — |
| No second dashboard / albums | **VERIFIED COMPLETE** (constraint held) | — | Albums DEFERRED by product |
| No auto-name / firewall | **VERIFIED COMPLETE** | review.py name paths only; tests | — |
| AuraFace / second engine | **DEFERRED** | Eval order ADR | Needs approval + evidence |
| Preserve people/decisions/embeddings | **VERIFIED COMPLETE** | No destructive migration | — |

## Phase 4 — Search doors

| Item | Status | Location / evidence | Missing / blocker |
|---|---|---|---|
| OCR `search_text` → Field | **WIRED** | media_ids + bridge `_apply_discovery_search`; `test_discovery_slice_e` | Desktop OCR binary optional |
| OCR basis label | **WIRED** | “Text in photos — not a person” | — |
| Tesseract BYO | **LANDED** | probe on PATH | MSI bundle not approved |
| NanoDet observe + search_object | **WIRED** (BYO) | `object_pack` / `object_nanodet` / observers / CLI / shell | Real ONNX on machine for end-to-end detect |
| NanoDet redistribute / MSI bundle | **BLOCKED** | L OPEN; SHA unrecorded | Exact bytes L PASS + allowlist |
| Contours ≠ detector | **VERIFIED COMPLETE** | provider split; search ignores region | — |
| No CLIP/SigLIP/SAM2 archive engines | **VERIFIED COMPLETE** (constraint) | — | — |
| Thin result labels (D) | **VERIFIED COMPLETE** | similarBasisLabel ready-visible | Score UI deferred |

## Phase 5 — Licensing / MSI

| Item | Status | Evidence | Blocker |
|---|---|---|---|
| Weight inventory | **WIRED** | `docs/licenses.md`, IDENTITY-PACK, OBJECT-PACK | Owner SHA for NanoDet |
| MSI fail-closed on `.onnx` | **VERIFIED COMPLETE** | `tools/msi/assert-no-weights.py` (+ NanoDet names) | — |
| Bundle cleared weights | **BLOCKED** | L OPEN identity + observe | Legal sign-off + pins |
| BYO paths (no silent download) | **LANDED** | IDENTITY-PACK + OBJECT-PACK | — |
| buffalo_l out of production runtime | **VERIFIED COMPLETE** | deps/engine cutover | Historical BYO only |
| Installer inclusion tests | **PARTIAL** | assert-no-weights | Owner WiX build not run here |

## Phase 6 — Release / ops

| Item | Status | Blocker / owner |
|---|---|---|
| GHA matrix green | **BLOCKED** | Billing / remote evidence (infra) |
| Owner pack evidence | **BLOCKED** | No pack on this machine |
| SFace Q gate | **BLOCKED** | Corpus + eval |
| Native ARM64 OpenCV load | **BLOCKED** | `opencv_geometry500.dll` hang (historical) |
| Authenticode | **BLOCKED** | No cert secrets |
| MSI build/inspect | **BLOCKED** | WiX not executed here |

---

## Programme dual verdict (this pass)

| Verdict | Value |
|---|---|
| Product discovery A–E (implementable) | **WIRED / PARTIAL** — code + unit evidence; not all VERIFIED on real models/desktop |
| Slice E | **WIRED** (BYO / L OPEN) |
| Release readiness | **NOT READY** |

External blockers remain owner-owned: Q corpus, L PASS hashes, GHA billing, ARM64 load, Authenticode, MSI WiX inspect.
