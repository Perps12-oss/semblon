# P1 — Eight rejection-path audit (baseline evidence)

**Baseline:** `af0758537fdd4f5240439ef163918db14defea9d`  
**Freeze commit:** `50722efa8a9522867e37db352c30bc5d786ec1e2`  
**Detector tests:** `tests/test_p1_i1_baseline_detectors.py`  
**Rule:** Code-reading is not enough. Each path has a test. Expected-red paths use `xfail(strict=True)`.

| ID | Rejection path | Baseline result | Evidence |
|---|---|---|---|
| R1 | pack_id mismatch | **fail_closed** | `test_r1_pack_mismatch_already_fail_closed` |
| R2 | dimension mismatch | **fail_closed** | `test_r2_dimension_mismatch_already_fail_closed` |
| R3 | embedding length ≠ 4×dim | **fail_closed** | `test_r3_length_mismatch_already_fail_closed` |
| R4 | NaN in payload | **baseline_defect** (P0 #6) | `test_r4_nan_must_not_produce_score` (xfail); `test_issue6_nan_score_is_currently_non_finite_acceptance_risk` |
| R5 | Inf in payload | **baseline_defect** (P0 #6) | `test_r5_inf_must_not_produce_score` (xfail) |
| R6 | L2 norm not enforced | **baseline_defect** | `test_r6_non_unit_l2_must_not_produce_score` (xfail) |
| R7 | non-finite threshold | **baseline_defect** | `test_r7_non_finite_threshold_must_not_accept` (xfail) |
| R8 | empty / unknown pack | **baseline_defect** | `test_r8_empty_pack_must_fail_closed` (xfail) |

Same-dimension different-pack is covered by R1 (`test_same_dim_different_pack_already_fail_closed`).

**A1 implication:** Fixes must target R4–R8. Do not “fix” R1–R3 as if they were open. When a defect is closed, remove its strict xfail and keep the assertion.
