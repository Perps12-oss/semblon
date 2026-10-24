# Lens confirmatory set

**Status:** protocol. No frozen file is in the tree. Precision stays refused until one is.  
**Harness:** `semblon/lens_eval.py`, `tools/eval_lens_retrieval.py`.  
**Synthetic ranks:** `docs/evidence/lens-retrieval-eval.json` (not this set).

This file is the build contract for the missing confirmatory Lens set. It does not retune RRF weights, floors, or S1. It does not add a schema column.

## What the synthetic run is

`--eval-set synthetic` scores five built-in swatch tuples and prints ranks only. Precision is null on purpose. The rank bar is: the best relevant hit sits above every hard negative.

The published fusion weights stay:

| Constant | Value | Where |
|---|---|---|
| RRF `k` | 60 | `semblon/rank_fusion.py` |
| RRF look / kind | 1.35 on the active mode, 0.65 on the other | `semblon/selection_retrieval.py` |
| RRF text | 1.15 with a word or text-priority, else 1.0 | same |
| RRF object | 1.0 | same |
| Rerank look | 0.45 in Same look, 0.18 in Same kind | `semblon/query_spec.py` `look_weight` |
| Rerank kind | 0.18 in Same look, 0.42 in Same kind | `kind_weight` |
| Rerank text / object / RRF | 0.22 / 0.15 / 0.30 | `feature_rerank` |
| Word bonus | 0.08 when a modifier hit has text | `feature_rerank` |

Do not edit those numbers from `docs/evidence/lens-retrieval-eval.json` or from the first confirmatory report. Each door is divided by its best value in the candidate pool before those weights run, so a cosine and an OCR flag are not averaged raw. That rescaling is the calibration the ranking decision already required. It is not a new weight.

## Kind door

Same-kind SigLIP runs only when `SEMBLON_SIGLIP_ONNX` probes `AVAILABLE` (`semblon/lens.py` `probe_siglip`). A missing pack is `SKIPPED`. The search still returns. Skipping is not a failed search and it does not write `embeddings.modality='face'`. The synthetic rank bar does not require this pack. A confirmatory manifest may record `look_items` from a machine where the pack was installed. Do not download weights to manufacture a pass.

## Frozen file

Path: `docs/evidence/lens-confirmatory.json`.  
Images sit beside that file. Paths in `image` are relative to the JSON file.  
Command:

```text
python tools/eval_lens_retrieval.py --eval-set confirmatory
```

The report defaults to `docs/evidence/lens-confirmatory-eval.json` and does not replace the synthetic report. Exit 0 only when every case places its best relevant hit above every hard negative. Precision is macro Precision@5: relevant hits inside the top 5, divided by 5, averaged across cases. A short list’s empty slots count as misses. Recall@5 uses the same hits over the case’s relevant count. Both stay null when the file is missing, unfrozen, or refused.

The loader refuses the file when any of these are true:

- `frozen` is not `true`
- `source` is not `owner-photographs`
- `eval_set` is not `confirmatory`
- a `case_id` or `media_id` is one of the synthetic ids (`brand-acme`, `acme-hit`, `acne-lookalike`, `shirt-plain`, `logo-hit`, and the other ids in `labelled_cases`)
- any of the five families is missing: `brand_text`, `same_kind`, `same_look`, `part_vs_whole`, `hard_neg_colour`
- an `image` path is missing
- `look_items` name a media id that is not in `media`

## Manifest shape

```json
{
  "frozen": true,
  "source": "owner-photographs",
  "eval_set": "confirmatory",
  "media": [
    {"media_id": "q1", "image": "q1.jpg", "text": "NORTHWIND", "objects": ["mug"]}
  ],
  "cases": [
    {
      "case_id": "owner-brand-1",
      "family": "brand_text",
      "query_media_id": "q1",
      "relevant": ["h1"],
      "hard_negatives": ["n1"],
      "observations": [{"kind": "text", "payload": {"text": "NORTHWIND", "role": "ocr"}}],
      "query_spec": {"mode": "look"},
      "look_items": [
        {"media_id": "n1", "score": 0.9, "match_norm": [0, 0, 1, 1]}
      ],
      "notes": "one sentence a person can check"
    }
  ]
}
```

`look_items` are the appearance list recorded from production `find_similar_crop` on that highlight (pack present or colour fallback, labelled as such in `notes`). They are not the synthetic swatch scores. `text` and `objects` are what ingest would have stored. The runner builds a temporary SQLite archive and does not write persons or `embeddings.modality='face'`.

Label rules:

- One person labels. Relevant means the same visual content the highlight asked for, in this archive.
- A hard negative is close in colour or outline and wrong in the way the family names (wrong brand, wrong kind, whole shirt instead of the mark).
- Unknown is allowed: leave a photo out rather than force it into relevant.
- Do not invent a product, landmark, or species name in `notes`.
- At least one case per family. More cases are allowed. Do not drop a family to raise precision.

## Acceptance

| Check | Pass |
|---|---|
| Loader | File accepted. Synthetic ids refused. |
| Rank bar | Every case: best relevant rank is above every hard negative. |
| Precision | Printed only on this set. Report the number. Do not call a failing rank bar a pass. |
| Identity | `identity_clean` is true. |
| Weights | The table above is unchanged in the same change that adds the file. |
| Appearance regression | `docs/evidence/photo-region-eval.json` is not reopened. |

## Learned ranker (not fit in this tree)

A GBDT may replace the hand sum only after a second frozen file exists: `docs/evidence/lens-rank-train.json`, same schema, `"role": "train"`, media ids disjoint from the confirmatory file and from the synthetic ids. Fit on the train file only. Write `docs/evidence/lens-ranker.json` with `trained_on`, `not_trained_on: ["synthetic", "lens-confirmatory.json"]`, and one weight per pool-fraction feature (visual, text, object, kind, rrf). `feature_rerank` keeps the hand formula unless `SEMBLON_LENS_RANKER` points at that JSON. Refuse to load a file whose `trained_on` is missing or whose ids intersect the synthetic cases. Acceptance: on the confirmatory file, the rank bar is not worse than the hand formula, and identity stays clean. Do not fit either file from the five synthetic swatches.

## What this protocol does not do

- It does not start ANN. See `docs/SHIP-GATES.md`.
- It does not put a VLM on the first grid.
- It does not require Grounding DINO. Parts stay NanoDet plus stored boxes (`docs/decisions/2026-10-19-lens-style-retrieval.md`).
