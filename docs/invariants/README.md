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
| [P1-ERASURE-SCOPE.md](P1-ERASURE-SCOPE.md) | Draft erasure registration for identify_evaluations |
| [P1-CONFIRMATION.md](P1-CONFIRMATION.md) | P1 read-back of frozen P0 |
| [P1-PLAN.md](P1-PLAN.md) | P1 plan + gate structure |
| [P1-REVIEW-DISPOSITION.md](P1-REVIEW-DISPOSITION.md) | S1–S5 decisions (B.H) |
| [P1-PERMIT-LIST.md](P1-PERMIT-LIST.md) | Exact path permit list for S5 |
| [P1-REJECTION-PATH-AUDIT.md](P1-REJECTION-PATH-AUDIT.md) | Eight rejection-path baseline audit |

**Authorised now:** baseline I1 detectors + docs (S1 narrow exception). **Not authorised:** P1 behaviour fix / schema until Gate B.

**Frozen:** `tools/p0/` — do not modify. Raw P0 traces: `artifacts/p0/*` (gitignored); durable pointer `artifacts/p0/MANIFEST.json`.
