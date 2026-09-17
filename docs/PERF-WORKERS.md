# PERF — bounded ingest workers (experimental)

**Not an S1 correctness change.** Thresholds, pack, det_size, CPU EP, and clustering unchanged.  
Default product path remains `workers=1`. Flag: `semblon ingest FOLDER --store PATH --workers N`.

## Harness

| Field | Value |
|---|---|
| folder | `E:\LIBRARY\Yandex.Disk\DCIMaw\me` |
| host | SKY, Windows 10.0.26200 |
| arch / execution | **x64 / emulated** |
| pack_id | `insightface/buffalo_l@2.0/adapter-1/sha256:20a9264f823c3c3c` |
| provider / device | `CPUExecutionProvider` / cpu |
| det_size | 640 |
| embed_batch | 1 |
| stores | `%LOCALAPPDATA%\Semblon\perf-workers\w{1,2,4}.sqlite` (fresh each run) |
| implementation | ThreadPoolExecutor; thread-local `FaceAnalysis`; **single SQLite writer** |

Historical P0 (context only): run `20260917T021045Z-48095f25`, ingest **1299.3 s**, same face counts.  
This harness re-ran workers=1; wall times differ (machine load / thermal / disk). **Speedups below use harness w=1**, not historical P0.

## Results

| workers | run_id | model_load_s | ingest_s | img/s | faces/s | files | faces | ok | lq | rej | failed | speedup vs harness w=1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `20260917T035938Z-9e6cbb26` | 5.2 | **3228.2** | 0.0685 | 0.2977 | 221 | 961 | 393 | 530 | 38 | 0 | 1.00× |
| 2 | `20260917T045426Z-f5fe764d` | 22.3 | **3754.8** | 0.0589 | 0.2559 | 221 | 961 | 393 | 530 | 38 | 0 | **0.86×** |
| 4 | `20260917T055704Z-06ae1405` | 22.3 | **4880.6** | 0.0453 | 0.1969 | 221 | 961 | 393 | 530 | 38 | 0 | **0.66×** |

Peak RSS: not recorded (no `psutil` dependency).

## Logical equivalence

Across w=1/2/4 in this harness:

- Identical counts: 221 files, 961 faces, 393 ok, 530 low_quality, 38 rejected, 0 failed, 0 skipped.
- Matches historical P0 face/status counts.
- No SQLite lock errors, crashes, or missing observations.

UUIDs differ by design (per-row `uuid4`).

## Conclusion

On **x64-emulated** SKY with CPU EP, bounded thread workers **did not** reduce ingest time; 2 and 4 workers were **slower** than 1 (contention under emulation / multi-session ORT).

Do **not** make `workers>1` the product default from this evidence.  
Revisit only after native ARM64 ingest is unblocked (`docs/PERF-P1-ARM64.md`), or on a native x64 host.

## Commands used

```text
set FOLDER=E:\LIBRARY\Yandex.Disk\DCIMaw\me
set PERF=%LOCALAPPDATA%\Semblon\perf-workers
python -m semblon ingest "%FOLDER%" --store "%PERF%\w1.sqlite" --workers 1
python -m semblon ingest "%FOLDER%" --store "%PERF%\w2.sqlite" --workers 2
python -m semblon ingest "%FOLDER%" --store "%PERF%\w4.sqlite" --workers 4
```
