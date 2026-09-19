# Performance baseline P0 (folder timing)

**Not an S1 correctness gate.** Do not retune eps / min_samples / thresholds from this run.  
S1 golden remains `20260913T153515Z-1e915abe`. Emulation cost vs native ARM64 is a **hypothesis** until P1 measures it.

## Baseline P0

| Field | Value |
|---|---|
| run_id | `20260917T021045Z-48095f25` |
| host | SKY, Windows 10.0.26200 |
| arch / execution | **x64 / emulated** |
| pack_id | `insightface/buffalo_l@2.0/adapter-1/sha256:20a9264f823c3c3c` |
| folder | `E:\LIBRARY\Yandex.Disk\DCIMaw\me` |
| files | 221 stills (incremental, 0 skipped, 0 failed) |
| faces | 961 → 393 ok / 530 low_quality / 38 rejected |
| cluster | frozen `dbscan eps=0.40 min_samples=2 metric=1-dot` → 36 clusters (7 REVIEW, 29 STRONG), 88 UNASSIGNED, 0 decisions |
| device | CPU (`CPUExecutionProvider`) |
| workers / embed_batch | 1 / 1 |
| det_size | 640 |
| model_load_s | ~4.8 |
| **ingest_s** | **1299.3** (~5.9 s/file) |

Hot path (known): SHA-256 → `imread` → `imread` again → `FaceAnalysis.get()` (SCRFD + landmarks + buffalo_l + ArcFace) → per-file SQLite commit.

## Track

```text
P0  This baseline (documented) — no algorithm change
P1  Native ARM64 measure — BLOCKED 2026-09-17 (docs/PERF-P1-ARM64.md)
P2+ EP → workers → batching → drop duplicate imread → SQLite commits
    (each alone; workers only after P1 unblocks)
```

Standing pointers: `docs/SEM-ARCH.md` (planned work), `docs/runtime.md`, `docs/PERF-P1-ARM64.md`.  
Product parallel: review `7225de9d` (130 faces, min_intra 0.129) via `review-ui` — not a clustering retune.
