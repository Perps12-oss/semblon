# P0 — Lifecycle semantics (actual schema)

Do not invent a second job-state system. Map what exists.

**Schema version:** 6  
**Baseline:** `af0758537fdd4f5240439ef163918db14defea9d`

## 1. `work_items.tier_done_mask` (still ingest resume)

Defined in `semblon/scan_tiers.py` and `store.MIGRATION_5` / DDL.

| Bit | Constant | Meaning |
|---|---|---|
| 1 | `TIER_LIBRARY` | Hash / orientation / thumb / media row |
| 2 | `TIER_OBSERVE` | Faces + non-region observers |
| 4 | `TIER_SEMANTIC` | DINOv2 region/scene tokens (whole-picture) |
| 8 | `TIER_DETAIL` | Fine region windows/crops |

There is **no** pending/running/completed column on `work_items`. Skip-if-done is “bit set”.

### Semantics

| Event | Effect |
|---|---|
| New path or mtime/size change | Mask treated as stale; hash may be required (`load_still`) |
| Successful tier completion | Corresponding bit OR’d via `save_work_item` |
| Same path, same mtime/size, bit already set | Tier skipped |
| Category backfill | **Does not** stamp `tier_done_mask` (by design; see module docstring) |
| Regions coverage via `category_coverage` | Also counted in `semantic_coverage()` when frame/detail done |

### Permitted transitions (mask model)

Bits only move **0 → 1** for a given generation of (path, mtime_ns, byte_size). A content/metadata change clears the effective mask back to 0 for that path. There is no “running” bit.

### Forbidden (product)

- Treating mask bits as person identity.  
- Marking observe/semantic complete without corresponding evidence (tests assert resume behaviour; full mutation coverage of every bit edge is partial — see transition table).

### Transition tests

| Edge | Test / status |
|---|---|
| Library bit set after hash/geometry | `tests/test_scan_tiers.py` — covered |
| Observe bit set after faces | covered |
| Semantic / detail inference for older stores | `infer_mask` tests — covered |
| mtime/size change resets work | covered |
| Category backfill does not raise observe mask | `tests/test_category_backfill.py` — covered |
| Mutation test removing each bit-edge assertion | **Unresolved** — not run as dedicated mutation suite |

## 2. `category_coverage` (Discover category backfill)

Schema constraint (`store.MIGRATION_6`):

```
state IN ('pending','running','completed','failed','unavailable','interrupted','skipped')
```

**There is no `unsupported` state.** Unsupported media is `state='skipped'` with `outcome='unsupported'`. Missing originals: `skipped` + `outcome='missing_original'`.

Categories: `people` | `objects` | `regions` | `words`.

### State meanings (as implemented)

| State | Meaning |
|---|---|
| `pending` | Work known / partial (regions may park as pending after frame-only) |
| `running` | Claimed by an in-flight backfill |
| `completed` | Durable success for this sha256 + provider_version (regions require frame+detail) |
| `failed` | Retryable failure (`outcome` distinguishes `read_failure` / `execution_failure`) |
| `unavailable` | Provider missing mid-run |
| `interrupted` | Was `running` when process stopped, or cancelled mid-item |
| `skipped` | Not eligible or not present (`unsupported`, `missing_original`, …) |

Freshness (`_fresh`): completed ∧ same sha256 ∧ same provider_version ∧ (regions: frame_done ∧ detail_done).

### Permitted transitions

```
(none) → running → completed
(none) → running → failed
(none) → running → interrupted
(none) → running → unavailable
(none) → skipped (unsupported / missing_original)
running → interrupted   (recover_interrupted on restart, or cancel)
interrupted|failed|pending → running → …
completed → (stale if sha/provider changes) → running → …
regions: running → pending (frame_only) → running → completed
```

### Forbidden (intended)

| Claim | Enforcement today |
|---|---|
| Missing original as `completed` | Skipped + missing_original — covered by tests |
| Interrupted left as `running` after reopen | `recover_interrupted` — covered |
| Mark completed without evidence for regions | Requires frame+detail — covered |
| `unsupported` as a state value | CHECK constraint rejects — schema-enforced |

### Transition tests

| Edge | Status |
|---|---|
| recover_interrupted | Covered (`test_category_backfill`, workflow smoke) |
| missing_original skipped | Covered |
| unsupported skipped | Covered |
| cancel → interrupted | Covered |
| provider unavailable | Covered |
| regions frame then detail commit | Covered |
| Exhaustive mutation of every edge | **Unresolved** — document gap; P6 strengthens |

## 3. `runs` process stages (ingest pipeline)

No new columns. Stage/job tokens live in `runs.timings_json` via `persist_run_stage` (`process.py`).

Job tokens used: `queued|running|paused|cancelling|completed|failed|cancelled`.  
Stage tokens: `ingest|cluster|export`.

Incomplete notes: `cancelled`, `interrupted`.

`inspect_run_stages` / `find_resumable_run` derive ingest/cluster/export done from finished_at, notes, media observations, cluster rows, timings — not from `work_items`.

In-process `JobEngine.state`: `idle|running|paused|cancelling` — **transient**, not durable.

## 4. Minimum schema change posture for later phases

P0 records: reuse `tier_done_mask` and `category_coverage.state`/`outcome`. Do not add a parallel lifecycle table. Any P6 change must be the smallest compatible extension (e.g. documenting outcomes, not inventing `unsupported` as a state without migration evidence).
