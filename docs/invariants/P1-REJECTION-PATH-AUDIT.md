# P1 — Eight rejection-path audit

**Baseline (pre-fix):** `af0758537fdd4f5240439ef163918db14defea9d`  
**Post-fix detectors:** `tests/test_p1_i1_baseline_detectors.py`  
**Implementation:** `semblon/compare.py` + `require_finite_threshold` / `validate_identity_embedding`

| ID | Rejection path | Status | Evidence |
|---|---|---|---|
| R1 | pack_id mismatch | **fail_closed** | `test_r1_pack_mismatch_already_fail_closed` |
| R2 | dimension mismatch | **fail_closed** | `test_r2_dimension_mismatch_already_fail_closed` |
| R3 | embedding length ≠ 4×dim | **fail_closed** | `test_r3_length_mismatch_already_fail_closed` |
| R4 | NaN in payload | **fail_closed** (P1 A1) | `test_r4_nan_must_not_produce_score` |
| R5 | Inf in payload | **fail_closed** (P1 A1) | `test_r5_inf_must_not_produce_score` |
| R6 | L2 norm not ~1 | **fail_closed** (P1 A1) | `test_r6_non_unit_l2_must_not_produce_score` |
| R7 | non-finite threshold | **fail_closed** (P1 A2) | `test_r7_non_finite_threshold_must_not_accept` |
| R8 | empty / unknown pack | **fail_closed** (P1 A1) | `test_r8_empty_pack_must_fail_closed` |

Same-dimension different-pack remains R1.
