# P1 confirmation note — frozen P0 read-back

**Date:** 2026-11-05  
**Author of this note:** Cursor agent (plan author)  
**Code written:** none  
**`tools/p0/` modified:** no  

## Frozen references

| Item | Value |
|---|---|
| Evidence baseline (tree P0 was reconciled against) | `af0758537fdd4f5240439ef163918db14defea9d` |
| Reconciliation / freeze commit on branch | `50722efa8a9522867e37db352c30bc5d786ec1e2` (`docs: freeze P0 invariant evidence map and observation tools`) |
| Branch | `grok/p0-invariant-evidence` (pushed) |
| Schema version | 6 |
| P0 sign-off | **PENDING** — inherited; not reopened; not marked complete |

Artifacts read before planning:

- `docs/invariants/P0-EVIDENCE-MAP.md`
- `docs/invariants/P0-LIFECYCLE.md`
- `docs/invariants/P0-IDENTITY-COVERAGE.md`
- `docs/invariants/P0-COMPLETION.md`
- `docs/invariants/PROGRAMME.md`
- `artifacts/p0/sql_static_inventory.json` (local regenerate; **not in git** — see findings)

## Four inherited obligations (carried into P1)

1. **36 dynamic SQL sites** — when a P1 change touches a subsystem that contains one, move that site to a bounded disposition (or name it unbounded-partial for the P1 signer). Static count confirmed from local inventory: 36 sites across 16 files (top: `category_backfill.py` 9, `visual/persist.py` 5, `store.py` 4).
2. **Privacy** — any new instrumentation: parameter shape only; no OCR text, paths, or names; verify with a trace-inspection test.
3. **Coverage accounting** — any new SQL site must appear in the next static inventory with a runtime attribution method that passes the P0 self-test.
4. **Match method** — keep the P0 attribution join (callsite identity through the traced connection wrapper). Do not invent a second coverage method.

## Subsystems guarded by triggered deferrals

| Deferral | Guarded subsystem | Blocks until closed |
|---|---|---|
| `hashes` / `scans` runtime reconciliation | `semblon/dedupe_sidecar.py` (and any migration of those writers/readers) | Any dedupe change |
| `reembed.py` / `live.py` / cluster suite under SQL trace | `semblon/reembed.py`, `semblon/live.py`, `semblon/cluster.py` SQL/lifecycle | Any change to those modules’ SQL or lifecycle behaviour |

## Off-limits (confirmed understood)

- `tools/p0/` — no modify, improve, or “fix”
- Regenerating P0 evidence against a changed baseline
- Schema migration, threshold retune, clustering behaviour change, opportunistic GUI redesign, unrelated cleanup
- Unrelated working-tree files: `.rescue-compare/`, `docs/ARCHITECTURE-AUDIT-2026-10-28.md`
- Explicit non-P1: ErasureIntent (P2), `_decode_bgr` (P3), `_clear_unnamed_faces` (P2), `incompatible` (P4), provenance/`legacy_unverified` (P5), kill-9 (P8)

## Findings (ambiguities — not filled by inference)

1. **P0 gate vs this handoff.** `P0-COMPLETION.md` and `PROGRAMME.md` say do not start P1 implementation until the incident defender signs. This handoff authorises **plan-only** work under PENDING sign-off. Implementation remains blocked until the P0 signer completes the gate **or** an explicit exception is recorded by that signer.
2. **Named P0 signer is not in the freeze record.** Defect — recorded in `P0-COMPLETION.md` gap #12. P1 signer later named **B.H** in review disposition; spot-checker and adjudicator still unset (S2 blocked for merge).  
3. **`artifacts/p0/*.json` gitignored at freeze.** Corrected with committed `artifacts/p0/MANIFEST.json` (path, sha256, timestamp). Raw blobs remain local/regenerable.  
4. **Schema-migration conflict.** Resolved by S3: narrow additive `identify_evaluations` exception, Gate-B-gated; erasure registration day one; `decisions.kind` untouched.  
5. **“Acceptance path” vs cluster.** Unchanged: harden `compare()` without editing `cluster.py` SQL/lifecycle unless B2 closed and signer expands scope.  
6. **No formal P0 “deferral register” table** at freeze; reconstituted in `P1-PLAN.md` / `P1-REVIEW-DISPOSITION.md`.  
7. **Review header “P0 SIGNED” vs S1 body.** Ambiguity recorded; S1 body controls — P0 remains unsigned in this disposition.

## Stop line

Plan reviewed — see `P1-REVIEW-DISPOSITION.md`. No `tools/p0/` edits. No behaviour/schema until Gate B. Detector evidence permitted under S1.
