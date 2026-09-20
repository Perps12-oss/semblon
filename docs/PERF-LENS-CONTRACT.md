# PERF+LENS A/B contract (no-regression / no-semantic-drift)

This contract gates every Stream A/B implementation cycle.

Semblon's top invariant is correctness with identity separation.  
Throughput work that changes semantics is rejected.

## Required parity checks

1. Same fixed corpus before/after.
2. Same media accepted/skipped/failed counts.
3. Same face detection counts.
4. Same embeddings within documented tolerance.
5. Same clustering output under frozen parameters.
6. Same identify decisions.
7. Same UNKNOWN identify decisions.
8. Same non-face modality/pack/dimension isolation.
9. No non-face observer may create or modify identity.
10. No automatic person assignment may appear as side effect.
11. `observation != track != person` remains enforced.
12. Runtime evidence must record workers, provider, fallback, timings, and execution architecture.

## Numeric tolerances

- Embedding tolerance is explicit (`embedding_tol` in snapshot generation).
- Decision-score tolerance is explicit (`score_tol` in snapshot comparison).

Embeddings are compared via quantized hashes under `embedding_tol`; any change
beyond tolerance is treated as semantic drift.

## Tooling

- Snapshot generation: `python -m semblon lab contract snapshot --store STORE --run RUN --out SNAPSHOT.json`
- Comparison: `python -m semblon lab contract compare --before BEFORE.json --after AFTER.json`

Exit codes for compare:

- `0`: contract pass
- `3`: contract fail (semantic drift)
- `2`: usage/data error

## Throughput reporting contract

Performance reports must include:

- `images/sec`
- `faces/sec`
- `seconds/image`
- `seconds/face`
- scaling efficiency (`T1 / Tw`) across controlled worker/provider sweeps

Worker counts are empirical (`w=1,2,4,...`) up to a sensible machine ceiling.
Never assume higher worker count implies better performance.
