# PERF — workers measurement harness (current)

**Measurement only.** Does not retune identity (eps, min_samples, pack, det_size, CPU EP).  
**Product default remains `workers=1`.** This harness never flips that default. A `default_gate.verdict=PASS` only means it is *safe to consider* a separate, explicit default-change PR after owner review.

Historical multi-session ORT design (workers 2/4 slower than 1 on x64-emulated SKY) is **superseded and retired**. Re-measure hash-only workers with this harness before citing any throughput claim.

## What workers do (product)

`semblon ingest FOLDER --store PATH --workers N` (CLI / `process --workers`):

| Phase | Parallel? |
|---|---|
| Still SHA-256 hash | Yes, bounded ThreadPool (`N`, cap 32) when `N>1` |
| Skip-before-embed | Main thread, single SQLite connection |
| Decode + FaceKit embed | **One** `FaceAnalysis` on the writer/main path |
| SQLite writes | **Single writer** (main thread only) |
| Video | Still sequential (hash on main; streamed frames) |

Cancel / JobEngine pause use the same cooperative gates as `workers=1`. While paused, in-flight hash futures may finish; decode/embed/SQLite do not advance until unpause. Cancel drains the hash pool (`shutdown(cancel_futures=True)`).

## When `workers>1` is appropriate

Use `workers>1` only when:

1. The folder is **large** and hash I/O is a measurable share of wall time (many/large stills on fast CPU/disk).
2. A harness sweep on **your** host shows `face_count_equal: true` and a real `speedup_vs_w1` you care about.
3. You accept experimental CLI opt-in — Home / JobEngine still run the product default (`1`).

Do **not** raise the product default from Linux CI, emulated x64, or a dry-run. Historical multi-session evidence was a *slowdown*.

## What the harness does

`tools/perf_workers_harness.py` sweeps `workers=1,2,4` on a **user-supplied** stills folder:

- Fresh SQLite store per workers value
- Records `images_per_second`, `faces_per_second`, `peak_rss_mb`, `speedup_vs_w1`
- Asserts face-count equality (`files`, `faces`, `ok`, `low_quality`, `rejected`, `failed`)
- Emits machine-readable `default_gate` (`PENDING` / `FAIL` / `PASS`)
- Writes JSON with `verified: false` / `status: pending_human` until `--folder` + `--execute`

Single-workers throughput probes stay in `tools/bench_ingest.py` (one `--workers` value).

### `default_gate` criteria (safe to *consider* default)

| Check | Requirement |
|---|---|
| `verified` | Real `--execute` sweep |
| `face_count_equal` | Counts match across w=1/2/4 |
| `failed` | All runs `failed == 0` |
| `speedup_vs_w1` | Best workers>1 `images_per_second` ratio ≥ **1.15** |

- **PASS** → `safe_to_consider_default: true`, `status: measured_default_gate_pass`. Product default **still 1** until a separate PR.
- **FAIL** → measurement may still be valid; default stays 1 (`status: measured_default_gate_fail`).
- **PENDING** → no folder / no execute.

Optional: `--require-default-gate` exits **2** unless verdict is PASS (CI guard; does not flip default).

## Human must supply the folder

There is **no** corpus in the repo. Do not point this at the S1 golden dump to “beautify” results or retune clustering.

### Owner Windows measure (authorize default>1 later)

```text
set FOLDER=C:\path\to\your\stills
set OUT=%LOCALAPPDATA%\Semblon\perf-workers-harness\results.json

python tools/perf_workers_harness.py --out "%OUT%"
rem → verified=false, status=pending_human, default_gate.verdict=PENDING

python tools/perf_workers_harness.py --folder "%FOLDER%" --out "%OUT%" --execute
rem Inspect default_gate.verdict, face_count_equal, runs[].speedup_vs_w1
rem Only if verdict=PASS on a native host: open a separate PR to raise CLI default.
```

Optional: `--out-dir` for the per-workers stores (default: `<out.parent>\perf-workers-stores`).  
Optional: `--require-default-gate` for a non-zero exit when the gate is not PASS.

Record arch / execution honestly (`native` vs `emulated`). Prefer native ARM64 or native x64.

## JSON shape (honest)

| Field | Meaning |
|---|---|
| `verified` | `true` only after a real `--execute` sweep |
| `status` | `pending_human` / `measured_default_gate_fail` / `measured_default_gate_pass` / `face_count_mismatch` |
| `face_count_equal` | must be `true` for a valid comparison |
| `runs[]` | timings, counts, `speedup_vs_w1` |
| `default_gate` | `{verdict, reasons, criteria, product_default_unchanged, ...}` |
| `safe_to_consider_default` | mirror of gate; **never** auto-changes product default |
| `product_default_workers` | always `1` from this tool |
| `note` | repeats: default stays 1 unless separate PR |

## Tests

- `tests/test_perf_workers_harness.py` — dry-run, gate PASS/FAIL, mocked sweep
- `tests/test_ingest_workers.py` — count parity, cancel, pause gate, hash failure, max workers, default=1

## Shakedown

Cloud/Linux dry-run: `python tools/perf_workers_harness.py --out …` → `verified=false`, `default_gate.verdict=PENDING`, exit 0.  
No folder corpus here — **no throughput or speedup claimed**; **product default stays `workers=1`**. ARM64 OpenCV remains **BLOCKED** (`docs/PERF-P1-ARM64.md`).
