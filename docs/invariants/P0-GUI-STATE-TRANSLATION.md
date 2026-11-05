# P0 — G1 state translation table and GUI acceptance gaps

**G1:** No GUI state may be more confident than the underlying evidence.  
**Baseline:** `af0758537fdd4f5240439ef163918db14defea9d`  
**Inventory date:** 2026-11-05  

This is a **contract inventory**, not permission to redesign the shell. P0 does not implement speculative QML changes.

## Contract translation table

| Internal state | User-visible wording | Where shown | Current code status |
|---|---|---|---|
| `verified` | *(nothing)* | Never; default | **No such provenance state in schema yet** (P5). |
| `legacy_unverified` | Not re-checked since update | Expandable Details only | **Absent** — not implemented. |
| `stale` | Will update in background | Status line while reindexing | Partial: coverage notes exist (`scan_tiers.coverage_note`, category messages); no formal `stale` enum. |
| `invalid` | Couldn’t read this file | Per-item status with retry | Partial: category `read_failure` / failed copy; not a unified per-item badge. |
| `unavailable` capability | Optional feature not installed | Settings only | **Drift:** `surfaceState === "unavailable"` used broadly in shell (`Table.qml` treats as problem). Install suggestions exist. |
| `incompatible` capability | Paused until update | Non-blocking capability banner | **Present (P4):** `capability_manifest` + Settings pause copy + bridge notice. |
| Identity `UNKNOWN` | Not sure | People tab | **Present:** inbox + People copy; durable via `identify_evaluations`. |
| `below_threshold` | *(no ordinary wording)* | Reason detail only when requested | Scores live in decisions/policy; ordinary UI does not show reason codes — OK-ish; no formal Details reason panel contract tests. |
| `pack_mismatch` / `non_finite` | Recognition needs re-check | Banner when relevant | Backend refuses mismatch (tests); **no dedicated G1 banner copy** for non_finite (no check yet). |
| `unsupported` | File type not supported | Per-item coverage details | Backend: `skipped`+`outcome=unsupported`. Discover coverage text explains categories; not always per-item in Field. |
| `SOURCE_CHANGED` | Changed during scan — will retry | Transient status | **Present (P3):** `source_changed` outcome + message; ingest/category verify sha256 before analysis. |
| Missing original | Original file missing | Per-item coverage | Backend + bridge `_report_missing_original` copy exists. |
| Interrupted job | Resuming… | Transient status | Resume paths exist (`resume`, recover_interrupted). Copy is not uniformly “Resuming…”. |
| Recovered interrupted job | Picking up where we left off | Status; never automatic “Error” | **Gap:** recoverable interrupt can still surface failed/unavailable depending on path; needs P8 + copy audit. |

Any newly discovered internal state must be added here **before** ordinary UI exposure.

## Where GUI state originates today

| Surface | Origin | Notes |
|---|---|---|
| Job chrome (`jobState`, fraction, pause) | `ShellBridge` ← `Application`/`JobEngine` transient state + progress events | Percent shown in `Table.qml` when `jobTotal > 0` — prefer sentence progress (programme rule). |
| Progress copy | `semblon/ui_copy.py` | Explicitly avoids inventing percent; still emits percent when totals exist. |
| Discover coverage | `category_backfill.discover_coverage_text` | Honest category sentences; good P6 starting point. |
| Search empty / partial | `search.py` + `search_state_note` / `coverage_clause` | Distinguishes unchecked / failed / missing — aligns with P7 GUI obligation direction. |
| People / Not sure | `People.qml` + adapter unresolved counts | UNKNOWN treated as navigable, not only error — **P1 GUI direction already partly met**. |
| “Not this person” | `product_surface.VERB_LABEL_RULE_OUT` → review reject | Durable reject; confirm Undo reliability before advertising Undo (P2). |
| Missing photo | `bridge._report_missing_original` | User-facing path reconnect guidance. |
| Capability install | Settings / install actions | **P4:** missing = installable; incompatible = pause copy, not install. |

## Overstatement risks (acceptance gaps)

| Risk | Evidence | Phase |
|---|---|---|
| `unavailable` used as generic problem surface | `Table.qml` `surfaceState === "unavailable"` styled with error | G1 / P4 |
| Job % without sentence | `Getting photos ready N%` | G1 / P9 |
| Machine identify ACCEPT reflected as named person without human name | identify does not auto-set person_id (good); UI must not imply named | P1 |
| UNKNOWN vs never evaluated | **Closed in P1:** `NOT_CHECKED` vs `UNKNOWN` + People ordinary wording | P1 done |
| Coverage complete implication on home | Discover text is careful; home must stay calm (no red badge) | P6 |
| Empty search = exhaustive absence | Partial mitigation via coverage clauses; needs contract tests | P7 |
| Reject implies deletion | Need copy audit for “Nothing was removed” | P2 |
| Source race as modal error | **Closed in P3:** no imread fallback; digest mismatch → retry copy | P3 done |
| Interrupt as Error | Job failed mapping exists; recovered interrupt copy not locked | P8 |

## Required G1 tests (not yet present — P0 gap list)

1. Every user-relevant internal state has a translation row (this table).  
2. Ordinary UI never displays raw state identifiers / reason codes.  
3. UI cannot display a more confident state than underlying data.  
4. Details views still expose relevant states when expanded.

**Status:** Table documented. Automated detectors **not implemented** in P0 (implementation would be P1+ / G1 continuous). First-time usability study with five people is an acceptance requirement on P1–P9, not a separate phase — **not run**.

## First-run narrative vs current shell

Intended narrative (programme) vs inventory:

1. “Let’s look at your photos” / Add Folder — Safelight / home desk direction exists (`BUILD-STATUS`).  
2. Scanning counts from durable work — progress events + category coverage partially; ingest counters are process events (verify vs durable in P6/P8).  
3. Completion counts only if supported — needs audit against false cluster/person counts.  
4. Background reindex sentence — coverage notes exist; not a single banner contract.  
5. Capability incompatibility banner — **Present (P4)** via notice strip + Settings pause copy.  
6. Empty search + coverage pointer — partially present.

## Per-phase GUI obligations (tracking)

| Phase | Obligation | P0 finding |
|---|---|---|
| P1 | Named and Not sure peers; Not sure actionable | Directionally present in People.qml |
| P2 | Reject confirms suggestion rejected; nothing removed; Undo only if real | Verb exists; copy/Undo audit pending |
| P3 | Source mutation as retry | Not standardised |
| P4 | Capability-specific non-blocking | **Closed in P4** |
| P5 | legacy_unverified in Details only | State absent |
| P6 | What’s been indexed calm home | Discover text; dedicated view TBD |
| P7 | Empty ≠ exhaustive if incomplete | Partial |
| P8 | Recoverable = picking up | Partial |
| P9 | Meaningful long-op status | Partial (`ui_copy` / job note) |
