# P1 plan — Identity trust boundary (plan only; no code)

**Status:** REVIEWED — dispositions in [P1-REVIEW-DISPOSITION.md](P1-REVIEW-DISPOSITION.md). Behaviour/schema still Gate-B gated.  
**P0 freeze commit:** `50722efa8a9522867e37db352c30bc5d786ec1e2`  
**P0 evidence baseline:** `af0758537fdd4f5240439ef163918db14defea9d`  
**Schema:** 6 (additive `identify_evaluations` exception granted under S3; migration Gate-B gated)  
**Confirmation:** [P1-CONFIRMATION.md](P1-CONFIRMATION.md)  
**P1 signer (authorizer):** B.H · **Spot-checker / adjudicator:** unset (S2)

---

## 1. Problem

I1 is inventoried but not enforced: invalid / non-finite / under-contract vectors can still reach `compare()` and, on some paths, contribute to ACCEPT. P1 makes the smallest fail-closed change set that the P0 identity manifest already names — without reopening P0, without schema migration (unless the signer grants an exception), and without touching guarded subsystems before their deferrals close.

## 2. Scope

### Scope A — identity manifest → work items

Each row is a **work item derived from** `P0-IDENTITY-COVERAGE.md`. No new identity paths. Missing paths discovered during work are **findings**, not scope expansion.

| ID | Manifest entry | P1 work | Touches | Guarded? |
|---|---|---|---|---|
| A1 | Compare contract gaps (NaN/Inf, L2, unknown contract) | Strengthen `compare()` / shared contract check used by all face identity scores; detector that **fails on baseline** for NaN/Inf/cross-pack/wrong-dim/bad-norm | `semblon/compare.py` (+ thin helper in same module if needed) | No |
| A2 | Threshold validation | Reject non-finite / out-of-policy threshold inputs at identify entry; **do not change** `DEFAULT_THRESHOLD` value | `semblon/identify.py`, callers that pass threshold | No |
| A3 | Identify ACCEPT/UNKNOWN paths | Ensure every identify scoring path goes through A1; ACCEPT only after contract pass; UNKNOWN remains valid | `semblon/identify.py` | Dynamic site in identify (1) — bound or name |
| A4 | Gallery / pack gate | Keep pack-filtered gallery; refuse probe pack≠run; no silent continue that yields false ACCEPT from bad probe | `identify.py` (existing refuse paths) | No |
| A5 | Ingest face persist | Reject or mark non-ok when embedding fails contract **before** status=`ok` with blob | `ingest._persist_faces` | Dynamic site (1) — if touched, dispose |
| A6 | People backfill face persist | Same contract as A5 via shared persist helper or shared check | `category_backfill.process_people` → `_persist_faces` | Dynamic sites in category_backfill — **only if that file’s SQL shape changes**; prefer check inside `_persist_faces` to avoid backfill SQL edits |
| A7 | Review compare uses | `review.py` face compares must fail closed on bad vectors (no ACCEPT-equivalent ranking from NaN) | `review.py` | Dynamic site (1) if SQL touched; prefer compare-only |
| A8 | Search face compare | `search.py` face similarity must not treat invalid vectors as hits | `search.py` | Dynamic site (1) if SQL touched |
| A9 | Eval compare | `eval.py` compare path same contract; no threshold retune | `eval.py` | No |
| A10 | Cluster `compare()` use | **No change to clustering behaviour or `cluster.py` SQL/lifecycle.** Benefit only via A1 hardening of `compare()`. Disposition: `observed` via A1; module SQL `not_touched` | `cluster.py` — **do not edit** unless deferral B2 closed and signer allows | **Yes — B2** if edited |
| A11 | Reembed rewrite | Harden embedding write contract | `reembed.py` | **Yes — B2** — close B2 first |
| A12 | Live overlay delete/write | **Acceptance criterion for full I1 writer coverage** (not optional). Prefer disposition `not_production_door` + evidence; edit only if treated as identity writer. **Not** probe/gallery compatibility (that is A4). | `live.py` | **Yes — B2** if edited |
| A13 | Durable UNKNOWN vs never evaluated | Additive `identify_evaluations` (S3 exception) | **Gate B then migrate**; erasure scope day one; `decisions.kind` untouched | Migration after Gate B |
| A14 | Typed `IdentityVector` | Only if it fits without schema/API churn | Optional envelope around bytes+pack+dim in `compare.py` / identify | No |
| A15 | G1 People: Named / Not sure peers | Inventory says directionally present; **no opportunistic GUI redesign**. Only copy/tests if A13/A3 leave a false confidence claim | QML/bridge only if evidence shows overclaim | No redesign |
| A16 | Non-face embeddings | Confirm `compare_space` still refuses face; no identity vote | already present — regression only | No |
| A17 | Erasure / observation-tree / `_clear_unnamed_faces` | **Not P1** (P2) | — | Out of scope |
| A18 | Eval pairs writer | No change unless compare contract requires it | — | Default out |

