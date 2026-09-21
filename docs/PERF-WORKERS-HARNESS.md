# PERF — workers measurement harness (current)

**Measurement only.** Does not retune identity (eps, min_samples, pack, det_size, CPU EP).  
**Product default remains `workers=1`.** This harness never authorizes changing that default and never claims a speedup by itself.

Historical multi-session ORT numbers (workers 2/4 slower than 1 on x64-emulated SKY) live in [`docs/PERF-WORKERS.md`](PERF-WORKERS.md). That design is **superseded**; re-measure hash-only workers with this harness before citing any throughput claim.

## What it does

`tools/perf_workers_harness.py` sweeps `workers=1,2,4` on a **user-supplied** stills folder:

- Fresh SQLite store per workers value
- Records `images_per_second`, `faces_per_second`, `peak_rss_mb` when available
- Asserts face-count equality (`files`, `faces`, `ok`, `low_quality`, `rejected`, `failed`) across the sweep
- Writes JSON with `verified: false` / `status: pending_human` until `--folder` + `--execute`

Single-workers throughput probes stay in `tools/bench_ingest.py` (one `--workers` value).

## Human must supply the folder

There is **no** corpus in the repo. Do not point this at the S1 golden dump to “beautify” results or retune clustering.

```text
set FOLDER=C:\path\to\your\stills
set OUT=%LOCALAPPDATA%\Semblon\perf-workers-harness\results.json

python tools/perf_workers_harness.py --out "%OUT%"
rem → verified=false, status=pending_human

python tools/perf_workers_harness.py --folder "%FOLDER%" --out "%OUT%" --execute
```

Optional: `--out-dir` for the per-workers stores (default: `<out.parent>\perf-workers-stores`).

## JSON shape (honest)

| Field | Meaning |
|---|---|
| `verified` | `true` only after a real `--execute` sweep |
| `status` | `pending_human` until run; then `measured` |
| `face_count_equal` | must be `true` for a valid comparison |
| `runs[]` | one entry per workers value with timings and counts |
| `note` | repeats: default stays 1; no speedup claim |

## Tests

`tests/test_perf_workers_harness.py` exercises the dry-run / `verified: false` path without a real photo corpus or InsightFace download.
