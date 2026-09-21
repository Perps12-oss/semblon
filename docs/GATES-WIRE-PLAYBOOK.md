# Gates wire playbook — VERIFIED + WIRED (2026-09-21)

**Branch:** `cursor/gates-code-ahead-d6f3`  
**Policy:** Human VERIFY completed. Product **defaults ON**. Set `SEMBLON_GATE_*=0` to disable one surface.

```text
python -m semblon lab gates
```

---

## Wired surfaces

| Gate | CLI / product path | Disable |
|---|---|---|
| `r3_bakeoff` | `semblon lab r3-bakeoff [--out PATH]` (aggregates measure) | `SEMBLON_GATE_R3_BAKEOFF=0` |
| `r3_measure` | `semblon lab r3-measure [--out PATH]` | `SEMBLON_GATE_R3_MEASURE=0` |
| `ruled_out` | `semblon review ruled-out` + review-ui **Ruled out** | `SEMBLON_GATE_RULED_OUT=0` |
| `live_overlay` | `canvas` overlay styles via `overlay_boxes` | `SEMBLON_GATE_LIVE_OVERLAY=0` |
| `observer_honesty` | `semblon lab providers` probe-backed status | `SEMBLON_GATE_OBSERVER_HONESTY=0` |
| `hierarchy_frames` | `semblon lab r3-frames` | `SEMBLON_GATE_HIERARCHY_FRAMES=0` |
| `perf_workers_measure` | `semblon lab perf-workers --folder PATH` | `SEMBLON_GATE_PERF_WORKERS_MEASURE=0` |

Ingest `--workers` product default remains **1**.

---

## Master VERIFY checklist (completed)

1. [x] Human authorized: WIRE ALL GATES
2. [x] Ruled out CONTRACTS shape approved (no DDL)
3. [x] Observer honesty probes wired as default
4. [x] PERF workers measure CLI wired; default workers=1 unchanged
5. [x] Live overlay wired into canvas boxes
6. [x] R3 measure → bake-off aggregation wired
7. [x] R3 frames catalog CLI wired (§8.6 last; not shipping UI)
8. [x] Product paths connected; defaults ON

---

## Related parallel work — do not redo

| Branch / PR | Owns | This gates PR must not |
|---|---|---|
| `grok/r2-ipc-probe` | R2 JSON-lines JobEngine IPC probe | Rewrite `ipc_probe.py` |
| `grok/app1-c3-gate-pass` | APP-1 C.3 Windows live gate docs | Re-litigate pause/JobEngine |
| `cursor/sem-1.4-execution-bf81` (draft) | Historical PySide Home / live / benches | Revive `semblon/desktop` on `main` |
| `main` #54 | One GUI = tk Home + review-ui | Second product Home shell |

---

## Changelog

| Date | Note |
|---|---|
| 2026-09-21 | Initial playbook for code-ahead scaffolds |
| 2026-09-21 | VERIFY → wire all gates; defaults ON |
