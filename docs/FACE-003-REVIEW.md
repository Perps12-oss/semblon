# FACE-003 — S3 / 0.4 review evidence

**Gate:** FACE-002 → **FACE-003** → FACE-004 → FACE-005. This file is FACE-003 only.  
**eps=0.40 frozen.** No clustering-strategy work. Clusters are not people. FACE-004 identify is out of this gate.

Audit date: 2026-09-16. Dump store `semblon/s1-90-store` is local/gitignored.

## Contract (minimum)

From `docs/SEMBLON_MATURITY_BLUEPRINT.md` S3 / 0.4:

| Required | Meaning |
|---|---|
| CLI merge / split / name | Reviewer can correct groups and name after review |
| `decisions` rows | who/when/kind/run/pack; not silent retrain |
| Recluster does not clobber review | merge/split/ignore survive `cluster --run` |
| Cluster ≠ person until `name` | STRONG does not auto-enrol |
| Export lists decisions | HTML evidence, no embeddings |

Candidates **not** in this gate: merge suggestions, bridge-pair mining, exemplar ranking, undo (cheap-or-S5), identify (FACE-004).

## Code map (existing; no FACE-004)

| Surface | Path | Writes `decisions.kind` |
|---|---|---|
| `name --cluster` | `review.name_cluster` | `name` |
| `merge` / `review merge` | `review.merge_clusters` | `merge` |
| `split` / `review split` | `review.split_cluster` | `split` |
| `review ignore` | `review.ignore_subject` | `reject` + `policy_json` |
| `review note` | `review.note_subject` | `reject` + `policy_json` |
| recluster lock | `cluster._review_locks` / `_clear_unprotected_clusters` | does not delete merge/split/ignore |

Tests: `tests/test_review.py` — name, merge (not a person), merge survives recluster, split clears person on moved faces, ignore/note export, CLI merge/ignore.

`cluster_run` / `ingest` / `export` do not INSERT `persons`. `person_id` is stamped only in `review.name_*` (and FACE-005 `name --face`, which is enrol-an-unassigned, not identify).

## Dump evidence (run `20260913T153515Z-1e915abe`)

Read-only query 2026-09-16:

| kind | n |
|---|---|
| merge | 1 |
| name | 3 |
| identify | 5 (FACE-004 leakage on the dump; **not** this gate) |
| split / reject | 0 |

Merge: cluster `d56fdec9…` status **`merged`**, policy merged donor `9f6439db…` (4 faces), `created_at` 2026-09-13T22:11:58Z. `person_id` on that decision is **null**. Merge is not a person.

Name: explicit `name` on three clusters as P1/P2/P3 (2026-09-15). Not auto-enrol.

STRONG (`min_intra ≥ 0.50`) and unnamed:

| cluster | min_intra | named faces |
|---|---|---|
| `8940e0d2…` | 0.887 | 2 (P1, after explicit name) |
| `b5031fb7…` | 0.843 | 2 (P2, after explicit name) |
| `e1ecde7b…` | 0.789 | 2 (P3, after explicit name) |
| `cb4f10f0…` | 0.736 | **0** |
| `da5d738e…` | 0.714 | **0** |
| `d6e8906f…` | 0.687 | **0** |

Three STRONG clusters remain unnamed. STRONG is not a person.

## Minimum missing pieces (this gate)

1. **Git-recorded dump evidence** — this file. Store stays gitignored.  
2. **Unit guard:** `cluster_run` must not create `persons` (must-not auto-promote).  
3. **No code changes** to compare, eps, identify, ingest workers, or EP.

Not missing for 0.4: merge/split/name/ignore/note implementations; recluster lock; export DECISIONS.

## Reproduce

```text
py -3 -m pytest tests/test_review.py -q
```

Dump (local store only):

```text
SELECT kind, COUNT(*) FROM decisions GROUP BY 1;
SELECT cluster_id, status FROM clusters WHERE status='merged';
SELECT cluster_id, min_intra FROM clusters WHERE min_intra >= 0.50;
```
