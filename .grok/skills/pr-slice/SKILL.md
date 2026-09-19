---
name: pr-slice
description: One-slice git workflow for Semblon. Use at the start of any coding task.
---

# PR slice

1. Name the current `docs/SEM-ARCH.md` slice (or a KEEP leftover).
2. Touch only the files that slice needs.
3. Branch `grok/<slice>`.
4. Tests for that slice.
5. Stop before push. Draft PR only if asked.
6. Do not start a Cursor Cloud Agent.
7. Do not open a second writer on the same files.

Dump-gate still lives on the owner's Windows machine. Do not skip it from a laptop that is not that machine.
