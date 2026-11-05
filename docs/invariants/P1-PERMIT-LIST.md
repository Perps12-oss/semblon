# P1a permit list (exact paths) — for S5 confirmation

**Freeze base:** `50722efa8a9522867e37db352c30bc5d786ec1e2`  
**List version:** 2026-11-05T01  
**Hasher:** SHA-256 of this file’s UTF-8 bytes after the frozen hash line is filled (see footer).

Criteria (from review): exact file paths · one-line justification · `tools/p0/` absent · list hashed · freeze exclusions justified.

## A. Pre–Gate B (authorised now — detector + docs only)

| Path | Justification |
|---|---|
| `docs/invariants/P1-CONFIRMATION.md` | Plan read-back; durable review record |
| `docs/invariants/P1-PLAN.md` | Plan + gate; review dispositions |
| `docs/invariants/P1-PERMIT-LIST.md` | This list (S5) |
| `docs/invariants/P1-REJECTION-PATH-AUDIT.md` | Eight-path audit so A1 cannot “fix” closed paths |
| `docs/invariants/P1-REVIEW-DISPOSITION.md` | S1–S5 decisions + privacy retention |
| `docs/invariants/README.md` | Index link updates only |
| `docs/invariants/P0-COMPLETION.md` | Record review/sign-off state and freeze defects (no claim rewrite of evidence map) |
| `artifacts/p0/MANIFEST.json` | Durable sha256 pointers for gitignored raw P0 artifacts |
| `.gitignore` | Allow `artifacts/p0/MANIFEST.json` while keeping raw traces ignored |
| `tests/test_p1_i1_baseline_detectors.py` | Red detectors for issue #6 and R1–R8 audit (no production fix) |

**Explicitly absent:** `tools/p0/` (unmodified).

## B. P1a after Gate B (proposed — confirm or strike)

No production edits until Gate B (P0 sign-off · incident-defender #11 · named P1 signer). Migration for `identify_evaluations` is separate and also Gate-B-gated (S3).

| Path | Justification |
|---|---|
| `semblon/compare.py` | A1 fail-closed contract (R4–R8); R1–R3 already closed |
| `semblon/identify.py` | A2–A4 threshold/pack/ACCEPT paths through contract |
| `semblon/ingest.py` | A5 persist gate only (`_persist_faces` / contract check call) |
| `semblon/eval.py` | A9 compare/threshold contract only; **no** `DEFAULT_THRESHOLD` value change |
| `semblon/review.py` | A7 only if compare call sites need local refuse; prefer compare-only |
| `semblon/search.py` | A8 only if face compare call sites need local refuse; prefer compare-only |
| `tests/test_p1_i1_baseline_detectors.py` | Flip strict xfail → pass as defects close |
| `tests/test_compare.py` | Optional focused contract unit tests if split from detectors |
| `tests/test_identify.py` | Regressions for ACCEPT/UNKNOWN under contract |
| `docs/invariants/P1-EVIDENCE.md` | Generated/updated P1 evidence record |
| `docs/invariants/P1-COMPLETION.md` | Gate fill-in at phase end |
| `tools/p1/README.md` | P1 evidence harness docs (if tools added) |
| `tools/p1/__init__.py` | Package marker for P1 tools only |
| `tools/p1/reconcile.py` | P1 reconcile wrapper invoking frozen `tools/p0` as-is |
| `artifacts/p1/MANIFEST.json` | Pointers for P1 evidence blobs |

### S3 migration (after Gate B only — additive)

| Path | Justification |
|---|---|
| `semblon/store.py` | Additive `identify_evaluations` table + migration N+1; no ALTER of existing tables |
| `tests/test_schema.py` | Migration up/down + `decisions.kind` untouched assertion |
| `docs/invariants/P1-ERASURE-SCOPE.md` | Day-one erasure registration for identify_evaluations (P2 liability) |

### P1b after B2 (not P1a)

| Path | Justification |
|---|---|
| `semblon/reembed.py` | A11 — only after deferral B2 closed |
| `tests/test_reembed.py` | A11 detectors/regressions (create only if missing) |

## C. Freeze exclusions (justified, not merely noted)

| Path | Justification |
|---|---|
| `.rescue-compare/` | Unrelated local rescue tree; not programme evidence; must not enter P0/P1 commits |
| `docs/ARCHITECTURE-AUDIT-2026-10-28.md` | Unrelated pre-existing untracked audit; outside invariant programme freeze |

## D. Forbidden (any phase of this plan)

| Path | Justification |
|---|---|
| `tools/p0/**` | Frozen observation instruments; edits void P0 audit |
| `semblon/cluster.py` | Clustering behaviour frozen; B2 guards SQL/lifecycle |
| `semblon/live.py` | Not production door; B2 if ever touched |
| `semblon/dedupe_sidecar.py` | B1 guards hashes/scans |
| `semblon/category_backfill.py` | Prefer contract inside `_persist_faces`; avoid backfill SQL / `_clear_unnamed_faces` (P2) |

## Frozen hash

After this file is final for a commit, compute:

```
sha256sum docs/invariants/P1-PERMIT-LIST.md
```

**Content SHA-256 (UTF-8, this revision):** `4bdaf397db4e773f90dfc0a007ec370e2b9dacccccda0881c688032c1fda7c92`  

The implementing commit message must replace `PENDING_COMMIT_FILL` with the hash of the file **excluding** the hash line itself, or hash the file with the placeholder left as the literal string `PENDING_COMMIT_FILL` and record that digest below once.

**Procedure used:** hash of file bytes with the line `**Content SHA-256 (UTF-8, this revision):** \`PENDING_COMMIT_FILL\`` present unchanged.
