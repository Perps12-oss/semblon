# PERF — provider / EP harness

**Measurement / listing only.** Does not retune identity. Does not claim GPU speedup.  
**Product default workers remain `1`.** FaceKit remains the only identity engine.

## What it does

`tools/perf_provider_harness.py` records:

- ORT provider list via `select_execution_provider`
- `product_prefer_gpu` honesty
- optional observer availability (`lab providers` shape)
- status lines identical to Home Settings EP block

`verified` stays **false** — listing is not a smoke-tested GPU claim. Azure ≠ GPU.

```text
python tools/perf_provider_harness.py --out "%LOCALAPPDATA%\Semblon\perf-provider.json"
python tools/perf_provider_harness.py --out "%LOCALAPPDATA%\Semblon\perf-provider.json" --execute
```

## Related

| Harness | Doc |
|---|---|
| Workers sweep (hash-only) | `docs/PERF-WORKERS-HARNESS.md` |
| Single-folder bench | `tools/bench_ingest.py` |
| ARM64 OpenCV blocker | `docs/PERF-P1-ARM64.md` (**still BLOCKED**) |

## Shakedown (2026-09-21, Linux cloud)

Dry-run + `--execute` listing ran successfully in this environment. ORT listed Azure + CPU only → product path CPU. **No speedup claimed.** Native ARM64 OpenCV ingest remains blocked on the owner Windows machine (`opencv_geometry500.dll` hang) — unchanged.
