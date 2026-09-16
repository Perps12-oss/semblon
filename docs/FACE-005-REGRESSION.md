# FACE-005 — regression / scale validation

**Gate:** FACE-002 → FACE-003 → FACE-004 → **FACE-005**. This file is that gate only.  
Not: workers, EP/GPU, watcher, daemon, OpenCV swap, 10k ingest, threshold retune.

Audit date: 2026-09-16. `pytest -q` on `main`: **66 passed**.

## What this gate is

Your sequence: **regression / scale validation** after identify 1.0.  
Blueprint S5 (incremental ingest + inbox) **already shipped** as 1.1 (`tests/test_face005.py`). That is **not** missing. Watcher / exemplars / daemon stay deferred.

## Regression coverage already on `main`

| Layer | Where | What it guards |
|---|---|---|
| Schema | `tests/test_schema.py` | WAL, sha256 unique, embedding length, eval pair order, pack compare |
| Cluster / export | `tests/test_cluster.py` | grouping, recluster replace, HTML evidence, no embeddings in export |
| Review 0.4 | `tests/test_review.py` | name/merge/split/ignore; merge survives recluster; cluster is not a person |
| Eval 1:1 | `tests/test_eval.py` | no FAR/FRR unless frozen confirmatory; remine ≠ confirmatory |
| Identify 1:N | `tests/test_identify.py` | vs persons; UNKNOWN; no auto-enrol |
| Incremental / inbox | `tests/test_face005.py` | hash skip; inbox buckets |
| Observatory | `tests/test_observatory.py` | snapshot readonly; review-count regression mark |
| Memory | `tests/test_memory.py` | time/place do not change `compare()` |

Dump confirmatory **re-score 2026-09-16** (same as FACE-002; not retuned):

`lab eval score --store semblon\s1-90-store --eval-set confirmatory` → FAR **0.0**, FRR **0.091**, status `measurable`.

S1 golden counts (`docs/S1-GOLDEN.md`): 90 jpg, 85 faces, 78 ok, 10 clusters, false merge 0. **Do not re-ingest to “confirm.”**

## Scale evidence that already exists

| Evidence | Size | Honest limit |
|---|---|---|
| S1 dump | **90** stills | The only live identity-path scale |
| Confirmatory pairs | **22** | Harness-measurable, not FRTE |
| PRODUCT “~10k first target” | **not run** | Underpowered for 10k. Do not invent it. |

Incremental skip is unit-tested (`test_media_skip_seen_across_runs`). A grown-folder re-ingest on this dump was **not** re-run for this gate (would not add 10k evidence).

## Minimum missing (demonstrated)

1. **No automated pin** that `DEFAULT_EPS=0.40`, `DEFAULT_MIN_SAMPLES=2`, metric `1-dot`, `STRONG_MIN_INTRA=0.50`, identify/eval threshold `0.60` still match `docs/S1-GOLDEN.md`.  
   `cluster.py` still said “Hypothesis — not frozen.” That comment is **false** after S1 PASS.
2. **Git-recorded regression/scale audit** — this file.

Not missing: 10k ingest, workers, EP, GPU, watcher, new identity rules.

## Reproduce

```text
py -3 -m pytest -q
py -3 -m pytest tests/test_frozen_params.py -q
```
