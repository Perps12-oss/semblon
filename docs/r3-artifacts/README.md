# R3 artifacts (§8.1–§8.7)

**Status:** COMPLETE for matrix + interaction cross-product + collision frames + state-triple grid + hierarchy test frames; bake-off checklist + harness present (**no measurements**); shell decision packet OPEN.  
**Authority:** `docs/R3-BRIEF.md` (visual/interaction). Roadmap: `docs/SEM-ARCH-V1.4.md` (§I.5 human gates **DEFERRED TO LAST** — development continues).  
**Date:** 2026-09-21  
**Not (yet as ship claims):** toolkit bake-off measurements (§8.5), naming a winner (§8.7), inventing schema columns. Shell chrome work against this pack **is authorized** while human gates wait.

Open the HTML frames in a browser. Spec docs are markdown. Reviewer hesitation on a collision pair = rule or rendering fails. Hierarchy frames are **TEST, not SPEC**.

| # | Artifact | Path |
|---|---|---|
| 8.1 | Complete state matrix (17 components) | [01-state-matrix.md](01-state-matrix.md) |
| 8.2 | Identity × processing interaction spec | [02-interaction-cross-product.md](02-interaction-cross-product.md) |
| 8.3 | Collision ledger — 15 comparison frames | [03-collision-frames.html](03-collision-frames.html) |
| 8.4 | State-triple grid — 30 cards | [04-state-triple-grid.html](04-state-triple-grid.html) |
| 8.5 | Bake-off checklist (human-run; no results) | [05-bake-off-checklist.md](05-bake-off-checklist.md) |
| 8.6 | Clickable hierarchy frames (TEST) | [06-hierarchy-frames.html](06-hierarchy-frames.html) |
| 8.7 | Shell decision packet (OPEN) | [07-shell-decision.md](07-shell-decision.md) |

Master human-verify → wire playbook (all gated plan items): [`docs/HUMAN-VERIFY-THEN-WIRE.md`](../HUMAN-VERIFY-THEN-WIRE.md).

Shared visual tokens (CSS): inlined in each HTML file from the brief’s grammar (notch + stroke texture; processing = shape, not hue).

## How to review

1. Read **01** — any shipped chrome state missing from the matrix is a bug.
2. Read **02** — illegal cells must not be painted as identity conclusions.
3. Open **03** — each pair side-by-side; if you hesitate, the pair fails. Footer must show pair count 15.
4. Open **04** — ingest × analysis are independent channels; identity notch cycles. Footer must show card count 30. Confusable pair = wrong channel assignment.
5. Use **05** + `semblon lab r3-bakeoff` / `tools/r3-bakeoff/` for real toolkit measurements on owner hardware — leave blanks until then.
6. Open **06** — click Library / People / Work nav; select an asset; confirm Inspector keeps evidence (machine) vs actions (human) split. Banner says TEST not SPEC.
7. Fill **07** only after a toolkit has six-of-six PASS; do not invent a winner from preference.

## Explicitly deferred (to **last** — SEM-ARCH §I.5)

- §8.5 Toolkit bake-off **measurements** against brief §6 (checklist + harness exist; no PASS claimed)
- §8.7 Naming a shell winner without measured bake-off
- APP-1 C.3 Windows live gate as a ship claim
- CONTRACTS product wire claim for durable **Ruled out** (scaffold may exist)
- Other owner-machine human verifies

Development of shell chrome / IA against this pack **must continue** meanwhile.
