# Gates wire playbook — code ahead, wire after human VERIFY

**Branch intent:** `cursor/gates-code-ahead-d6f3`  
**Policy:** All gates in `semblon/gates.py` default **OFF**. Code may exist. **Human VERIFY authorizes wiring.** Enabling an env flag without completing the VERIFY checklist below is forbidden.

Read-only status anytime:

```text
python -m semblon lab gates
```

---

## Global rules (every gate)

1. Do **not** retune FaceKit / clustering / `eps` / identity thresholds.
2. Do **not** invent schema columns unless a named CONTRACTS slice is VERIFY-approved.
3. Do **not** revive PySide product Home on `main` (#54 removed it; spike stays under `tools/s8_toolkit_spike`).
4. Do **not** redo parallel work on other branches (see bottom).
5. After VERIFY: set the gate env var **only on the verification machine first**, then land a small wire PR that flips product paths behind `gates.is_enabled(...)`.

---

## Gate-by-gate checklist

### 1. `r3_bakeoff` — `SEMBLON_GATE_R3_BAKEOFF`

| | |
|---|---|
| **Default** | OFF |
| **Code exists** | `tools/r3_bakeoff/` (`criteria.py`, `harness.py`); `tests/test_r3_bakeoff.py` |
| **HUMAN VERIFY** | On a real Windows host (or documented toolkit sandbox): run the harness; confirm **no criterion emits PASS** without a real measurement; rejected list still includes Electron / Tauri / permanent Tk AppShell / CustomTkinter |
| **WIRE AFTER VERIFY** | Expose `semblon lab r3-bakeoff` (or keep tools CLI); store dated JSON under `artifacts/`; link from R3 decision packet. Do not choose WinUI/Qt from preference alone |

### 2. `r3_measure` — `SEMBLON_GATE_R3_MEASURE`

| | |
|---|---|
| **Default** | OFF |
| **Code exists** | `tools/r3_measure/` (`runners.py`, `refuse.py`); `tests/test_r3_measure.py` |
| **HUMAN VERIFY** | Each §6 criterion returns `verified=False` / `status=unverified` when not measured; `assert_no_fake_pass` rejects `pass=True` with `verified=False`; no silent simulate-PASS path |
| **WIRE AFTER VERIFY** | Feed runner outputs into bake-off aggregation; record host/toolkit/theme for each metric |

### 3. `ruled_out` — `SEMBLON_GATE_RULED_OUT`

| | |
|---|---|
| **Default** | OFF |
| **Code exists** | `docs/CONTRACTS.md` § “Ruled out (FLAGGED — not wired)”; `semblon/ruled_out.py`; `tests/test_ruled_out.py` |
| **HUMAN VERIFY** | Approve **PROPOSAL**: `decisions.kind='reject'` + `policy_json.action='ruled_out'` (vs Ignore `action='ignore'`); confirm **no DDL**; confirm display matrix mapping; decide whether candidate `person_id` is policy-only vs FK when person exists |
| **WIRE AFTER VERIFY** | Add `review ruled-out` CLI + review-ui action; keep Ignore separate; still no new columns unless VERIFY revises the proposal |

### 4. `live_overlay` — `SEMBLON_GATE_LIVE_OVERLAY`

| | |
|---|---|
| **Default** | OFF |
| **Code exists** | `semblon/overlay_scaffold.py`, `semblon/overlay_preview.py`; `tests/test_overlay_scaffold.py` |
| **HUMAN VERIFY** | Visual check of five display states + three-layer stroke at **smallest face size**; no auto `person_id`; cluster ≠ person; gate OFF leaves current canvas/live drawing unchanged |
| **WIRE AFTER VERIFY** | Call `apply_overlay_styles` from `canvas` / live preview only when gate ON; do not bake overlays into source media |

### 5. `observer_honesty` — `SEMBLON_GATE_OBSERVER_HONESTY`

| | |
|---|---|
| **Default** | OFF |
| **Code exists** | `semblon/observer_probes.py`; gated branch in `semblon/observers.optional_status`; `tests/test_observer_honesty.py` |
| **HUMAN VERIFY** | On target Windows: `python -m semblon lab providers` with gate ON — OCR/CLIP/pose `runnable` matches real capability (esp. MediaPipe `solutions.pose`); import-only must not claim runnable |
| **WIRE AFTER VERIFY** | Prefer probe-backed status as default for `lab providers`; keep unavailable extras as stubs, never identity voters |

### 6. `hierarchy_frames` — `SEMBLON_GATE_HIERARCHY_FRAMES`

| | |
|---|---|
| **Default** | OFF |
| **Code exists** | `docs/R3-FRAMES.md`; `tools/r3_frames/catalog.py`; `tests/test_r3_frames_catalog.py` |
| **HUMAN VERIFY** | Walk collision ledger pairs (hesitation = fail); walk state-triple grid; **only then** hierarchy frames (§8.6 last). Confirm Disabled≠Unknown≠Processing and Ruled out≠Ignored |
| **WIRE AFTER VERIFY** | Attach frame ids to R3 decision packet after APP-1 C.3 + R2; still not shipping UI |

### 7. `perf_workers_measure` — `SEMBLON_GATE_PERF_WORKERS_MEASURE`

| | |
|---|---|
| **Default** | OFF |
| **Code exists** | `semblon/perf_workers_harness.py`; `tools/perf_workers_measure.py`; `tests/test_perf_workers_harness.py` |
| **HUMAN VERIFY** | Run workers=1/2/4 hash-phase harness on **native** Windows host with a real folder; record JSON; **do not** change product `--workers` default from one run |
| **WIRE AFTER VERIFY** | Append results to `docs/PERF-WORKERS.md`; keep ingest default `workers=1` unless a later measurement-gated decision says otherwise |

---

## Master human action list (order)

Do these on the owner Windows machine / R3 review seat. Check each box only after evidence exists.

1. [ ] `python -m semblon lab gates` — confirm all `enabled: false` before any VERIFY session.
2. [ ] **Ruled out CONTRACTS proposal** — approve or revise `docs/CONTRACTS.md` FLAGGED section (no DDL).
3. [ ] **Observer honesty** — enable `SEMBLON_GATE_OBSERVER_HONESTY=1`; compare `lab providers` to installed OCR/CLIP/pose reality.
4. [ ] **PERF workers measure** — run `tools/perf_workers_measure.py` at 1/2/4; archive JSON; leave default=1.
5. [ ] **Live overlay visual** — enable `SEMBLON_GATE_LIVE_OVERLAY=1` in a preview harness; smallest-face notch check.
6. [ ] **R3 §6 measure + bake-off** — run measure runners then bake-off aggregator; zero fake PASS.
7. [ ] **R3 frames walk** — collision → triple → hierarchy (§8.6 last); record hesitations.
8. [ ] **Wire PRs** — one small PR per gate (or tightly related pair) that connects product paths only after the matching VERIFY above.
9. [ ] Re-run `lab gates` on a clean shell — product defaults still OFF until intentional env/config promotion.

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
| 2026-09-21 | Initial playbook for code-ahead scaffolds on gates branch |
