# Semblon

Local face intelligence. Working name `SEMBLON` (`SEM-blon`).

Personal, local-first Windows CLI. One user. No cloud. Files stay put.

**Current: FACE-005 regression/scale recorded (`docs/FACE-005-REGRESSION.md`).** Frozen params guarded in tests. 90-file dump is the live scale; 10k is not evidenced. eps=0.40 frozen.

`cluster → review → person → name`. Never `cluster = person`.

S1 golden (repo record): `docs/S1-GOLDEN.md` — run `20260913T153515Z-1e915abe`, Windows ARM64, 90/85/78, 10/63/15, false merge 0, params frozen.

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
semblon ingest "D:\photos\dump" --store "D:\semblon\store.sqlite" --reprocess

semblon cluster --run RUN_ID --store "D:\semblon\store.sqlite"
semblon export --run RUN_ID --store "D:\semblon\store.sqlite" --out "review.html"
semblon export --run RUN_ID --store "D:\semblon\store.sqlite" --views "D:\semblon\views"

semblon review --run RUN_ID --store "D:\semblon\store.sqlite" merge --clusters SURVIVOR DONOR
semblon review --run RUN_ID --store "D:\semblon\store.sqlite" split --cluster CLUSTER_ID --faces FACE_ID
semblon review --run RUN_ID --store "D:\semblon\store.sqlite" ignore --cluster CLUSTER_ID --as not_a_person
semblon review --run RUN_ID --store "D:\semblon\store.sqlite" ignore --face FACE_ID --as singleton
semblon review --run RUN_ID --store "D:\semblon\store.sqlite" note --cluster CLUSTER_ID --text "same person, two groups"

semblon lab observatory freeze --store "D:\semblon\store.sqlite" --run RUN_ID --stage S1 --notes "HUMAN REVIEW SENTENCE"
semblon lab observatory enter --stage S3 --store "D:\semblon\store.sqlite" --run RUN_ID

semblon lab eval create --store "D:\semblon\store.sqlite" --eval-set hard1 --kind confirmatory_hard --pack PACK_ID
semblon lab eval pair --store "D:\semblon\store.sqlite" --eval-set hard1 --faces FACE_A FACE_B --label different --stratum lookalike
semblon lab eval freeze --store "D:\semblon\store.sqlite" --eval-set hard1
semblon lab eval score --store "D:\semblon\store.sqlite" --eval-set confirmatory

semblon identify --face FACE_ID --run RUN_ID --store "D:\semblon\store.sqlite"
semblon identify --image "D:\photos\probe.jpg" --run RUN_ID --store "D:\semblon\store.sqlite"
semblon identify --run RUN_ID --store "D:\semblon\store.sqlite"

semblon inbox --run RUN_ID --store "D:\semblon\store.sqlite"
semblon name --face FACE_ID --as "P4" --run RUN_ID --store "D:\semblon\store.sqlite"

semblon stats --run RUN_ID --store "D:\semblon\store.sqlite"
semblon report --run RUN_ID --store "D:\semblon\store.sqlite" --out "report.md"

semblon memory history --person "Alice" --store "D:\semblon\store.sqlite"
semblon memory together --store "D:\semblon\store.sqlite"
semblon memory events --store "D:\semblon\store.sqlite"
```

Quote Windows paths. Put a space between `--out` and the next argument — do not glue `docs\runtime.md` onto another path.

Double-click `review.html`. No server. Page order: counts → REVIEW REQUIRED → STRONG → UNASSIGNED → REJECTED → DECISIONS.

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
