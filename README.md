# Semblon

Local face intelligence. Working name `SEMBLON` (`SEM-blon`).

Personal, local-first Windows CLI. One user. No cloud. Files stay put.

**Current: 0.3** — `ingest` on `main`; `cluster` + static `review.html`.

`cluster → review → person → name`. Never `cluster = person`.

## Commands

```text
semblon lab profile --image PATH\to\a.jpg --out docs/runtime.md

semblon ingest D:\photos\dump --store D:\semblon\store.sqlite

semblon cluster --run RUN_ID --store D:\semblon\store.sqlite
semblon export --run RUN_ID --store D:\semblon\store.sqlite --out review.html
```

Double-click `review.html`. No server. Page order: counts → REVIEW REQUIRED → STRONG → UNASSIGNED → REJECTED.

DBSCAN on `1 − cosine` for `status=ok` faces only (`eps=0.40`, `min_samples=2`) is a hypothesis. Rework it from the page.

0.4 (`name` / `merge` / `split`) is next.

## Docs (authority)

| File | Role |
|---|---|
| `docs/SEMBLON_MATURITY_BLUEPRINT.md` | capability North Star (S0–S9) |
| `docs/SEMBLON_CAPABILITY_DISCOVERY_BLUEPRINT.md` | scavenging / value / absorb process |
| `docs/SEMBLON_ENGINEERING_OBSERVATORY.md` | measurement spine (not a gate) |
| `docs/PRODUCT.md` | frozen v1 product |
| `docs/CONTRACTS.md` | schema / CLI / runtime |
| `docs/runtime.md` | FACE-000 output (fill on each machine) |

`pack_id` includes weight hashes. `buffalo_l` is a family name, not the compare key.

Weights are for internal evaluation only. See `docs/licenses.md`.
