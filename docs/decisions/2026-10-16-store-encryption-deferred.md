# Decision: Store encryption deferred (design only)

**Date:** 2026-10-16  
**Status:** Current — DEFERRED for this release  
**Tracker:** `docs/BUILD-STATUS.md` issue 02

## Decision

Do **not** encrypt the live SQLite store in this release. The store remains plaintext under the user ACL (`docs/THREAT-MODEL.md`). Expanding this design is required before any implementation.

## Threat model (summary)

Sensitive assets: display names, file paths, 512-d face templates in `store.sqlite` (+ WAL/SHM).

Protected today: other Windows users (ACL); crash-safe migration/restore paths already hardened.

Not protected: same-user malware; synced backup folders; stolen disk.

## Required design before implementation (not coded)

| Topic | Requirement |
|---|---|
| Key management | Windows DPAPI vs password; recovery if key lost; multi-machine forbid |
| WAL / SHM | Encrypt or checkpoint so WAL cannot leak plaintext beside an encrypted main file |
| Backup | Encrypted backup format or explicit plaintext backup warning |
| Migration | Copy to disposable target; verify integrity (page count, PRAGMA integrity_check, row counts); atomic replace only after success |
| Interruption | Fail closed; never leave half-encrypted live library |
| Rollback | Keep pre-migration backup until N successful opens |
| Prototype | Disposable copies only — never the user’s live library |

## Prototype rule

Any encryption experiment uses throwaway fixtures under a temp directory. Live `%LOCALAPPDATA%` libraries are out of scope.

## Claims

Do **not** claim the store is encrypted. Document residual risk: stolen-disk plaintext until this feature ships.
