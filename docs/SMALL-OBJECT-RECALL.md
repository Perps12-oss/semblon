# Small-object recall

Measured 2026-10-25 on branch `grok/hybrid-discovery-latency`. This is a Linux x64 lab run. It is not Windows, not native ARM64, not an owner archive, and not the Kodak quarter-crop bench.

The question was: if a person selects a genuinely small detail, can hybrid find the other pictures of that same thing before the library has been fully detail-indexed?

On this corpus the answer is no for the smallest band, and only partly for the rest. The production grid and the production batch of 8 were not changed. Nothing here is a reason to shrink either one.

## How to reproduce

```text
export LD_LIBRARY_PATH=/tmp/egl6/usr/lib/x86_64-linux-gnu
export QT_QPA_PLATFORM=offscreen QT_QUICK_CONTROLS_STYLE=Basic
export PYTHONPATH=.
export SEMBLON_PERF=0
python tools/bench_small_object.py --work /tmp/small-object-bench --reps 3 \
  --out docs/evidence/small-object-recall.json
```

`LD_LIBRARY_PATH` is only so PySide can see libEGL in this sandbox. The bench itself calls the same ingest and search entry points as `tools/bench_hybrid.py`. Each prep and each search is a fresh process. Cold is the first pass over the queries. Warm is the same queries again on the same database.

Pixels and sqlite files stay in the work directory. Do not commit them. The raw report is [docs/evidence/small-object-recall.json](evidence/small-object-recall.json). It has no filesystem paths.

Corpus checks, with no model and no search: `tests/test_small_object_corpus.py`.

## What was held fixed

- Grid: 1 frame + 8 windows + up to 6 proposals. Not varied.
- Promotion batch: 8. Budget 12 s. One rescore at the end of the batch. The shell path.
- Balanced profile, unchanged: at most 8 results, colour floor 0.85, region floor 0.76, patch token floor 0.35, patch score floor 0.28, patch coverage floor 0.28.
- Pack: `dinov2-vits14`, SHA-256 `f22797eabf810a75e41de68d378541ebea372122b25c4ce3ef25ff618250c20a`, Apache-2.0. ONNX Runtime 1.30.0 with `CPUExecutionProvider` only (`region_encoder.py`). OpenCV 5.0.0. No new weights.

Recall@10 is recall inside that list of 8. Ranks 9 and 10 were never returned. A miss past the cap is a miss.

Recall and precision are set metrics. A query with 7 other pictures of the same sprite scores Recall@5 = (how many of those 7 are in the top 5) / 7. Precision@5 divides by 5, so a short or empty list is penalised. "Any hit" means at least one of the other pictures is in the list. The Kodak bench's Recall@5 was the second kind of number (the one copy was in the top 5). Do not compare the two figures.

## Machine

| | |
|---|---|
| OS | Linux 6.12.8+, glibc 2.36, x86_64, native, not emulated |
| CPU | Intel Xeon Platinum 8481C @ 2.70 GHz. The sandbox shows 2 logical CPUs. The host's physical core count is not visible. |
| RAM | 3930 MB visible |
| Python | 3.11.2 |

## Corpus

`tools/small_object_corpus.py`, generator `semblon-small-object-corpus-1`, seed `20261025`, checksum `9d904972f72999c2695bcf9e148220bf378836e5f172f6f169102bb46406307b`.

26 pictures, 960×640, drawn by the script. No external dataset, no owner photographs, no redistributed photographs. Three sprites (a medallion, a wide tag, a tall shard), each placed in several pictures. Relevance is that sprite's id. A second medallion is a category distractor. A tag that reuses the same stripe seed and colours but different dots is a visual distractor. Two pictures contain neither.

Size is the selection box's area as a percentage of the picture. Bands are labels, not search thresholds.

| Band | Queries | Box area | Examples |
|---|---|---|---|
| Very small, below 0.1% | 3 | 0.049–0.053% | 18×18, 27×12, 12×25, all clean and central |
| Small, 0.1–0.5% | 7 | 0.22–0.29% | clean centre, flush with the left edge, or ~42–45% occluded in clutter at JPEG quality 48 |
| Medium-small, 0.5–1% | 5 | 0.72–0.80% | clean, or rotated 32° with shear 0.22, dimmed, lightly occluded |
| Larger control, 1–3% | 5 | 1.5–1.8% | clean, or JPEG quality 38 with a reflection |

