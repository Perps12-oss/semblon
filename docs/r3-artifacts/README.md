# R3 artifacts

**Status:** Artifacts 1–3 CANONICAL (owner paste); Artifact 4 criteria CANONICAL, **measurements DEFERRED TO LAST**; hierarchy frames TEST; shell decision OPEN.  
**Authority:** `docs/R3-BRIEF.md` (visual/interaction). Roadmap: `docs/SEM-ARCH-V1.4.md` (§I.5 human gates **DEFERRED TO LAST** — development continues).  
**Date:** 2026-09-21  
**Not (yet as ship claims):** toolkit bake-off measurements, naming a winner, inventing schema columns. Shell chrome work against this pack **is authorized** while human gates wait.

Open the HTML frames in a browser. Spec docs are markdown. Reviewer hesitation on a collision pair = rule or rendering fails. Hierarchy frames are **TEST, not SPEC**.

## Canonical Artifacts 1–4

| # | Artifact | Path |
|---|---|---|
| 1 | Full state matrix (17 components) | [01-state-matrix.md](01-state-matrix.md) |
| 2 | State triple (ingest × analysis × identity) | [02-state-triple.md](02-state-triple.md) |
| 3 | Collision ledger | [03-collision-ledger.md](03-collision-ledger.md) |
| 4 | Toolkit bake-off (criteria) | [05-bake-off-checklist.md](05-bake-off-checklist.md) |

Artifact 1 inventory includes **Person card**, **Face card**, and **Dialog / confirmation** (among 17). Abbreviated seed formerly in `R3-BRIEF` §3 is **superseded**.

Artifact 4 criteria are canonical; **human bake-off measurements are DEFERRED TO LAST** (SEM-ARCH §I.5). No PASS until measured. Development continues.

## Related + rendered frames + decision

| Role | Path |
|---|---|
| Related — identity × processing cross-product | [02-interaction-cross-product.md](02-interaction-cross-product.md) |
| Frames — collision ledger (15 pairs) | [03-collision-frames.html](03-collision-frames.html) |
| Frames — state-triple grid (30 cards) | [04-state-triple-grid.html](04-state-triple-grid.html) |
| Hierarchy frames (TEST, not SPEC) | [06-hierarchy-frames.html](06-hierarchy-frames.html) |
| Shell decision packet (OPEN) | [07-shell-decision.md](07-shell-decision.md) |

Keep `02-interaction-cross-product.md` as the related identity×processing cross-product (not deleted; not renumbered as Artifact 2 — that slot is the state triple).

Master human-verify → wire playbook (all gated plan items): [`docs/HUMAN-VERIFY-THEN-WIRE.md`](../HUMAN-VERIFY-THEN-WIRE.md).

Shared visual tokens (CSS): inlined in each HTML file from the brief’s grammar (notch + stroke texture; processing = shape, not hue).

## How to review

1. Read **Artifact 1** (`01-state-matrix.md`) — any shipped chrome state missing from the matrix is a bug.
2. Read **Artifact 2** (`02-state-triple.md`) — three channels must not collapse; then open `04-state-triple-grid.html` (30 cards).
3. Read **Artifact 3** (`03-collision-ledger.md`) — then open `03-collision-frames.html`; hesitation on a pair fails. Footer must show pair count 15.
4. Use **related** `02-interaction-cross-product.md` so illegal identity×processing cells are not painted as identity conclusions.
5. Use **Artifact 4** + `semblon lab r3-bakeoff` / `tools/r3-bakeoff/` for real toolkit measurements on owner hardware — **DEFERRED TO LAST**; leave blanks until then.
6. Open **06** — click Library / People / Work nav; select an asset; confirm Inspector keeps evidence (machine) vs actions (human) split. Banner says TEST not SPEC.
7. Fill **07** only after a toolkit has six-of-six PASS; do not invent a winner from preference.

## Explicitly deferred (to **last** — SEM-ARCH §I.5)

- Artifact 4 / §8.5 Toolkit bake-off **measurements** against brief §6 (checklist + harness exist; no PASS claimed)
- §8.7 Naming a shell winner without measured bake-off
- APP-1 C.3 Windows live gate as a ship claim
- CONTRACTS product wire claim for durable **Ruled out** (scaffold may exist)
- Other owner-machine human verifies

Development of shell chrome / IA against this pack **must continue** meanwhile.
