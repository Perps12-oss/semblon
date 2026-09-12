# Semblon

Local face intelligence. Working name `SEMBLON` (`SEM-blon`), provisional pending clearance.

**Current milestone: FACE-000** — prove InsightFace `buffalo_l` on Windows x64 native and Windows ARM64 (native, or fail + emulated).

Do not implement ingest, cluster, export, FAISS, or a review UI in this milestone.

## Docs (authority)

| File | Role |
|---|---|
| `docs/SEMBLON_IMPLEMENTATION_PLAN.md` | when to build |
| `docs/CONTRACTS.md` | schema / CLI / runtime |
| `docs/runtime.md` | FACE-000 output (fill on each machine) |
| `docs/CURSOR_INSTRUCTION.txt` | agent brief |

## FACE-000 on this machine

```text
python -m venv .venv
.venv\Scripts\activate
pip install -e .
semblon lab profile --image PATH\to\a.jpg --out docs/runtime.md
```

Record `arch` and `execution` (`native` vs `emulated`). Never label x64-on-ARM64 as native.

`pack_id` includes weight hashes. `buffalo_l` is a family name, not the compare key.

Weights are for internal evaluation only. See `docs/licenses.md`.
