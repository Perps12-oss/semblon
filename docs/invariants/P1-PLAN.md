# P1 plan (implementation map)

**Active status:** `P1-COMPLETION.md`. This file is the work map, not a gate queue.

## Done (P1a)

Fail-closed identity compare · threshold gate · persist gate · gallery load validation · durable `identify_evaluations` · erasure day-one · non-face `compare_space` refuse.

## Done (P1 remainder)

| ID | Work |
|---|---|
| A11 | Re-embed: contract validation on write; delete stale `identify_evaluations` for rewritten / unmatched faces |
| A12 | Live: probe validate · write evaluations · retention deletes evaluations · never auto-assign `person_id` |
| A15 / G1 | Inbox + People copy: Named / Not sure / Not checked yet; machine ACCEPT ≠ named |

## Out of P1

| ID | Notes |
|---|---|
| A17 / P2 | ErasureIntent DB enforcement |
| Level 3 release | Full suite · dual-arch · packaging |

## Product invariants (keep)

No auto identity · false merge worse than false split · UNKNOWN valid · track ≠ person · fail-closed invalid embeddings · frozen thresholds / `decisions.kind` unless a separate product decision.
