# Production readiness ledger — 2026-10-22

Action list for the audit in `docs/audits/PRODUCTION-READINESS-AUDIT.md`. This is not a second roadmap. Programme status stays in `docs/BUILD-STATUS.md`. Architecture ledger stays in `docs/COMPLETION-MATRIX.md`.

**Verdict: NOT READY FOR RELEASE.**

| ID | Sev | Status | Subsystem | Action | Verification |
|---|---|---|---|---|---|
| PR-01 | P0 | REPAIRED, NOT VERIFIED ON GHA | CI | Restored `.github/workflows/ci.yml` | Diff against the parent of `f0c42e6`. A runner must go green |
| PR-02 | P1 | REPAIRED | Video open | Stop patching `os.name` in the portable test; prefix helper is pure | `test_windows_video_open_tries_extended_path`, `test_extended_win_prefix_drive_unc_and_passthrough` |
| PR-03 | P1 | REPAIRED | Store | `connect_readonly` URI-encodes and sets `query_only` | `test_readonly_open_keeps_hash_and_percent_in_the_path` |
| PR-04 | P1 | REPAIRED | Shell crops | xyxy board box → xywh before the image provider | `test_face_corners_become_a_crop_size` |
| PR-05 | P1 | REPAIRED | Region parts | NanoDet corners converted to width/height | `test_live_part_box_uses_detector_corners` |
| PR-06 | P1 | REPAIRED | QML contract | Zero-arg `findSimilarFaces`; `faceCount` on people rows | Shell tests in the 911-pass summary; call sites in `Shell.qml` |
| PR-07 | P1 | REPAIRED | Search index | No pickle load; uncovered query returns `None` so SQLite is used | Search/index tests in the full summary |
| PR-08 | P1 | REPAIRED | Dependencies | `pillow==13.0.0`; lock matches one 3.12 `uv pip compile` | `pip-audit --local` exit 0 |
| PR-09 | P1 | REPAIRED | Identity lock | `cluster._review_locks` includes `policy.face_ids` | `test_name_faces_locks_every_named_face` |
| PR-10 | P1 | REPAIRED | Identity attach | `name_faces` refuses a different `attach_to_person_id` | `test_name_faces_refuses_conflicting_attach` |
| PR-11 | P0 | OPEN | Release | Get a GHA runner; do not claim the matrix is green | Push run `39814855887` created the matrix and stayed queued with no runner and 0 steps. Historical run `39365699632` died in ~3s with `runner_id` 0 |
| PR-12 | P0 | BLOCKED | Installer | Authenticode secrets and a WiX owner run | `msi-release.yml` dispatch-only; secrets absent |
| PR-13 | P0 | BLOCKED | Identity pack | Redistribution and Q-gate eval. Do not edit `PRODUCT.md` until that decision | `docs/decisions/2026-10-16-identity-engine-evaluation.md` |
| PR-14 | P1 | BLOCKED | Owner evidence | Run the owner pack workflow on a machine that has the pack | No PASS JSON in this environment |
| PR-15 | P2 | DEFERRED | Store | Do not implement encryption in this release | Decision 2026-10-16 |
| PR-16 | P1 | REPAIRED | Ingest | `claim_new_media` clears the old path when a new digest is inserted there | `test_replaced_bytes_do_not_keep_the_old_path` |
| PR-17 | P2 | REPAIRED | Erasure | Empty cluster drops `centroid`. Remaining faces rebuild it from `faces.embedding` | `test_delete_person_drops_centroid_of_their_cluster` |
| PR-18 | P1 | OPEN | Optional CLIP | Confirm `pretrained="openai"` cannot run except as the documented human download | `observers.py` clip_embed. Not executed |
| PR-19 | P2 | REPAIRED | Text search | A stored score of 0 stays 0. Only a missing score becomes 1.0 | `test_text_search_keeps_a_zero_score` |
| PR-20 | P0 hist. | NOT RE-TESTED | Windows shell | Re-run the 3.14 shell on Windows. Queued ingest completion remains the recorded fix | No Windows process in this audit |
| PR-21 | P2 | OBSERVED | Test host | Full pytest in this container aborts at finalization (exit 134) after a green summary. Do not treat that as a hidden pass or as a proven GitHub failure | `/tmp/pytest-final.txt`: 911 passed, 6 skipped, EXIT 134 |

`merge_clusters` person stamp: **kept**. Tests require one shared person on every survivor face and reject two different persons. Not a ledger item to "fix" without a product change.

Continuation on 2026-10-22 re-ran the repair slice (`70 passed`) and the new path, centroid, and score tests inside `38 passed`, both exit 0. The full suite was not repeated. GitHub Actions was not green at the start of this continuation.