Dev / held-out (12 / 8) alternates within each band by query id. No threshold was tuned. The batch experiment below uses dev only, so the held-out numbers were not used to choose a batch.

This is a small synthetic set. DINOv2 was trained on photographs. These stripes are not a face, a logo, or a piece of jewellery. A miss here is evidence about this index. It is not a measurement of a real archive.

## Strategies

A, B, and C saw the same 26 files, the same 20 boxes, and the same relevance lists.

| | Preparation | What a search does |
|---|---|---|
| A Exhaustive | Full region ingest before any query | Search only. 26/26 searchable and detailed. 37,440 patch rows (1,440 per photo: frame plus 8 windows) and 110 region rows. |
| B On demand | Copy of the base library. No region index. | Colour-door promotion, then search. |
| C Hybrid | Region-lite: scene vector plus the frame grid only. 4,160 patch rows. 26/26 searchable, 0/26 detailed. | Search, then promote up to 8 photos that lack detail, then one rescore. |

Base ingest, before any region pass: 1.42 s, peak 197 MB, coverage searchable 0 / detailed 0 / total 26.

No strategy deleted or skipped a photo. Coverage after A and after C's cold pass is 26/26 detailed. Coverage after B is still searchable 0 / detailed 0.

## Primary result

Three repetitions. Recall did not move between them. Timings below are the median of the three repetition-medians, with the min and max of those medians. The per-query spread is much wider than the repetition spread and is called out underneath.

| | A Exhaustive | B On demand | C Hybrid |
|---|---|---|---|
| Prep | 27.64 s (26.67–27.71), peak 576 MB | 0 s, peak 100 MB | 3.27 s (3.17–3.39), peak 314 MB |
| Recall@5 cold, before this query's promotion | 0.271 | 0.000 | 0.229 |
| Recall@5 cold, after | 0.271 | 0.000 | 0.243 |
| Recall@5 warm | 0.271 | 0.000 | 0.271 |
| Recall@1 cold, after | 0.090 | 0.000 | 0.083 |
| Recall@10 cold, after (inside the cap of 8) | 0.360 | 0.000 | 0.317 |
| Precision@5 cold, after | 0.340 | 0.000 | 0.300 |
| Queries with any true picture in the top 5, cold | 16/20 | 0/20 | 15/20 |
| First result, median across queries | 67 ms (64–69) | 187 ms (185–190) | 78 ms (77–81) |
| Complete, median across queries | 67 ms | 187 ms | 102 ms (99–105) |
| Complete, warm median | 52 ms (51–55) | 171 ms (171–177) | 88 ms (87–89) |
| Photos promoted during the cold pass | 0 | 0 | 26 |
| Search peak RSS | 252 MB | 288 MB | 756–798 MB |

No query on any strategy reached Recall@5 of 1. The best single query was the edge-placed tag, 4 of 7 in the top 5 (0.571). Most queries have 7 relevant pictures, so the top 5 can score at most 0.714, and the top 8 can in principle hold all 7. They never did. Mean Recall@10 of 0.36 is about 2.5 of those 7, with empty slots left. The cap is not what makes this low.

Hybrid's median complete time of ~100 ms is the median of 20 queries, 16 of which did not promote. On repetition 0 the four that did promote took 7.74 s, 7.78 s, 8.58 s, and 2.39 s. Quoting 100 ms as hybrid's answer time would be wrong.

### What promotion actually changed

On the cold hybrid pass, promotion ran for 4 of 20 queries (8, 8, 8, then 2 photos). The other 16 promoted nothing: either the patch shortlist was empty, or earlier queries had already detailed the library. After those 26 promotions the library was 26/26 detailed, which is why the warm hybrid pass matches exhaustive on every query. A library larger than one batch would not finish inside this cold pass. This corpus cannot show that.

