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
| PR-11 | P0 | OPEN | Release | Get a GHA runner; do not claim the matrix is green | Runs `39365699632` / empty-workflow runs. Not re-triggered here |
| PR-12 | P0 | BLOCKED | Installer | Authenticode secrets and a WiX owner run | `msi-release.yml` dispatch-only; secrets absent |
| PR-13 | P0 | BLOCKED | Identity pack | Redistribution and Q-gate eval. Do not edit `PRODUCT.md` until that decision | `docs/decisions/2026-10-16-identity-engine-evaluation.md` |
| PR-14 | P1 | BLOCKED | Owner evidence | Run the owner pack workflow on a machine that has the pack | No PASS JSON in this environment |
| PR-15 | P2 | DEFERRED | Store | Do not implement encryption in this release | Decision 2026-10-16 |
| PR-16 | P1 | OPEN | Ingest | Same path, new bytes, second `media` row. Write a failing test before changing skip/insert | Read of `ingest.py` sha256 skip and insert. Not executed |
| PR-17 | P2 | OPEN | Erasure | Null or rebuild `clusters.centroid` when a person's faces are deleted | Read of `erasure.delete_person`. Not changed |
| PR-18 | P1 | OPEN | Optional CLIP | Confirm `pretrained="openai"` cannot run except as the documented human download | `observers.py` clip_embed. Not executed |
| PR-19 | P2 | OPEN | Text search | Do not map a missing score to 1.0 if a test shows it ranks junk first | `search.py` OCR take. Not changed |
| PR-20 | P0 hist. | NOT RE-TESTED | Windows shell | Re-run the 3.14 shell on Windows. Queued ingest completion remains the recorded fix | No Windows process in this audit |
| PR-21 | P2 | OBSERVED | Test host | Full pytest in this container aborts at finalization (exit 134) after a green summary. Do not treat that as a hidden pass or as a proven GitHub failure | `/tmp/pytest-final.txt`: 911 passed, 6 skipped, EXIT 134 |

`merge_clusters` person stamp: **kept**. Tests require one shared person on every survivor face and reject two different persons. Not a ledger item to "fix" without a product change.

Local suite note: the 911 figure is **before** PR-09 and PR-10. Those two tests were run after, with the review/memory/cluster slice, and passed. The full suite was not repeated after PR-09/PR-10 because the previous full process aborted in teardown and the new tests do not import Qt.