### Scope B — triggered deferrals (must close before touching guarded code)

| ID | Deferral | Trigger | Expected evidence to close | Owner |
|---|---|---|---|---|
| B1 | `hashes`/`scans` runtime reconcile | Before any dedupe sidecar writer/reader change | SQL trace under P0 method over `tests/test_dedupe_*.py` (+ smoke if needed); reconcile static↔runtime; update P1 evidence record — **without modifying `tools/p0/`** (invoke as-is; write outputs under `artifacts/p1/`) | P1 implementer |
| B2 | `reembed` / `live` / cluster suite under SQL trace | Before changing those modules’ SQL or lifecycle | Trace `tests/test_cluster.py` + reembed/live tests; reconcile; dispositions recorded | P1 implementer |

**Earliest trigger against this plan:**  
- Default P1 slice (A1–A9, A14, A16) does **not** edit dedupe, reembed, live, or cluster → **neither B1 nor B2 fires**.  
- A11 (reembed) fires **B2** before that work item.  
- Any cluster.py edit fires **B2**.  
- Any dedupe edit fires **B1**.

**First closure task when implementation starts:** If the reviewed plan keeps A11 in-scope for P1 closure of I1 writers, **close B2 first**. If A11 is deferred to a later slice, first implementation task is A1 detectors on baseline — no B1/B2 work yet. **Recommendation:** defer A11/A12 to a P1b slice; close B2 immediately before that slice; do not claim full writer coverage until then.

## 3. Explicitly not P1

ErasureIntent DB enforcement; `_decode_bgr` path re-read; `_clear_unnamed_faces`; `incompatible` capability; provenance / `legacy_unverified`; kill-9 recovery; schema migrations; threshold value changes; clustering behaviour changes; `tools/p0/` edits; regenerating P0 baseline artifacts.

## 4. Inherited obligations → tasks

| Obligation | P1 task |
|---|---|
| 36 dynamic sites | For each subsystem file P1 edits that contains dynamic SQL, add a disposition row (bound shape / unbounded-partial named). Prefer changes that avoid editing dynamic SQL call sites (centralise in `compare()` / `_persist_faces`). |
| Privacy | If `tools/p1/` adds tracing: shape-only; add `tests/test_p1_trace_privacy.py` (or equivalent) that fails if values/paths/OCR appear in sample output. |
| Coverage accounting | After P1 code lands, run static inventory **via frozen `tools/p0/sql_static_inventory.py` unchanged**; store delta under `artifacts/p1/`; any new site must have runtime attribution. |
| Match method | Reuse P0 traced-connection callsite attribution; document in P1 evidence record; no second join key. |

## 5. Signer decisions required before code (blockers)

| Decision | Options | Recommendation |
|---|---|---|
| **S1 — P0 sign-off** | (a) Sign `P0-COMPLETION.md` then authorise P1 impl; (b) written exception to implement under PENDING | Do not impl until (a) or (b) |
| **S2 — Named P1 signer** | One person ≠ tools/p1 author ≠ spot-checker | **FINDING: name not available** — must be supplied |
| **S3 — Durable UNKNOWN** | (a) Exception allowing `identify_evaluations` migration; (b) reuse `decisions` with stricter policy_json + always-record; (c) defer durability to later phase | Prefer escalate: (a) vs (c). (b) conflicts with “do not overload decisions.kind” from original brief |
| **S4 — A11 reembed in P1a** | Include (close B2 first) vs defer P1b | Defer to P1b |
| **S5 — IdentityVector type** | Thin TypedDict/dataclass vs skip | Thin optional; only if it clarifies A1 |

## 6. Proposed implementation order (after plan review + S1)

1. **Detectors first (baseline red):** NaN, Inf, cross-pack same-dim, wrong dim, absurd length, non-finite threshold → must **not** ACCEPT. Prove failure on freeze-baseline behaviour.  
2. **A1** fail-closed contract in `compare()` (and shared validate used by persist if needed).  
3. **A2–A4, A7–A9, A16** wire-through / regressions.  
4. **A5/A6** persist gate so `status='ok'` cannot hold non-finite blobs.  
5. **A14** only if still clarifying.  
6. **A15** only if a concrete overclaim remains.  
7. **P1b:** close **B2**, then A11 (and A12 disposition).  
8. **A13** only after S3.  
9. Reconcile → fill P1 gate rows → spot-check → signer.

## 7. P1 gate structure (pre-built; fill at end of phase)

### 7.1 Row-per-change record (template)

| Change ID | Subsystem | Sites touched | Disposition before | Disposition after | Verifying test | Dynamic-site effect | Residual risk |
|---|---|---|---|---|---|---|---|
| _(filled when change lands)_ | | | observed / partially_observed / not_observed / deferred | | test that fails without change | bounded / touched / blocked / none | |

### 7.2 Dynamic-site status column

Required on every change row (above). Unbounded-partial sites named for signer acknowledgement.