Phase sums for those 26 promotions, repetition 0 (the other two reps are within a few percent):

| decode | windows | proposals | tensor | ONNX | lane wait | embed | persist |
|---|---|---|---|---|---|---|---|
| 332 ms | 0.6 ms | 43 ms | 582 ms | 21,528 ms | 0 | 198 ms | 1,030 ms |

About 817–848 ms of ONNX per promoted photo (21.2–22.0 s across the three reps). That matches the Kodak note of ~870 ms per photo on this machine. The forward is the cost. Ranking was 24 passes and 2.6–3.1 s total, because only the four promoting queries ran a second pass. Query-crop ONNX time sits inside the 20–130 ms first-result figure and was not counted separately. This report does not invent a `session.run` tally.

The two queries whose top 5 gained a relevant picture were `q-p04-larger` (0.143 → 0.286, added `p02`, 7.8 s) and `q-p06-small` (0.286 → 0.429, added `p17`, 8.6 s). Both already had a true picture in the list before the rescore. No query went from "nothing relevant" to "something relevant" because of its own promotion. First useful result, where one exists, is the first result, not the rescore.

`detail_priority` counted `promoted` 26, `duplicates_avoided` 0, `already_done` 0, `failed` 0. Duplicate avoidance was not exercised. Do not read this run as a test of it.

### By size, cold, repetition 0

Recall@5 before this query's own promotion, then after. "Any" is whether the top 5 contained at least one true picture.

| Band | A Recall@5 (any) | C before → after (any) | B |
|---|---|---|---|
| Very small (3) | 0.000 (0/3) | 0.000 → 0.000 (0/3) | 0 |
| Small (7) | 0.265 (6/7) | 0.184 → 0.204 (5/7) | 0 |
| Medium-small (5) | 0.390 (5/5) | 0.362 → 0.362 (5/5) | 0 |
| Larger (5) | 0.324 (5/5) | 0.295 → 0.324 (5/5) | 0 |

Very small is a total miss for every strategy, including exhaustive and including a search after every photo has been detail-indexed. Hybrid does not promote those queries: the patch shortlist length is 0, so the batch of 8 never starts.

The small band is not one outcome:

- `q-p02-small`, medallion, 37×37, 0.223%, clean centre. Hybrid cold: `NO_RESULT`, shortlist 0, nothing promoted, 21 ms. Exhaustive, and hybrid after the library has been detailed: Recall@5 0.429 (3 of 7: `p03`, `p04`, `p13`). The detail index has the picture. Hybrid will not build that index for this query, because the frame grid produced nothing to promote.
- `q-p10-small`, shard, 27×61, 0.268%, clean centre. Exhaustive is also `NO_RESULT`. Detail does not recover this query. The same photo can appear later as a *result* (`q-p11` gains `p10` only after a batch of 8). Using the small crop as the *query* still matches nothing.
- `q-p06-small`, tag, 57×26. The frame grid already returns hits. Promotion adds one more top-5 hit and then matches exhaustive.

Held-out looks slightly better than dev (exhaustive Recall@5 0.304 vs 0.250, any-hit 7/8 vs 9/12) because two of the three very-small queries, and both of hybrid's empty small queries (`q-p02`, `q-p10`), sit in dev. That is the split, not a tuned model.

### By difficulty

These labels overlap. A query with several labels is counted in each. Figures are cold hybrid, repetition 0, Recall@5 after promotion, and whether any true picture was in the top 5. Exhaustive is in parentheses when it differs.

| Label | n | Recall@5 | Any in top 5 |
|---|---|---|---|
| Clean centre, no extra difficulty label | 4 | 0.143 (A 0.286) | 2/4 (A 3/4) |
| Wide | 8 | 0.286 | 7/8 |
| Tall | 4 | 0.250 | 2/4 |
| Edge | 2 | 0.357 | 2/2 |
| Occlusion | 2 | 0.143 | 2/2 |
| Clutter | 2 | 0.143 | 2/2 |
| Viewpoint | 2 | 0.286 | 2/2 |
| Lighting | 2 | 0.286 | 2/2 |
| Compression | 4 | 0.250 | 4/4 |
| Reflection | 2 | 0.357 | 2/2 |

