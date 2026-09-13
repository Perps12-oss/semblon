# Semblon

Local face intelligence. Working name `SEMBLON` (`SEM-blon`).

Personal, local-first Windows CLI. One user. No cloud. Files stay put.

**Current: 0.4** — `name` / `merge` / `split` after `cluster` + `review.html`.

`cluster → review → person → name`. Never `cluster = person`.

**Stage-1 baseline (2026-09-13):** same-person folder (3 stills) → ingest → cluster → `review.html` passed on Windows ARM64 native. Next gate: multi-person separation (hard negatives). Do not retune `eps` from the same-person run alone.

## Install

Python **3.11+**, Windows x64 or ARM64 **native** (not x64 Python on ARM64).

Work from the **repository root** (`...\GITHUB\SEMBRON`), not from inside `semblon\`. Put `.venv` at the repo root — never inside the package folder.

```text
cd C:\Users\S8633\Documents\GITHUB\SEMBRON

py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -c "import sys; print(sys.executable)"
# expect: ...\SEMBRON\.venv\Scripts\python.exe

python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install -e .

semblon --help
```

`pip install -r requirements.txt` then `pip install -e .` is required. That pulls `insightface`, `onnxruntime`, `opencv-python-headless`, and `numpy`, and registers the `semblon` console script. Do not discover those packages one failure at a time.

Equivalent module entry (same code path):

```text
python -m semblon --help
```

Do **not** run `python semblon\cli.py ...` from inside the package — that breaks imports (`No module named 'semblon'`).

`buffalo_l` downloads on first `lab profile` / `ingest` into `%USERPROFILE%\.insightface\models\buffalo_l` (internal evaluation only).

## Commands

```text
semblon lab profile --image "D:\photos\face.jpg" --out "docs\runtime.md"

semblon ingest "D:\photos\dump" --store "D:\semblon\store.sqlite"

semblon cluster --run RUN_ID --store "D:\semblon\store.sqlite"
semblon export --run RUN_ID --store "D:\semblon\store.sqlite" --out "review.html"

semblon name --cluster CLUSTER_ID --as "Alice" --run RUN_ID --store "D:\semblon\store.sqlite"
semblon merge --clusters SURVIVOR DONOR... --run RUN_ID --store "D:\semblon\store.sqlite"
semblon split --cluster CLUSTER_ID --faces FACE_ID... --run RUN_ID --store "D:\semblon\store.sqlite"

semblon lab observatory freeze --store "D:\semblon\store.sqlite" --run RUN_ID --stage S1
semblon lab observatory enter --stage S3 --store "D:\semblon\store.sqlite" --run RUN_ID
```

Quote Windows paths. Put a space between `--out` and the next argument — do not glue `docs\runtime.md` onto another path.

Double-click `review.html`. No server. Page order: counts → REVIEW REQUIRED → STRONG → UNASSIGNED → REJECTED.

DBSCAN on `1 − cosine` for `status=ok` faces only (`eps=0.40`, `min_samples=2`) is a hypothesis. Use `review.html` to decide whether it survives — including whether different people stay separated on a mixed dump.

Corrections write `decisions` rows. Naming links `cluster_person` and stamps `faces.person_id`; the cluster id is never the person id.

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
