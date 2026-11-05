# Semblon invariant hardening programme

Governing documentation for P0–P9. Scope is frozen. Do not add P10+.

| Document | Role |
|---|---|
| [PROGRAMME.md](PROGRAMME.md) | Programme contract, invariants I1–I6 + G1, phase gates |
| [P0-EVIDENCE-MAP.md](P0-EVIDENCE-MAP.md) | Reconciled writer/reader evidence (static + runtime + workflows) |
| [P0-LIFECYCLE.md](P0-LIFECYCLE.md) | Real `work_items` / `category_coverage` / run semantics |
| [P0-IDENTITY-COVERAGE.md](P0-IDENTITY-COVERAGE.md) | First I1 coverage manifest |
| [P0-GUI-STATE-TRANSLATION.md](P0-GUI-STATE-TRANSLATION.md) | G1 translation table and acceptance gaps |
| [P0-COMPLETION.md](P0-COMPLETION.md) | P0 completion record (**frozen** at `50722ef`) |
| [P0-COMPLETION-ADDENDUM.md](P0-COMPLETION-ADDENDUM.md) | Post-freeze sign-off / defects (append-only) |
| [P1-CONFIRMATION.md](P1-CONFIRMATION.md) | P1 read-back of frozen P0 |
| [P1-PLAN.md](P1-PLAN.md) | P1 plan + gate structure |
| [P1-REVIEW-DISPOSITION.md](P1-REVIEW-DISPOSITION.md) | S1–S5 decisions (B.H) |
| [P1-PERMIT-LIST.md](P1-PERMIT-LIST.md) | Exact path permit list for S5 |
| [P1-REJECTION-PATH-AUDIT.md](P1-REJECTION-PATH-AUDIT.md) | Eight rejection-path baseline audit |
| [P1-ERASURE-SCOPE.md](P1-ERASURE-SCOPE.md) | Day-one erasure registration for identify_evaluations |
| [P1-EVIDENCE.md](P1-EVIDENCE.md) | P1a change register + verification |
| [P1-COMPLETION.md](P1-COMPLETION.md) | P1a completion (P1b A11 deferred) |

**Authorised now:** P1a PROCEED (Gate B + S5 + C.G.T). **P1 not complete:** A15 GUI + P1b (B2 → A11/A12).

**Frozen:** `tools/p0/` — do not modify. Raw P0 traces: `artifacts/p0/*` (gitignored); durable pointer `artifacts/p0/MANIFEST.json`.
