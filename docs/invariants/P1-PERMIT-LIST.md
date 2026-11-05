# P1a permit list (exact paths) — for S5 confirmation

**Freeze base:** `50722efa8a9522867e37db352c30bc5d786ec1e2`  
**List version:** 2026-11-05T03 (post-CONFIRM fixture + erasure amendment)  
**S5:** CONFIRMED 2026-11-05; amendment below records A5/A13 follow-ons only.

Criteria (from review): exact file paths · one-line justification · `tools/p0/` absent from permits · list hashed · freeze exclusions justified with forward disposition.

**Allow-list semantics:** Section B/S3/P1b paths may be edited only when the corresponding P1-PLAN work item requires them. Listing a path does not force an edit.

## A. Pre–Gate B (authorised now — detector + docs only)

| Path | Justification |
|---|---|
| `docs/invariants/P1-CONFIRMATION.md` | Plan read-back; durable review record |
| `docs/invariants/P1-PLAN.md` | Plan + gate; review dispositions |
| `docs/invariants/P1-PERMIT-LIST.md` | This list (S5) |
| `docs/invariants/P1-REJECTION-PATH-AUDIT.md` | Eight-path audit so A1 cannot “fix” closed paths |
| `docs/invariants/P1-REVIEW-DISPOSITION.md` | S1–S5 decisions + privacy retention |
| `docs/invariants/P0-COMPLETION-ADDENDUM.md` | Post-freeze append-only P0 sign-off / defects (frozen `P0-COMPLETION.md` untouched) |
| `docs/invariants/P1-ERASURE-SCOPE.md` | Erasure registration for identify_evaluations |
| `docs/invariants/README.md` | Index link updates only |
| `artifacts/p0/MANIFEST.json` | Durable sha256 pointers for gitignored raw P0 artifacts |
| `.gitignore` | Allow `artifacts/p0/MANIFEST.json` while keeping raw traces ignored |
| `tests/test_p1_i1_baseline_detectors.py` | Red detectors for issue #6 and R1–R8 audit (no production fix) |

**Explicitly absent from permits:** every `tools/p0/` path (see Forbidden).

**Frozen file not editable:** `docs/invariants/P0-COMPLETION.md` (bytes restored to freeze `50722ef`; further P0 completion facts go only in the addendum).

## B. P1a after Gate B (CONFIRMED)

No production edits until Gate B is recorded and this list is confirmed. Migration for `identify_evaluations` remains Gate-B-gated (S3) — **now authorised**.

| Path | Justification |
|---|---|
| `semblon/compare.py` | A1 fail-closed contract (R4–R8); R1–R3 already closed |
| `semblon/identify.py` | A2–A4 threshold/pack/ACCEPT paths through contract |
| `semblon/ingest.py` | A5 persist gate only (`_persist_faces` / contract check call); `_clear_unnamed_faces` not in this file |
| `semblon/eval.py` | A9 compare/threshold contract only; **no** `DEFAULT_THRESHOLD` value change |
| `semblon/review.py` | Conditional on need for A7; not authorised unless P1-PLAN A7 requires a local refuse beyond `compare()` |
| `semblon/search.py` | Conditional on need for A8; not authorised unless P1-PLAN A8 requires a local refuse beyond `compare()` |
| `semblon/erasure.py` | A13 day-one: delete `identify_evaluations` on person/face erasure |
| `tests/test_p1_i1_baseline_detectors.py` | Flip strict xfail → pass as defects close |
| `tests/test_compare.py` | Conditional on need; create/edit only if detectors are split from this file |
| `tests/test_identify.py` | Regressions for ACCEPT/UNKNOWN under contract + erasure of evaluations |
| `docs/invariants/P1-EVIDENCE.md` | Generated/updated P1 evidence record |
| `docs/invariants/P1-COMPLETION.md` | Gate fill-in at phase end |
| `tools/p1/README.md` | Conditional on need; authorised only if a `tools/p1/` harness is added |
| `tools/p1/__init__.py` | Conditional on need; package marker if `tools/p1/` harness is added |
| `tools/p1/reconcile.py` | Conditional on need; P1 reconcile wrapper invoking frozen `tools/p0` as-is |
| `artifacts/p1/MANIFEST.json` | Pointers for P1 evidence blobs |

### S3 migration (after Gate B only — additive)

Migration plumbing lives in `semblon/store.py` (`MIGRATIONS` / `apply_migrations`); there is no separate `migrations/` or alembic tree in this repo.

