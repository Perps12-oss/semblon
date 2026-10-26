# Object-memory retrieval evaluation

This evaluation is a focused companion to the existing Lens evaluation. It must not replace Lens cases, tune Lens ranking thresholds, or overwrite Lens evidence.

## Run

```bash
python tools/eval_object_memory.py --manifest docs/evidence/object-memory-eval.json
```

Each frozen case must include `case_id`, `relevant_media_ids`, `hard_negative_media_ids`, and `ranked_media_ids` from the actual retrieval result. For a confirmatory real-photo case, also include `real_photo: true`, `query_image`, and `candidate_images` paths or stable dataset references. Use multiple physical objects, views, lighting, backgrounds, and partial occlusion. Keep all images local and do not commit private photos.

The report computes Recall@1/5/10, MRR, and hard-negative win rate. Synthetic fixtures validate the metric machinery only. The report explicitly refuses to call the result proof of real-photo recognition unless every case is marked real-photo and contains query/candidate image references.

## Interpretation

- Saved-name lookup measures name retrieval, not visual recognition.
- A real-photo visual baseline must record rankings returned by the production visual retrieval path for each selected crop and frozen candidate set.
- Do not tune the ranker against the same cases used for final reporting.
- Keep Lens evaluation and its evidence unchanged.
- Object labels must never write `faces.person_id` or face embeddings.
