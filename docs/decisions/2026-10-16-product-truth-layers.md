# Decision — four documentation layers

**Date:** 2026-10-16  
**Status:** current  
**Inspected revision:** `079d88ba` on `grok/ship-audit` (docs-only branch `grok/product-truth`)

## Decision

Semblon's intended product, the current build, and the remaining work are three different documents.

| Layer | File | Job |
|---|---|---|
| Product contract | `docs/PRODUCT.md` | What Semblon is. Stable until an explicit product decision amends it. |
| Current build | `docs/BUILD-STATUS.md` | Evidence-backed status of this checkout. Statuses move. The product statement does not. |
| Delivery roadmap | `docs/ROADMAP.md` | Ordered user outcomes that close the gap. It does not redefine the product or the architecture. |
| Decision history | `docs/decisions/` | Superseded statements and why they changed. |

`docs/ARCHITECTURE.md` stays the closed production architecture. `docs/SEM-ARCH-V1.4.md` stays engineering planned work. `docs/COMPLETION-MATRIX.md` stays the architecture closed/open ledger. `docs/CONTRACTS.md` stays schema and runtime authority. None of those is a second product definition.

## Why

The 2026-09-12 brief called Semblon a face-first CLI and was then amended in place for Tk Home, then for the PySide6 shell, including the line “Find is not a V1 capability.” The checkout at `079d88ba` already browses an archive, opens stills in Focus, searches by a colour histogram and by stored non-face embeddings, reviews people, and filters by time. Those capabilities are not yet one visual-memory journey. Rewriting the product sentence to match each increment hid the gap.

## What was kept

- Local-first, one user, files stay put, unknown is valid, cluster ≠ person.
- FaceKit is the only identity engine. Thresholds stay frozen.
- PySide6 → `Application` stays the production architecture.
- The 2026-09-12 brief is preserved verbatim in `docs/decisions/2026-09-12-v1-product-brief.md`.

## What this decision does not do

It does not retune identity, add schema, change runtime behaviour, or reopen the shell migration. It does not make optional OCR, CLIP, SigLIP, or SAM2 into default capabilities.
