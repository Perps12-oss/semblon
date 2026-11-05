# P0 completion record

## Identity

| Field | Value |
|---|---|
| Programme | Invariant hardening P0–P9 |
| Phase | P0 — Empirical evidence map and lifecycle reconciliation |
| Branch | `grok/p0-invariant-evidence` |
| Baseline HEAD | `af0758537fdd4f5240439ef163918db14defea9d` |
| Reconciliation date | 2026-11-05 |
| Schema version | 6 |
| Platform of evidence | Windows 10/11, Python 3.12.10, repo `.venv` |
| Working tree note | Unrelated untracked `.rescue-compare/` and `docs/ARCHITECTURE-AUDIT-2026-10-28.md` left untouched |

## Deliverables checklist

| # | Deliverable | Location | Status |
|---|---|---|---|
| 1 | Reconciled evidence map | [P0-EVIDENCE-MAP.md](P0-EVIDENCE-MAP.md) | Done |
| 2 | Writer/reader inventory | `artifacts/p0/sql_static_inventory.json` + evidence map | Done |
| 3 | Lifecycle semantics / transitions | [P0-LIFECYCLE.md](P0-LIFECYCLE.md) | Done (mutation suite unresolved) |
| 4 | P0 test / workflow evidence | focused 120 passed; workflow smoke 878 events | Done |
| 5 | Identity coverage manifest | [P0-IDENTITY-COVERAGE.md](P0-IDENTITY-COVERAGE.md) | Done (first manifest) |
| 6 | Unresolved gaps / exclusions | Listed below + per-doc | Explicit |
| 7 | Baseline commit + date | This record | Done |
| 8 | Sign-off | Below | **PENDING** |

## Instruments added (observation only — not P1)

- `tools/p0/sql_static_inventory.py`
- `tools/p0/sql_runtime_trace.py`
- `tools/p0/pytest_plugin.py`
- `tools/p0/workflow_smoke.py`
- `tools/p0/reconcile.py`

## Commands actually run

| Command | Outcome |
|---|---|
| `python tools/p0/sql_static_inventory.py --summary` | connect=131 exec=524 dynamic=36 writers=183 readers=265 tables=30 |
| `python tools/p0/workflow_smoke.py` | ok; 878 SQL events |
| pytest focused suite + SQL trace (see evidence map) | **120 passed** in 186s; 95 391 events; 39 connections |
| `python tools/p0/reconcile.py` | static_only=`hashes`,`scans` classified as dedupe sidecar |

| Not run | Reason |
|---|---|
| Full `pytest -q` under trace | Time / volume; focused identity+lifecycle set used |
| Live `semblon shell` GUI scripted Add Folder | Not automated this pass |
| Owner FaceKit dump ingest | Weights BYO; owner machine |
| kill -9 recovery | P8 |
| Five-person usability study | Acceptance on P1–P9; not a P0 coding task |

## Explicit unresolved gaps

1. Lifecycle **mutation testing** of every declared edge — unresolved.  
2. Dedupe sidecar (`hashes`/`scans`) runtime reconcile — deferred.  
3. `reembed.py` / `live.py` / full cluster suite under SQL trace — deferred.  
4. G1 translation **automated detectors** — not written in P0.  
5. No `ErasureIntent` DB enforcement (P2).  
6. `compare()` does not reject NaN/Inf (P1 detector baseline expected to fail).  
7. `_decode_bgr` may re-read path after decode failure; tier1/2 decode from path (P3).  
8. `category_backfill._clear_unnamed_faces` deletes decisions (P2).  
9. `incompatible` capability state unused (P4).  
10. Provenance tuple / `legacy_unverified` absent (P5).  
11. Human incident-defender **sign-off** — pending.

## Sign-off

P0 is complete only when the person responsible for defending Semblon during an incident reviews the evidence and signs below.

| Role | Name | Date | Verdict |
|---|---|---|---|
| Incident defender / programme owner | _pending_ | _pending_ | **NOT SIGNED** |

**Do not start P1 implementation until this table records an explicit sign-off.**

## Changed files (this phase)

Documentation under `docs/invariants/`; observation tools under `tools/p0/`; generated evidence under `artifacts/p0/` (local regenerate; do not treat large traces as review text). No P1 identity-enforcement code. No schema migration. No threshold changes.
