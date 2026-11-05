# P1a completion — Identity trust boundary

**Status:** **P1a COMPLETE**. **P1 programme NOT COMPLETE** (A15 GUI / G1 open; P1b A11+A12 after B2).  
**Date:** 2026-11-05  
**Freeze base:** `50722efa8a9522867e37db352c30bc5d786ec1e2`  
**`tools/p0/` modified:** no  

Do not treat focused pytest green counts as a P1-complete claim.

## Roles

| Role | Name |
|---|---|
| P1 signer | B.H |
| Spot-checker | D.S |
| Adjudicator | C.G.T |

## Gate fill

| Gate | Result |
|---|---|
| Gate B (P0 + incident-defender + named signer) | PASS — addendum |
| S5 permit list confirmed | PASS — CONFIRMED + fixture amendment recorded |
| A1–A9, A13, A16 | PASS — see `P1-EVIDENCE.md` mapping |
| A4 gallery load validation | PASS — independent of probe; see evidence |
| A11 / A12 | Deferred **P1b** after **B2** (A12 = live writer disposition, acceptance criterion) |
| A15 GUI | **OPEN** — not A16 |
| Baseline integrity vs permit list | Spot-check SHA `8f0484778d575e359b362b4ffadea716891987d3` (`git diff --name-only 50722ef 8f04847`) |
| Privacy / no new p0 tools | PASS |
| Spot-check protocol (K=12) | **Pending D.S** — check SHA `8f04847`, not a moving tree |
| Adjudicator close | C.G.T named; protocol close awaits spot-check |

## What shipped (P1a)

- Fail-closed face `compare()` (NaN/Inf/L2/empty pack) + shared `validate_identity_embedding`
- Finite threshold gate; `DEFAULT_THRESHOLD` value unchanged
- Persist gate in `_persist_faces`
- Gallery exemplars contract-validated at `_gallery()` load (probe and gallery independent)
- Additive `identify_evaluations` (schema 7); `decisions.kind` CHECK unchanged
- Restart durability test for UNKNOWN + reason; `empty_gallery` reason asserted
- Day-one erasure registration + delete paths
- R1–R8 detectors green

## Explicit non-claims

- **P1 complete**
- Full-suite SQL trace coverage (D1)
- I1 “fully covered” while reembed / live disposition open (A11 / A12)
- GUI / G1 People verification (A15)
- Spot-check sample PASS (D.S still to run)
- Clustering / threshold retune / `tools/p0/` changes

## Next

1. D.S spot-check against **this commit SHA**.  
2. P1b: close B2 → A11; dispose A12 as acceptance criterion (not optional).  
3. A15 / G1 GUI evidence before any P1-complete claim.  
4. Do not start P2 until programme gate allows.
