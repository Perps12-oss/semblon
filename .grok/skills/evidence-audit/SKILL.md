---
name: evidence-audit
description: Evidence-first review for Semblon. Use when auditing, reviewing a PR, or claiming PASS/FAIL.
---

# Evidence audit

Do not treat markdown as proof.

- Cite `path:line` or a command + exit code.
- Schema claims go to `docs/CONTRACTS.md` plus `tests/test_schema.py`.
- Cluster claims go to `tests/test_cluster.py` plus frozen params in `docs/S1-GOLDEN.md`.
- Review/decision claims go to `tests/test_review.py`.
- Eval/precision claims require `--eval-set confirmatory` and `tests/test_eval.py`.
- Observatory stage claims go to `tests/test_observatory.py` and freeze notes with a human sentence.
- If you did not run it, say so.