| Path | Justification |
|---|---|
| `semblon/store.py` | Additive `identify_evaluations` + observation-tree delete; no ALTER of existing tables |
| `tests/test_schema.py` | Migration up + `decisions.kind` untouched assertion |
| `docs/invariants/P1-ERASURE-SCOPE.md` | Finalise alongside migration landing |

### Fixture amendment (A5 — unit L2 mocks / schema pin)

Required so persist-gate + schema 7 do not false-fail existing fixtures. Not a production behaviour change beyond A5/A13.

| Path | Justification |
|---|---|
| `tests/test_audit_regressions.py` | Replace zero embeddings with unit L2 |
| `tests/test_scan_tiers.py` | Unit L2 mocks + SCHEMA_VERSION 7 pin |
| `tests/test_ingest_workers.py` | Unit L2 mocks |
| `tests/test_category_backfill.py` | Migration assert 6→7 |
| `tests/test_ship_audit.py` | Unit L2 mocks where needed |
| `tests/test_negative.py` | Unit L2 mocks |
| `tests/test_fullstack.py` | Unit L2 mocks |
| `tests/test_temporal.py` | Unit L2 mocks |
| `tests/test_progress.py` | Unit L2 mocks |
| `tests/test_visual_discovery.py` | Unit L2 mocks |

### P1b after B2 (not P1a)

| Path | Justification |
|---|---|
| `semblon/reembed.py` | A11 — only after deferral B2 closed |
| `tests/test_reembed.py` | A11 detectors/regressions; create only if missing when A11 runs |

## C. Freeze exclusions (justified + forward disposition)

| Path | Justification | Forward disposition |
|---|---|---|
| `.rescue-compare/` | Unrelated local rescue tree; not programme evidence; must not enter P0/P1 commits | Permanently excluded from this programme |
| `docs/ARCHITECTURE-AUDIT-2026-10-28.md` | Unrelated pre-existing untracked audit; outside invariant programme freeze | Permanently excluded from this programme (triage outside P0–P9 if ever needed) |

## D. Forbidden (exact paths)

| Path | Justification |
|---|---|
| `tools/p0/__init__.py` | Frozen observation instrument; edits void P0 audit |
| `tools/p0/README.md` | Frozen observation instrument; edits void P0 audit |
| `tools/p0/pytest_plugin.py` | Frozen observation instrument; edits void P0 audit |
| `tools/p0/reconcile.py` | Frozen observation instrument; edits void P0 audit |
| `tools/p0/sql_runtime_trace.py` | Frozen observation instrument; edits void P0 audit |
| `tools/p0/sql_static_inventory.py` | Frozen observation instrument; edits void P0 audit |
| `tools/p0/workflow_smoke.py` | Frozen observation instrument; edits void P0 audit |
| `docs/invariants/P0-COMPLETION.md` | Freeze artifact at `50722ef`; use addendum only |
| `semblon/cluster.py` | Clustering behaviour frozen; B2 guards SQL/lifecycle |
| `semblon/live.py` | Not production door; B2 if ever touched |
| `semblon/dedupe_sidecar.py` | B1 guards hashes/scans |
| `semblon/category_backfill.py` | Prefer contract inside `_persist_faces`; avoid backfill SQL / `_clear_unnamed_faces` (P2) |

Creating any **new** file under `tools/p0/` is also forbidden.

## Evidence hash chain (manifest)

| Artifact | Content SHA-256 | Introducing commit |
|---|---|---|
| `artifacts/p0/MANIFEST.json` | `5190afbd32aeada710442f695b99f0c18fd2fe98c7b5ab81f3601e8a7047c26a` | `0824f634097a9ec7570c612368ef3b95d5637318` |

Also recorded in `docs/invariants/P0-COMPLETION-ADDENDUM.md`.

## Frozen hash

**Verification procedure (authoritative):** SHA-256 over the UTF-8 bytes of this file **after deleting the single line that begins with** `**Content SHA-256`. Equivalents:

```
# POSIX
sed '/^\*\*Content SHA-256/d' docs/invariants/P1-PERMIT-LIST.md | sha256sum

# PowerShell
python -c "from pathlib import Path; import hashlib; b=Path('docs/invariants/P1-PERMIT-LIST.md').read_bytes();
lines=b.splitlines(True); body=b''.join(x for x in lines if not x.decode('utf-8','replace').startswith('**Content SHA-256'));
print(hashlib.sha256(body).hexdigest())"
```

The recorded hash is that digest. The hash line below is excluded from the hashed body.

**Content SHA-256 (UTF-8, this revision):** `784b8717817aadca76e79893aa0e38d8ace7a34e67efe93fcb2a7c055f033a33`