Occlusion, clutter, and compression do not cause the empty result. They return a list whose first entries are the wrong sprite. Viewpoint and lighting still put a true picture in the top 5, at Recall@5 0.286 (about 2 of 7). The tall shard is the weak shape: the very-small and small tall queries are empty, so the tall group is 2/4.

Edge placement was not the failure. Both edge queries (`q-p13`, `q-p17`) are in the small band and both return hits. `q-p17` is the best query in the set (4 of 7).

## Background enrichment

A fresh lite index, then a full region ingest of all 26 photos, then a search with promotion off.

Enrichment took 24.04 s and peaked at 701 MB. Coverage went from searchable 26 / detailed 0 to 26/26 detailed. The search matches exhaustive on every query, including the misses: Recall@5 0.271, any-hit 16/20, very small still 0, `q-p10` still empty. Enrichment recovers `q-p02`. It does not recover an object the 15-piece index cannot see.

## On demand

All 20 queries returned `NO_RESULT` from `color-hist`, 0 items, 0 promotions, in about 180–190 ms (one cold query at ~530 ms). The colour door did not clear the balanced floor of 0.85, so promotion had no candidates. The pictures stayed unprepared and the result list was empty. They were not dropped out of a longer list. Coverage stayed searchable 0, detailed 0, complete false.

## Batch size, dev split only

Not the primary comparison. One pass each, 12 dev queries, production code with `DETAIL_PROMOTE_MAX` overridden inside that process only. Batch 0 skips promotion.

| Batch | Recall@5 before → after | Any-hit@5 after | Promoted | Complete median (max) | Queries that gained a top-5 hit |
|---|---|---|---|---|---|
| 0 | 0.087 → 0.087 | 4/12 | 0 | 21 ms (133) | 0 |
| 1 | 0.087 → 0.087 | 4/12 | 5 | 134 ms (1.16 s) | 0 |
| 4 | 0.159 → 0.163 | 6/12, down from 7/12 | 26 | 3.83 s (4.56 s) | 1, and one loss |
| 8 | 0.163 → 0.202 | 8/12 | 26 | 101 ms (8.17 s) | 2 |

Very small stayed at 0 for every batch. The shortlist is empty, so the batch size is never consulted.

Batch 4 made `q-p14-small` worse. Before the rescore, Recall@5 was 0.286. After promoting 4 photos the true medallion `p02` fell from the top 5 to rank 7, and the top 5 was `p18`, `p22`, `p21`, `p23`, `p08` (another sprite, two category distractors, a visual distractor, another sprite). Any-hit for the dev split dropped. The primary batch of 8, on the full 20-query run, left `q-p14` at one true hit in the top 5, the same as exhaustive. This one dev pass is not a tuning result. It is enough to refuse a smaller batch: 0 and 1 added no recall, and 4 both cost seconds and knocked a true picture out of the top 5.

Batch 8 is also what put the small shard photo `p10` into `q-p11`'s top 5 (Recall@5 0 → 0.667) and put `p02` into `q-p04`'s top 5. Shrinking the batch would have dropped those two gains on this pass. It would not have saved the very-small queries.

## Cancellation and duplicates

The cancel probe copied the hybrid database after the cold pass had already detailed all 26 photos. Cancelling the first query (`q-p01`, which is a genuine miss) returned `NO_RESULT` in 461 ms. The follow-up search was also `NO_RESULT`. That shows this miss was not turned into a false list. It does not show what cancellation does to a query that has results.

The in-promote cancel returned in 0.0 ms because there was nothing left to encode. It did not interrupt `session.run`. The Kodak measurement still stands: once a forward has started, cancel is not under 200 ms. This run does not replace that measurement, and it says nothing about Windows UI responsiveness.

## Where it fails

The JSON lists every query as a failure, because the filter is "Recall@5 is 1, and promotion did not matter, and no labelled distractor is ahead." None of the 20 queries meet that bar. The ones that matter:

