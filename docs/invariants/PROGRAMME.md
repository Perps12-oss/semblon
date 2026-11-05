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

## Frozen phase programme

| Phase | Focus | Status |
|---|---|---|
| P0 | Empirical evidence map and lifecycle reconciliation | **IN PROGRESS — awaiting sign-off** |
| P1 | Identity trust boundary | Blocked on P0 sign-off |
| P2 | Human decision preservation + ErasureIntent DB enforcement | Blocked on P1 |
| P3 | Source integrity (single-buffer digest/decode) | Blocked on prior |
| P4 | Capability manifest (`available` / `unavailable` / `incompatible`) | Blocked on prior |
| P5 | Observation provenance states | Blocked on prior |
| P6 | Coverage truth on existing tables | Blocked on prior |
| P7 | Search evidence contract then FTS projection | Blocked on prior |
| P8 | Job idempotency and crash recovery | Blocked on prior |
| P9 | Resource bounds and safe destructive ops | Blocked on prior |

Do not add phases. Do not implement P1+ until P0 is signed off by the person who would defend the system in an incident.

## Discipline

Every invariant follows: invariant → detector → baseline failure → implementation → passing detector → permanent regression gate.

A test that fails only because a proposed column is missing is not evidence of a provenance defect.

## Local-first

No cloud APIs, OpenAI, Google Cloud Vision, or generative AI. Local CV/ML remain permitted.

## Production chain (must preserve)

`semblon shell` → `native_shell/run.py` → `native_shell/host.py` → `Application` → `ArchiveModel` / `ShellBridge` / QML.
