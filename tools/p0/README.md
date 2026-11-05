# P0 evidence tools

Observation only. No identity enforcement. No schema writes beyond what exercised code already does.

| Script | Purpose |
|---|---|
| `sql_static_inventory.py` | Source 2 — AST inventory of connect/execute sites |
| `sql_runtime_trace.py` | Source 1 — authorizer + trace + execute shapes |
| `pytest_plugin.py` | Opt-in via `SEMBLON_P0_SQL_TRACE=1` |
| `workflow_smoke.py` | Source 3 — pack-free store lifecycle smoke |
| `reconcile.py` | Compare static vs runtime summaries |

See `docs/invariants/`.
