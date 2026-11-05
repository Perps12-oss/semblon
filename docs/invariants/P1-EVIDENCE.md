# P1 evidence

**Freeze:** `50722ef` · **Schema:** 7 · **`tools/p0/`:** unmodified  

## Focused suite (P1 complete)

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_identify.py tests/test_p1_i1_baseline_detectors.py tests/test_schema.py `
  tests/test_reembed.py tests/test_people_identity_g1.py tests/test_face005.py `
  tests/test_critique_p0.py tests/test_live.py
```

**57 passed.**

| Check | Result |
|---|---|
| NaN/Inf/dim/length/pack/empty-pack/threshold | Covered |
| Empty gallery `empty_gallery` vs empty pack | Covered |
| Gallery load validation | Covered |
| UNKNOWN + reason survives reopen | Covered |
| No auto person assignment | Covered |
| Re-embed clears evaluations / rejects bad L2 | Covered |
| Inbox Named / Not sure / Not checked; ACCEPT≠KNOWN | Covered |
| Live suite | Covered (with P1a contract) |
| Ingest persist guard | Source-confirmed |
| Threshold / `decisions.kind` / `tools/p0/` | Unchanged |

### Source-inspected only (not separate tests)

`zero_vector`, `wrong_dtype_shape`, `missing_pack`, `invalid_dimension` on shared validators.

### `identify_evaluations` fields

probe · pack · dim · run + gallery_size · outcome + reason · policy_version + threshold · created_at

## Map

| ID | Status |
|---|---|
| A1–A9, A13, A16 | Done |
| A11, A12, A15/G1 | Done |
| A17 / P2 | Not started |
