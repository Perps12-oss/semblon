# Semblon

Local face intelligence. Working name `SEMBLON` (`SEM-blon`).

Personal, local-first Windows CLI. One user. No cloud. Files stay put.

**Current: S1 PASS — closed (2026-09-13).** Next planned gate: FACE-002 confirmatory hard negatives. Do not retune clustering. Do not start architecture expansion.

`cluster → review → person → name`. Never `cluster = person`.

Authoritative dump `20260913T153515Z-1e915abe` (Win ARM64 native, 90 `.jpg`): 85 faces, 78 ok, 10 clusters, 63 clustered, 15 eligible unassigned. No observed false merge. Clusters remain clusters. Export evidence `unassigned` matches the cluster CLI (OK faces with no assignment only).

## Install

Python **3.11+**, Windows x64 or ARM64 **native** (not x64 Python on ARM64).

```text
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
pip install -e .
```

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

semblon lab observatory freeze --store "D:\semblon\store.sqlite" --run RUN_ID --stage S1 --notes "HUMAN REVIEW SENTENCE"
semblon lab observatory enter --stage S3 --store "D:\semblon\store.sqlite" --run RUN_ID
```

Quote Windows paths. Put a space between `--out` and the next argument — do not glue `docs\runtime.md` onto another path.

Double-click `review.html`. No server. Page order: counts → REVIEW REQUIRED → STRONG → UNASSIGNED → REJECTED.

DBSCAN on `1 − cosine` for `status=ok` faces only (`eps=0.40`, `min_samples=2`) is a hypothesis. Use `review.html` to decide whether it survives.

Corrections write `decisions` rows. Naming links `cluster_person` and stamps `faces.person_id`; the cluster id is never the person id.

## Docs (core)

| File | Role |
|---|---|
| `docs/PRODUCT.md` | frozen v1 (folder-first, face-first, local-first) |
| `docs/CONTRACTS.md` | schema / CLI / runtime |
| `docs/SEMBLON_MATURITY_BLUEPRINT.md` | long-term plan: structure + S0–S9 + absorb + measure |
| `docs/runtime.md` | FACE-000 output (fill on each machine) |
| `docs/licenses.md` | weights / licence record |

Architecture may anticipate the future. Implementation must earn it. FaceKit / InsightFace is the identity engine. Other spaces must not silently influence identity.

`pack_id` includes weight hashes. `buffalo_l` is a family name, not the compare key.

Weights are for internal evaluation only. See `docs/licenses.md`.
