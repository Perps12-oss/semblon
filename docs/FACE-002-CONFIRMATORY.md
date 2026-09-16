# FACE-002 confirmatory validation (local labels)

**Date scored:** 2026-09-16  
**Command (exit 0):**

```text
py -3 -c "from semblon.cli import main; raise SystemExit(main(['lab','eval','score','--store', r'semblon\s1-90-store', '--eval-set', 'confirmatory']))"
```

Store `semblon/s1-90-store` is **local-only** (gitignored). Face embeddings and dump photos are not in git. Pairs below are face_ids on frozen run `20260913T153515Z-1e915abe`.

Do not retune `eps=0.40`. Do not re-ingest this dump. Clusters are not people.

## Distinctions (do not collapse)

| Thing | What it is |
|---|---|
| Confirmatory labels | Human same/different on this dump. Frozen set `s1-confirmatory`. |
| Mined negatives | `s1-mined` / `mined_discovery`. Hypothesis only. Remine does not refresh confirmatory. |
| Clustering | DBSCAN `eps=0.40`, `1-dot`. A grouping, not identity. |
| Person identity | Only after `name`. Not used as eval labels here. |

A pair can be **same person and split across clusters**. That is a false split, not a license to retune.

## Harness floor vs this dump

`semblon/eval.py`: FAR/FRR only if frozen `confirmatory_hard`, ≥10 same, ≥10 different, ≥1 hard-negative with similarity ≥ `hard_near` 0.50. Threshold = `1 - eps` = **0.60** (not retuned).

This set **meets the harness floor** → status `measurable`. It is still a **22-pair family dump**. That is not NIST FRTE. Do not market a single accuracy number.

## Score (2026-09-16)

| Field | Value |
|---|---|
| eval_set_id | `s1-confirmatory` |
| kind | `confirmatory_hard` |
| frozen | 1 |
| pack_id | `insightface/buffalo_l@2.0/adapter-1/sha256:20a9264f823c3c3c` |
| pairs / scored / skipped | 22 / 22 / 0 |
| same / different | 11 / 11 |
| hard_negatives | 1 |
| cluster_impurity | 0 (no `different` pair shares a cluster) |
| false_accept | 0 |
| false_reject | 1 |
| **FAR** | **0.0** (0/11) |
| **FRR / FNMR** | **0.0909** (1/11) |

## False reject (same person, reject)

| face_a | face_b | sim | clusters |
|---|---|---|---|
| `14bd9310527b44a6952b80149e2f777f` | `6a7830d646a147a99ebd16cebdc12adf` | 0.519 | different clusters |

Label **same** (visual: same child, two stills). Similarity 0.519 < 0.60 → reject. This is a **false split** at the frozen operating point. `s1-mined` still lists this pair as hypothesized `different` — that mined row is **not** confirmatory.

## Hard-negative (different people, sim ≥ 0.50)

| face_a | face_b | sim | decision | stratum |
|---|---|---|---|---|
| `492090470989423997411ef21ba8708d` | `db2485850aaf4454b3d2b8d844626b33` | 0.589 | reject | lookalike |

Two different adult women. Correct reject. FAR stays 0.

## Confirmatory pairs

Same (11). Stratum `same_condition`. Visual same-person; **not** “same because clustered.”

| face_a | face_b | sim | decision |
|---|---|---|---|
| 14bd9310… | 6a7830d6… | 0.519 | reject |
| 276eb055… | 3b5a454c… | 0.763 | accept |
| 276eb055… | 6668d24e… | 0.781 | accept |
| 3b5a454c… | 6668d24e… | 0.765 | accept |
| 3b5a454c… | b9173989… | 0.838 | accept |
| 49209047… | bd6afa73… | 0.687 | accept |
| 57a18926… | d2d27e79… | 0.736 | accept |
| 631b7f77… | 8909ac2d… | 0.789 | accept |
| 6668d24e… | b9173989… | 0.714 | accept |
| 7a5f9395… | dfb57a1b… | 0.887 | accept |
| db248585… | f302e7c7… | 0.843 | accept |

Different (11). Adult vs child, or adult man vs woman. Not cluster membership.

| face_a | face_b | sim | stratum | decision |
|---|---|---|---|---|
| 49209047… | 6668d24e… | −0.075 | adult_cross | reject |
| 49209047… | 7a5f9395… | 0.095 | adult_child | reject |
| 49209047… | d2d27e79… | 0.023 | adult_child | reject |
| 49209047… | db248585… | 0.589 | lookalike | reject |
| 6668d24e… | 7a5f9395… | −0.051 | adult_child | reject |
| 6668d24e… | d2d27e79… | 0.014 | adult_child | reject |
| 7a5f9395… | 8909ac2d… | −0.041 | adult_child | reject |
| 7a5f9395… | db248585… | 0.096 | adult_child | reject |
| 8909ac2d… | d2d27e79… | 0.050 | adult_child | reject |
| 8909ac2d… | db248585… | −0.006 | adult_cross | reject |
| d2d27e79… | db248585… | 0.102 | adult_child | reject |

Full 32-char ids are in the store `eval_pairs` table and in the CLI JSON.

## What this does not close

- Generalization beyond this dump
- x64 native FACE-000
- Switching Semblon onto the ARM64 OpenCV pyd
- Concurrent ingest / EP / GPU work (deferred)

S1 params unchanged: `eps=0.40`, `min_samples=2`, `1-dot`, `STRONG_MIN_INTRA=0.50`.
