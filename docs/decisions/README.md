# Decision history

Material product and architecture decisions, plus superseded statements. The current product contract is `docs/PRODUCT.md`. This folder does not replace it.

| Date | Record | Status |
|---|---|---|
| 2026-10-16 | [Python support policy](2026-10-16-python-support-policy.md) | Current |
| 2026-10-16 | [Identity engine redistribution](2026-10-16-identity-engine-redistribution.md) | Current |
| 2026-10-16 | [Store encryption deferred](2026-10-16-store-encryption-deferred.md) | Current |
| 2026-10-16 | [Screen-capture UI deferred](2026-10-16-screen-capture-deferred.md) | Current |
| 2026-10-16 | [Four documentation layers](2026-10-16-product-truth-layers.md) | Current |
| 2026-09-12 | [v1 product brief](2026-09-12-v1-product-brief.md) | Historical. Identity rules kept. Face-first CLI and “Find is not a V1 capability” are not the contract. |
| 2026-10-05 | `docs/ARCHITECTURE.md` | Current for the production shell. Migration complete. |
| 2026-10-02 | `docs/SHELL-IA.md` | Historical for production chrome. Still the Model D lock for the retired Tk Home client. |
| 2026-10-15 | `docs/TIMELINE-VIEW.md` | Current description of production shell chrome (left nav, calendar, field). |
| 2026-09-21 | `docs/SEM-ARCH-V1.4.md` | Current engineering planned work. Not the product contract. |

## Historical audits and proposals

These remain in the tree as records. They are not current product definitions and they are not a queue.

| Document | Why it is historical |
|---|---|
| `docs/PRODUCTION-STATUS.md` | 2026-09-22 capability list plus a 2026-10-05 shell correction. Product status moved to `docs/BUILD-STATUS.md`. |
| `docs/COMPLETION-MATRIX.md` | Architecture closed/open ledger. Product capability status moved to `docs/BUILD-STATUS.md`. |
| `docs/UI-EXPOSURE-MAP.md` | September 2026 Tk inventory, with later banners. Current exposure is the 2026-10-16 section at the top. |
| `docs/GUI-MIGRATION-PLAN.md` | Tk migration steps. Superseded 2026-10-05. |
| `docs/GUI-TARGET-ARCHITECTURE.md` | Pre-migration target. Superseded by `docs/ARCHITECTURE.md`. |
| `docs/GUI-ARCHITECTURE-FORENSIC-AUDIT.md` | Forensic notes from the Tk period. |
| `docs/GUI-CAPABILITY-EXPOSURE-MATRIX.md` | Exposure matrix from the Tk period. |
| `docs/FRONTEND-BLUEPRINT-V3-ANNOTATED.md` | Annotated blueprint. Not a status board. |
| `docs/frontend-redesign-phase-report.md` | Phase report. |
| `docs/GUI-REGISTRY-IMPLEMENTATION.md` | Registry implementation notes tied to the old Home client. |
| `docs/r3-artifacts/` | Bake-off record. Ship gates in SEM-ARCH §I.5 are closed. |
| `docs/S8-TOOLKIT.md`, `docs/S8-REVIEW-UI.md` | Research and retired review UI. Not the production shell. |
