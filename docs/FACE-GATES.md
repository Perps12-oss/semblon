# FACE-002 → FACE-005 (completed validation sequence)

Evidence is on `main`. This is a status index, not a second plan.

| Gate | Evidence commit | File |
|---|---|---|
| FACE-002 confirmatory | `751b11a` | `docs/FACE-002-CONFIRMATORY.md` |
| FACE-003 review 0.4 | `cb2523d` | `docs/FACE-003-REVIEW.md` |
| FACE-004 identify 1.0 | `b23a8c4` | `docs/FACE-004-IDENTIFY.md` |
| FACE-005 regression/scale | `6dc5a34` | `docs/FACE-005-REGRESSION.md` |

## Distinctions (do not collapse)

- Cluster ≠ person.
- STRONG ≠ person until `name`.
- Local confirmatory pair labels ≠ cluster membership and ≠ named-person identity.
- Identify is 1:N against **named persons**, never clusters.

## Evidence boundaries (do not exceed)

- Live scale: **90** stills (S1 golden `20260913T153515Z-1e915abe`).
- Confirmatory: **22** pairs (11 same, 11 different, 1 hard-negative).
- At frozen threshold **0.60** (`1 − eps`, `eps=0.40`): **FAR 0/11**, **FRR 1/11**.
- No 10k claim. PRODUCT “~10k first target” is a design target, not a run.
- Native ARM64 OpenCV **binary** proven (`cv2.cp314-win_arm64.pyd`, PE `0xaa64`). Semblon still uses x64 `cv2` (`0x8664`). S1 environment not swapped.
- Native x64 Windows FACE-000: **unverified** (no x64 PC). Not an ARM64 failure. No VM/emulation as native x64.

## Already on `main` (not this sequence’s missing work)

Incremental ingest + inbox: **1.1** (`ingest` hash skip, `inbox`, `name --face`).  
S6 `memory` 1.2 is on `main` (not part of FACE-002–005).

## Deferred (explicit)

- Bounded concurrent ingest workers
- Provider-aware CPU/GPU execution-provider selection
- Recording actual provider / device / worker in run evidence
- Folder watcher / daemon
- 10k ingest
- Consuming the ARM64 OpenCV pyd in the S1 path

## After FACE gates (2026-09-16)

S8 Interactive Review slice: `docs/S8-REVIEW-UI.md` (`review-ui`).  
Full deferred catalog + Phase 1 validation pause: `docs/ROADMAP-RECONCILE.md`.  
S7 video remains deferred. Do not invent a parallel plan.