1. `q-p01-very_small`, `q-p05-very_small`, `q-p09-very_small`. Boxes 18×18, 27×12, and 12×25 (under 0.06% of a 960×640 frame). Status `NO_RESULT`, shortlist 0, on exhaustive as well as hybrid, before and after enrichment. An 18 px object letterboxed into the 224 input is about 4 px, under one ViT-S/14 patch. Inside a 40% window it is still about 10 px. The frozen 15-piece index did not retrieve them. Promotion never started, so the batch size is irrelevant here.

2. `q-p02-small`. 37×37, clean, central, 0.223%. Hybrid's first search returns nothing and promotes nothing. Exhaustive returns 3 of 7 in the top 5. This is the case the product question is about: the whole-picture stage misses a small object that the detail stage can rank, and hybrid does not promote when that stage returns an empty shortlist. The user only gets the exhaustive answer after some other search, or a background pass, has detailed the library.

3. `q-p10-small`. 27×61, tall, 0.268%, clean. Empty on exhaustive too. The 15-piece grid is not sufficient for this query. Medium and larger crops of the same shard are found.

4. `q-p14-small`. Occluded ~45%, high clutter, JPEG 48. Any-hit is true and Recall@5 is 0.143 (1 of 7). Ranked `p18` (the other sprite, also occluded), `p22` and `p21` (category distractors, scores 0.67 and 0.66), then the true `p02` at 0.63. The first three results are not the object.

5. `q-p20-larger`. The control group is not clean either. Rank 1 is `p16`, a different sprite that shares the recompression and reflection treatment (score 0.67). Rank 2 is the near-copy tag `p24` (0.59). The first true tag is `p18` at rank 3. Recall@5 is 0.429, so a true picture is present, under the wrong objects.

6. `q-p18-small`. Same occlusion treatment on the tag. Rank 1 is `p14`, the occluded medallion. One true picture sits at rank 2. Shared damage outranks the instance.

No query retrieved every other picture of its sprite. Treating "larger" as solved because any-hit is 5/5 would hide Recall@5 of 0.324.

## Decision

- The first-stage index does not reliably retrieve genuinely small objects. Under 0.1% of the frame it retrieves none. Around 0.2–0.3% it depends on shape: the wide tag is found, the square medallion is not, the tall shard is not.
- Detailed promotion added a top-5 hit on 2 of 20 queries, both of which already had a hit, at about 8 s and ~21 s of ONNX across the promotions that also finished the rest of this small library. It added no recall on any very-small query, because those queries never entered promotion.
- After background enrichment, hybrid matches exhaustive and still misses every very-small query and `q-p10`. The weak band is the object size, not the decision to defer detail.
- Hybrid's latency advantage on this machine is preparation (3.3 s versus 28 s) and a first list in tens of milliseconds. The completed, rescored list is fast only when nothing is promoted. When something is promoted it costs several seconds and, here, usually does not change the top 5. On 26 photos the cold pass happens to finish the whole library, so the next search matches exhaustive. That will not be true of a real library, and this set is too small to measure the difference.
- The 15-piece grid is not adequate for the very-small band or for `q-p10`. It is what retrieves `q-p02`, which the frame grid misses. It was not reduced, and these numbers do not support reducing it.
- Batch size 8 stays. Batches 0 and 1 added no recall. Batch 4, on one dev pass, removed a true picture from a top 5. Very-small queries never reach the batch, so a smaller batch cannot help them and a larger one was not tested. Production is unchanged.
- On demand, with nothing indexed, found nothing. Colour did not open a door on these crops.
- The remaining trade-off is unchanged in kind and now visible in degree: whole-picture indexing is what makes a search possible at all, detail is what catches some small-but-not-tiny objects, and objects below about a tenth of one percent of the frame are invisible to the current grid whether or not the user waits.

## Not verified

- Windows, native ARM64, and owner photographs.
- Natural categories. Three generated sprites.
- A different grid, a different batch above 8, or a lower patch floor. None of those were tried, on purpose.
- In-flight ONNX cancellation on a query that has results.
- Duplicate avoidance under contention.
- A library big enough that a batch of 8 cannot detail it during one cold pass.
