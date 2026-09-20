# Semblon

Local face intelligence. Working name `SEMBLON` (`SEM-blon`).

Personal, local-first Windows CLI. One user. No cloud. Files stay put.

**Current:** FACE-002 → FACE-003 → FACE-004 → FACE-005 **validation recorded** (`docs/FACE-GATES.md`). Incremental ingest + inbox 1.1 on `main`. Live scale: 90 stills; confirmatory 22 pairs (FAR 0/11, FRR 1/11 at frozen 0.60). No 10k claim. eps=0.40 frozen. Cluster ≠ person. Identify vs named persons only.

`cluster → review → person → name`. Never `cluster = person`.

S1 golden (repo record): `docs/S1-GOLDEN.md` — run `20260913T153515Z-1e915abe`, Windows ARM64, 90/85/78, 10/63/15, false merge 0, params frozen.

## First use (simple)

One-time setup in this folder (PowerShell or Command Prompt):

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
```

Equivalent by hand:

```text
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -U pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -e .
```

Then **double-click `semblon.cmd`** to open the **Semblon window**: add a folder, watch progress, and review/name groups in the same Mica shell. Review is the Unknown page of that window — not a second app. Face crops show in the grid (the same path+bbox seek used by `review.html`).

**Status:** the shipping UI is the PySide6 window (`semblon home` / `semblon-desktop`). tkinter Home/Review remains `--legacy` / `semblon review-ui`. The QML tree under `tools/s8_toolkit_spike/` is a research spike, not a product UI.

```text
semblon.cmd home
semblon.cmd home --legacy
semblon.cmd desktop
```

Or pass a path explicitly (no need to activate the venv, no need to copy a run id):

```text
semblon.cmd process "D:\photos\dump"
```

That will:

1. Ingest the folder into `%LOCALAPPDATA%\Semblon\store.sqlite` (or pass `--store`)
2. Cluster with the frozen S1 settings
3. Write `review.html` beside the store
4. Open the review page in your browser

Optional flags: `--store`, `--out`, `--no-open`, `--reprocess`.

`buffalo_l` downloads on first run into `%USERPROFILE%\.insightface\models\buffalo_l` (internal evaluation only).

## Install (power users)

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

`pip install -r requirements.txt` then `pip install -e .` is required. That pulls `insightface`, `onnxruntime`, `opencv-python-headless`, and `numpy`, and registers the `semblon` console script. Do not install those packages one failure at a time.

Equivalent module entry (same code path):

```text
python -m semblon --help
```

Do **not** run `python semblon\cli.py ...` from inside the package — that breaks imports (`No module named 'semblon'`).

Then use `semblon` directly (after activate), or keep using `semblon.cmd`.

## Commands

Power-user surface (still supported). Happy path above is `process`.

```text
semblon lab profile --image "D:\photos\face.jpg" --out "docs\runtime.md"

semblon process "D:\photos\dump"
semblon process "D:\photos\dump" --store "D:\semblon\store.sqlite" --out "D:\semblon\review.html"
semblon review-ui --store "D:\semblon\store.sqlite"
semblon review-ui --store "D:\semblon\store.sqlite" --run RUN_ID

semblon ingest "D:\photos\dump" --store "D:\semblon\store.sqlite"
semblon ingest "D:\photos\dump" --store "D:\semblon\store.sqlite" --reprocess

semblon live --store "D:\semblon\store.sqlite" --source 0 --seconds 5 --hz 1
semblon live --store "D:\semblon\store.sqlite" --source "rtsp://cam/stream" --seconds 0 --hz 5 --reembed-s 2 --retain-s 30

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

`live` runs a real loop: detect → track → selective embed → identify vs named persons. `--seconds 0` keeps running until cancel/SIGINT. `--reembed-s` controls per-track re-embed cadence; `--retain-s` applies rolling retention on that live media. `UNKNOWN` is valid and live faces are never auto-assigned `person_id`.

Quote Windows paths. Put a space between `--out` and the next argument — do not glue `docs\runtime.md` onto another path.

Double-click `review.html`. No server. Page order: counts → REVIEW REQUIRED → STRONG → UNASSIGNED → REJECTED → DECISIONS.

DBSCAN on `1 − cosine` for `status=ok` faces only (`eps=0.40`, `min_samples=2`) is a hypothesis. Use `review.html` to decide whether it survives — including whether different people stay separated on a mixed dump.

Corrections write `decisions` rows. Naming links `cluster_person` and stamps `faces.person_id`; the cluster id is never the person id.

## Docs (core)

| File | Role |
|---|---|
| `docs/PRODUCT.md` | frozen v1 (folder-first, face-first, local-first) |
| `docs/CONTRACTS.md` | schema / CLI / runtime |
| `docs/PRODUCTION-STATUS.md` | current production classification |
| `docs/PRODUCTION-AUDIT.md` | freeze audit vs plans, tests, and code |
| `docs/SEMBLON_MATURITY_BLUEPRINT.md` | long-term plan: structure + S0–S9 + absorb + measure |
| `docs/runtime.md` | FACE-000 output (fill on each machine) |
| `docs/licenses.md` | weights / licence record |

Architecture may anticipate the future. Implementation must earn it. FaceKit / InsightFace is the identity engine. Other spaces must not silently influence identity.

`pack_id` includes weight hashes. `buffalo_l` is a family name, not the compare key.

Weights are for internal evaluation only. See `docs/licenses.md`.