### 7.3 Deferral register (P1)

| ID | Item | Owner | Phase | Trigger | Expected evidence | Status |
|---|---|---|---|---|---|---|
| B1 | hashes/scans runtime reconcile | P1 implementer | P1 | Before dedupe change | Trace + reconcile under `artifacts/p1/` | Open — not fired by P1a |
| B2 | reembed/live/cluster SQL trace | P1 implementer | P1 | Before those modules’ SQL/lifecycle change | Trace + reconcile | Open — **named trigger for D6** |
| D1 | Full pytest under SQL trace | Programme | later | Before claiming whole-suite coverage | Full suite trace | Open (from P0) |
| D2 | Production shell Add Folder smoke | Programme | later | Before GUI completion claims | Scripted smoke | Open (from P0) |
| D3 | identify_evaluations / durable UNKNOWN | P1 after Gate B | P1a | Gate B + S3 terms | Additive migration + erasure registration + decisions.kind test | **Exception granted; migration not started** |
| D4 | G1 automated translation detectors | Programme | G1 continuous | Before G1 PASS claim | Detector tests | Open (from P0) |
| D5 | Lifecycle mutation suite | Programme | P6 | Before lifecycle “fully covered” claim | Mutation coverage report | Open (from P0) |
| D6 | A11 reembed contract | P1 implementer | **P1b** | **B2 closed** | Detector + persist tests on `reembed.py` | **Registered** — blocked on B2 |
| D7 | A12 live.py | P1 | **P1b** | Before claiming full I1 writer coverage | Trace + disposition (`not_production_door` or harden) | **Acceptance criterion** — not probe/gallery (A4) |

### 7.4 Baseline-integrity check

From P0 freeze `50722ef` to P1 reconciliation commit:

```
git diff --name-only 50722efa8a9522867e37db352c30bc5d786ec1e2 <P1_RECON_COMMIT>
```

**Exact permit list (S5):** [P1-PERMIT-LIST.md](P1-PERMIT-LIST.md) — hashed; awaiting authorizer confirm/strike. Do not use directory globs.

### 7.5 Privacy verification

| Check | Status |
|---|---|
| New logs omit values/paths/OCR/names | verified / unverified (fill with test name) |
| Trace-inspection test present | required if any new instrumentation |

### 7.6 Independent spot-check protocol

| Field | Value |
|---|---|
| Sample size K | **Proposed K=12** identity-related change rows / SQL sites (adjust if &lt;12 changes) |
| Sampling method | Stratified: ≥1 from compare, identify, persist, search/review if touched; remainder uniform from change register |
| Seed | Recorded at spot-check time (`SEMBLON_P1_SPOT_SEED` or documented integer) |
| Raw-evidence inspection | Spot-checker reads test output + disposition rows; does not author `tools/p1/` |
| Adjudicator | **≠** tools/p1 author, **≠** spot-checker — **NAME REQUIRED** |
| Caution (must appear on sign-off) | A passing sample does not prove the map correct; it tests whether the map is trustworthy. |

### 7.7 Named signer

| Role | Name |
|---|---|
| P1 signer (one person; ≠ tools/p1 author; ≠ spot-checker) | **B.H** |
| Spot-checker | **D.S** |
| Adjudicator | **unset — required before spot-check protocol closes** |

## 8. Worth doing now / skip / pushback

| Class | Items |
|---|---|
| **Worth doing now (after review + S1)** | A1 detectors→fix; A2–A9; A16; persist gate A5/A6; P1 evidence harness under `tools/p1/` if needed for reconcile **without** editing `tools/p0/` |
| **Skip / defer** | A11/A12 until B2; A13 until S3; GUI redesign; dedupe; schema; thresholds; cluster behaviour |
| **Pushback** | Implementing `identify_evaluations` under a silent migration violates this handoff — escalate via S3. Claiming I1 “fully covered” while reembed untraced/unfixed violates the manifest. Starting implementation while P0 sign-off is PENDING violates `P0-COMPLETION.md` unless S1(b) is written. |

## 9. Findings section (P0 tooling / record — do not fix in P1)

1. `artifacts/p0/*.json` gitignored — freeze commit does not contain the machine inventory blob.  
2. No standalone P0 deferral-register file; reconstituted here.  
3. P0 tools not modified even if defects found; any tool bug → separate tooling PR against a **new** baseline, not P1.  
4. (Reserve lines here during impl for any `tools/p0/` defects discovered — record only.)

## 10. Ask (remaining)

1. Confirm or strike entries in [P1-PERMIT-LIST.md](P1-PERMIT-LIST.md) (**S5**).  
2. Name **spot-checker** and **adjudicator** (**S2**).  
3. Complete **Gate B** (P0 sign-off · incident-defender #11 · roles) before behaviour/schema.  

**Authorised now (S1 narrow):** baseline detectors + docs on this branch. **Not authorised:** compare() fix, migration, Task 3 deferral closure until S5 (and Gate B where required).
