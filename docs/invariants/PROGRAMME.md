# Invariant hardening programme (P0–P9)

**Product:** Semblon — local-first visual memory you can look into  
**Execution rule:** Evidence → detector → implementation → verification  
**Architecture:** reuse existing PySide6 → `Application` → domain / storage / providers. No second engine, job system, vector DB, or UI migration.

## Governing principle

No state in the application — backend or GUI — may claim more confidence than the underlying evidence supports.

## Backend invariants

| ID | Name | Rule |
|---|---|---|
| I1 | Identity integrity | Invalid, incompatible, corrupted or insufficient evidence can never produce identity acceptance. |
| I2 | Human decision preservation | Automated maintenance cannot destroy, silently replace or sever human decisions. Explicit authorised erasure is separate. |
| I3 | Source integrity | Analysis operates on the exact source bytes whose fingerprint it records. |
| I4 | Completion truth | Progress and completion are derived from durable, verifiable state. |
| I5 | Search integrity | Search is reproducible from canonical base-table evidence. Indexes are rebuildable projections. |
| I6 | Provenance and staleness | Every observation carries enough provenance to decide current / unverified / stale / invalid. |

## GUI invariant

| ID | Name | Rule |
|---|---|---|
| G1 | Evidence-bounded UI | No GUI state may be more confident than the underlying evidence. Ordinary UI never leaks internal state names. |

G1 applies in every phase. See [P0-GUI-STATE-TRANSLATION.md](P0-GUI-STATE-TRANSLATION.md).

## Phase programme (technical work, not ceremony)

| Phase | Focus | Status |
|---|---|---|
| P0 | Empirical evidence map and lifecycle reconciliation | **Frozen** at `50722ef` (+ addendum) |
| P1 | Identity trust boundary | **Complete** — `P1-COMPLETION.md` |
| P2 | Human decision preservation + ErasureIntent DB enforcement | **Complete** — `P2-COMPLETION.md` |
| P3 | Source integrity (single-buffer digest/decode) | **Complete** — `P3-COMPLETION.md` |
| P4 | Capability manifest (`available` / `unavailable` / `incompatible`) | **Complete** — `P4-COMPLETION.md` |
| P5 | Observation provenance states | Planned |
| P6 | Coverage truth on existing tables | Planned |
| P7 | Search evidence contract then FTS projection | Planned |
| P8 | Job idempotency and crash recovery | Planned |
| P9 | Resource bounds and safe destructive ops | Planned |

Do not add phases. Do not start P2+ without an explicit go. Verification uses feature / trust-critical / release levels (`P1-COMPLETION.md`), not per-change sign-off rituals.

## Discipline

Invariant → tests for invalid/failure/persist paths where trust-critical → implement → keep regressions. Docs record results; they do not replace tests.

A test that fails only because a proposed column is missing is not evidence of a provenance defect.

## Local-first

No cloud APIs, OpenAI, Google Cloud Vision, or generative AI. Local CV/ML remain permitted.

## Production chain (must preserve)

`semblon shell` → `native_shell/run.py` → `native_shell/host.py` → `Application` → `ArchiveModel` / `ShellBridge` / QML.
