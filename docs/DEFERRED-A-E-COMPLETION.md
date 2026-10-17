# Deferred A–E capability completion matrix

**Programme:** Semblon — A–E Deferred Capability Completion  
**Evidence date:** 2026-10-16 (finish pass with owner BYO NanoDet)  
**Branch:** `grok/yunet-sface-discovery-plan`  
**Authority:** `docs/PRODUCT.md` · `docs/BUILD-STATUS.md` · `docs/COMPLETION-MATRIX.md` · `docs/decisions/2026-10-16-yunet-sface-discovery-plan.md` · `docs/licenses.md` · `docs/IDENTITY-PACK.md` · `docs/OBJECT-PACK.md`

**Vocabulary:** LANDED · WIRED · PARTIAL · DEFERRED · BLOCKED · VERIFIED COMPLETE  
Do not treat UI presence, stubs, docs, or mock-only tests as VERIFIED COMPLETE.

---

## Phase 2 — Core discovery

| Item | Status | Location / evidence | Missing / blocker |
|---|---|---|---|
| Field + Focus workflows | **VERIFIED COMPLETE** | `test_gate_a_*`, journey tests | — |
| Region → Similar (natural) | **VERIFIED COMPLETE** | Drag → `findSimilar` | — |
| Whole / region vs real archive | **VERIFIED COMPLETE** | Gate A / Unicode region tests | Not semantic quality |
| Results navigation / follow-up | **PARTIAL** | Strip + text/object Field | Combined face+near-dup deferred |
| Time / neighbouring memories | **VERIFIED COMPLETE** | `openFocusInContext` | — |
| Results → real media; optional models | **VERIFIED COMPLETE** | media_id paths; UNAVAILABLE | — |
| Combined face + near-duplicate “same photo” | **DEFERRED** | No combined UI claim | Eval semantics |

## Phase 3 — People / identity

| Item | Status | Location / evidence | Missing / blocker |
|---|---|---|---|
| SFace Q calibration | **BLOCKED** | Provisional `identity_config.py` | Owner representative corpus + false-merge/split report |
| Detect / align / embed / metric | **PARTIAL** | Runtime wired; dim 128 verified live | Thresholds not corpus-calibrated |
| Overlooked-faces / inbox | **VERIFIED COMPLETE** (offscreen) | `openUnresolvedInbox`; `test_ae_shell_programme` | Visible desktop residual optional |
| Tracks on People desk | **VERIFIED COMPLETE** (offscreen) | “Track (not a person)”; programme test | — |
| Person-only Field filter | **VERIFIED COMPLETE** (offscreen) | `showSelectedPersonOnly` / clear | Day neighbours archive-wide until filter on |
| Focus→named person | **WIRED** | Prefers named subject when face named | — |
| No auto-name / firewall | **VERIFIED COMPLETE** | review.py only; YuNet smoke persons unchanged | — |
| AuraFace / second engine | **DEFERRED** | — | Needs approval |
| Preserve people/decisions/embeddings | **VERIFIED COMPLETE** | No destructive migration | — |

## Phase 4 — Search doors

| Item | Status | Location / evidence | Missing / blocker |
|---|---|---|---|
| OCR → Field + scope | **VERIFIED COMPLETE** (unit + live store OCR SUCCESS) | `within_media_ids`; bridge Field apply; Tesseract on PATH | — |
| OCR basis label | **VERIFIED COMPLETE** | “Text in photos — not a person” | — |
| NanoDet observe + search_object | **VERIFIED COMPLETE** (BYO inference) | Pack pin+SHA; postprocess fixed for 3-level ONNX; live detect person/couch | MSI bundle still L OPEN |
| NanoDet redistribute / MSI | **BLOCKED** | SHA recorded; notices copied | Legal L PASS + allowlist |
| Contours ≠ detector | **VERIFIED COMPLETE** | Provider split; search ignores region | — |

## Phase 5 — Licensing / MSI

| Item | Status | Evidence | Blocker |
|---|---|---|---|
| Weight inventory + notices | **WIRED** | IDENTITY/OBJECT-PACK; `docs/notices/*` | Commercial redistribute still open |
| YuNet SHA | **VERIFIED** on machine | `8f2383e4…2fa4` | L PASS for MSI |
| SFace SHA | **VERIFIED** on machine | `0ba9fbfa…4e79` | L PASS for MSI; Q OPEN |
| NanoDet SHA | **VERIFIED** on machine | `4b82da99…0186` (3800954 bytes) | L PASS for MSI |
| MSI fail-closed `.onnx` | **VERIFIED COMPLETE** | `assert-no-weights` + packaging tests | — |
| WiX MSI build/inspect | **BLOCKED** | candle/wix not on PATH | Toolchain / owner build |

## Phase 6 — Release / ops

| Item | Status | Blocker / owner |
|---|---|---|
| GHA matrix green | **BLOCKED** | Billing / remote |
| SFace Q gate | **BLOCKED** | Corpus + eval harness results |
| Native ARM64 OpenCV load | **BLOCKED** | Historical DLL hang |
| Authenticode | **BLOCKED** | Cert |
| MSI WiX inspect | **BLOCKED** | Toolchain |

---

## Live verification (this machine, 2026-10-16)

| Check | Result |
|---|---|
| `search_text` on `%LOCALAPPDATA%\Semblon\store.sqlite` | SUCCESS with `media_ids` |
| NanoDet BYO probe | READY; SHA `4b82da99…0186` |
| NanoDet detect on archive JPG (4000×3000) | 3 hits: person×2, couch×1 |
| YuNet+SFace `embed_bgr` | 1 face, dim 128, no `person_id`; persons count unchanged |
| Pytest A–E suite | 52 passed (`test_discovery_slice_e`, `test_ae_shell_programme`, B/C/D, observers, MSI) |

---

## Programme dual verdict

| Verdict | Value |
|---|---|
| Locally implementable A–E product code | **COMPLETE** for code paths evidenced above |
| Release / ship readiness | **NOT COMPLETE** |
| Overall programme | **NOT COMPLETE** (external L/Q/GHA/ARM64/cert/WiX) |
