# FACE-004 — 1.0 identify vs reviewed persons

**Gate:** FACE-002 → FACE-003 → **FACE-004** → FACE-005. This file is FACE-004 only.  
**eps=0.40 frozen.** Identify against **persons**, never clusters. Unknown is valid.  
FACE-005 (inbox, incremental ingest, `identify --run` with no probe, `name --face`) is **not** this gate. Concurrent workers / EP / GPU are deferred.

Audit date: 2026-09-16. Dump store `semblon/s1-90-store` is local/gitignored.

## Contract (minimum)

From `docs/SEMBLON_MATURITY_BLUEPRINT.md` S4 / 1.0 and v1 ship test:

| Required | Meaning |
|---|---|
| Gallery of **named persons** | `persons.status=active` + `faces.person_id` after `name` |
| 1:N identify | top1 / top2 / margin → ACCEPT \| UNKNOWN |
| Not 1:1 verification | `lab eval score` is FACE-002, not this gate |
| Not clusters | `decisions.cluster_id` null; `policy.against=persons` |
| Same pack | mixed pack skipped / refused |
| No auto-ID | identify does not stamp `faces.person_id` |
| New still | `identify --image` embeds a probe; does not enrol it |

S4 “gains” **not** in this minimum: person retire CLI, person merge/split, ANN/FAISS, webcam, trusted-exemplar ranking.

## Code already on `main`

| Surface | Path | This gate? |
|---|---|---|
| `identify --face` | `identify.identify_face` | **Yes** |
| `identify --image` | `identify.identify_image` | **Yes** |
| ACCEPT iff exactly one person ≥ 0.60 | `identify._decide` | **Yes** (threshold = frozen `1-eps`) |
| `decisions.kind=identify` + scores | `identify._write_decision` | **Yes** |
| Gallery = active persons, pack match | `identify._gallery` | **Yes** |
| `identify --run` (no probe) | `identify.identify_run` | **No — FACE-005** |
| `inbox` | `inbox.py` | **No — FACE-005** |
| `name --face` | `review.name_face` | **No — FACE-005** |

Tests: `tests/test_identify.py` — ACCEPT vs named person; UNKNOWN empty/ambiguous gallery; no auto-assign; missing image; CLI `--face`.

Threshold is `DEFAULT_THRESHOLD = 1 - 0.40 = 0.60`. Not retuned.

## Dump evidence (run `20260913T153515Z-1e915abe`)

Read-only 2026-09-16. Gallery: P1, P2, P3 (`active`), from FACE-003 `name`, not from identify.

| source | probe | decision | person | top1 | top2 | margin | cluster_id |
|---|---|---|---|---|---|---|---|
| face | `dfb57a1b…` | ACCEPT | P1 | 0.887 | 0.129 | 0.757 | null |
| face | `f302e7c7…` | ACCEPT | P2 | 0.843 | 0.123 | 0.720 | null |
| face | `631b7f77…` | ACCEPT | P3 | 0.789 | 0.005 | 0.784 | null |
| image | (no face_id; not enrolled) | ACCEPT | P1 | 1.000 | 0.129 | 0.871 | null |
| image | (no face_id; not enrolled) | ACCEPT | P3 | 1.000 | 0.005 | 0.995 | null |

`policy.against` is `persons` on all five. `faces.person_id` count is 6 — those stamps are from `name`, not from identify.

`--image` used the **existing S1 OpenCV package** (x64 `cv2` PE `0x8664`). That is not a new identity-path experiment. ARM64 OpenCV pyd was **not** consumed.

## Minimum missing pieces (this gate)

1. **Git-recorded dump evidence** — this file. Store stays gitignored.  
2. **No identify implementation changes** for FACE-004. `--face` / `--image` / ACCEPT / UNKNOWN / no auto-enrol already exist.  
3. Do not fold FACE-005 `identify_run` / inbox into this close.  
4. Do not add workers, EP selection, or GPU.

## Reproduce

```text
py -3 -m pytest tests/test_identify.py -q
```

Dump (local store only):

```text
SELECT display_name, status FROM persons;
SELECT face_id, person_id, score_top1, score_top2, margin, policy_json
  FROM decisions WHERE kind='identify';
```
