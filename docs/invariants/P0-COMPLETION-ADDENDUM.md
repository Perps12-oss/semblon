# P0 completion addendum (post-freeze, append-only)

**Status:** Post-freeze only. Does **not** modify `P0-COMPLETION.md` (frozen at `50722efa8a9522867e37db352c30bc5d786ec1e2`).  
**Rule:** Append new dated sections only. Do not remove or rewrite prior addendum bytes in a way that drops history; new facts get a new dated section.

## 2026-11-05 — Freeze defects and Gate B roles

### Freeze defects (not in the frozen completion body)

| # | Defect | Disposition |
|---|---|---|
| A12 | P0 signer was unnamed in freeze evidence | Recorded here; see Gate B sign-off below |
| A13 | Raw `artifacts/p0/*.json` gitignored at freeze | Durable pointer: `artifacts/p0/MANIFEST.json` |

### `artifacts/p0/MANIFEST.json` hash chain

| Field | Value |
|---|---|
| Path | `artifacts/p0/MANIFEST.json` |
| Content SHA-256 | `5190afbd32aeada710442f695b99f0c18fd2fe98c7b5ab81f3601e8a7047c26a` |
| Introducing commit | `0824f634097a9ec7570c612368ef3b95d5637318` |
| Verification | `Get-FileHash artifacts\p0\MANIFEST.json -Algorithm SHA256` (Windows) or `sha256sum artifacts/p0/MANIFEST.json` |

If the manifest bytes change, append a new dated row here with the new hash and commit; do not silently edit the row above.

### Gate B sign-off (recorded 2026-11-05)

| Role | Name | Verdict |
|---|---|---|
| P0 programme signer | B.H | **SIGNED** |
| Incident defender (#11) | B.H | **SIGNED** |
| P1 signer / authorizer | B.H | Named |
| Spot-checker | D.S | Named |
| Adjudicator | C.G.T | Named (≠ B.H, ≠ D.S) |

Gate B body (P0 + incident-defender + named P1 signer) is satisfied. **S5 permit list CONFIRMED** (2026-11-05). Section B / S3 implementation authorised. **PROCEED** recorded 2026-11-05 with adjudicator **C.G.T** — see `P1-EVIDENCE.md` / `P1-COMPLETION.md`.

### Narrow S1 exception (pre–list-confirm; superseded by PROCEED)

Baseline I1 detectors (`tests/test_p1_i1_baseline_detectors.py`) and docs under the Section A permit list may land as evidence without behaviour change. Superseded once S5 confirm + Gate B + PROCEED authorised behaviour/schema.
