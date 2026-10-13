# Audit fix matrix

Published audit of 2026-10-11, fixed on branch `grok/photo-video-scope`. Not committed. Not pushed.

Identity stays FaceKit only. `pack_id` is still `insightface/buffalo_l@{version}/adapter-{n}/sha256:{16-hex}`. Clustering stays `eps=0.40`, `min_samples=2`, metric `1-dot`, `STRONG_MIN_INTRA=0.50`. No schema columns were added. Old runs with a null `ort_version` and no `opencv_version` in `runtime_json` still resume.

The suite command is `.\.venv\Scripts\python.exe -m pytest -q --tb=line`. It finished with exit 0: 1008 passed, 3 skipped, 2 warnings, 543.19s. The warnings are the existing open_clip QuickGELU note in two tests. They are not failures.

## Correctness

| Finding | Fix | Regression | Result |
|---|---|---|---|
| Blocker. `merge_clusters` deleted the donor and `decisions.cluster_id` has no `ON DELETE`, so a named donor raised `IntegrityError`. | Donor stays. `status='merged'`, `face_count=0`, centroid and `min_intra` cleared. `cluster_person` for the donor is still deleted. Merged shells are left out of live cluster counts. | `tests/test_review.py::test_merge_reviewed_same_person_keeps_decision_rows` | In the suite run. |
| Major. A still whose embed raised was committed, then `media_skip_reason` returned `same_run` or `seen` forever. | `_drop_failed_still` deletes the faces and the observation, and deletes the media row when this call created it and nothing else remains. Same drop on cancel-after-insert. | `tests/test_audit_regressions.py::test_embed_failure_is_retried`, `test_cancel_before_embed_drops_observation` | Passed in an earlier targeted run after face boxes were raised to 100 px (`CLUSTER_MIN_SIDE` is 80). Re-checked by the suite. |
| Major. A failed video frame still set `sampling_complete`. `IntegrityError` skipped a frame that had no faces. | `frames_failed` counts those frames. Complete is set only when every sampled frame embedded. An existing observation is embedded only when it has no faces. | `test_video_frame_failure_is_not_sampling_complete` | Same targeted pass, then the suite. |
| Major. Resume replaced the live `pack_id` with the stored run pack and kept writing vectors. | `identity_space_mismatch` raises before insert when the live pack, or a stored ORT/OpenCV version, differs. Missing stored ORT/OpenCV still resumes. `pack_id` formula is unchanged. | `test_resume_refuses_pack_mismatch_and_closes`, `test_null_ort_and_missing_opencv_still_resume` | In the suite run. |
| Major. `identify_image` scored the live model under the run's pack. | After `load_app()`, mismatch raises `IdentifyError` and writes no faces. | `test_identify_refuses_pack_mismatch_without_writing_faces`, `test_identify_allows_older_run_without_ort_or_opencv` | Passed in the targeted run of 2026-10-11 (51 passed, these two included). Re-checked by the suite. |
| Major. A finished run with zero clusters stayed resumable, and resume skipped ingest. | `cluster_done` requires `cluster_s` in timings when there are ok faces and no cluster rows. `process_folder` always calls incremental ingest. Success stamps `cluster_s` without wiping ingest timings. | `tests/test_progress.py::test_resume_ingests_when_cluster_is_unfinished`, `test_cluster_s_marks_zero_cluster_run_finished`, `test_cluster_keeps_ingest_timings` | In the suite run. |
| Major. `name_cluster` ignored `attach_to_person_id` when the cluster was already linked, and renamed person A. | Raises `ReviewError` before the update when the attach id is a different person. Renaming the linked person still updates `display_name`. | `tests/test_review.py` attach case (raises `already linked`) | In the suite run. |
| Major. Merge `min_intra` missed donor–donor pairs. | `_pairwise_min` on the union. Fallback is the min of stored mins, else null. Threshold unchanged. | `test_merge_min_intra_includes_donor_pairs` (vectors whose true min is B·C ≈ 0.9208, not the survivor–donor 0.98) | In the suite run. |
| Major. Confirmatory FAR/FRR divided by all pairs, including skips. | `far` / `frr` use `n_diff_scored` and `n_same_scored`. Power uses those counts against `MIN_SAME=10` and `MIN_DIFFERENT=10`. Threshold unchanged. | `test_skipped_pairs_do_not_dilute_far`, `test_skipped_same_pairs_stay_underpowered` | In the suite run. |
| Major. EXIF local time was labeled UTC, and a short GPS IFD raised `struct.error`. | Naive local time is stored with no `*_ns` when no offset tag exists. `OffsetTime*` (`±HH:MM`, hours ≤ 14) converts to UTC and sets `*_ns`. JPEG walk skips fill `0xFF`. GPS `struct.error` drops GPS and keeps the datetime. | `test_exif_offset_naive_and_malformed` | In the suite run. |

## Dead code and tests that could not fail

| Finding | Fix | Regression | Result |
|---|---|---|---|
| `or True` in album, archive display-role, and sha256 source checks. | Album assert matches the real deferred copy. Display role asserts `MediaRef.name`. SHA-256 checks `co_names`. | `tests/test_library_browse.py`, `tests/test_shell_adapter.py`, `tests/test_duplicates_integrity.py` | In the suite run. |
| `Application.analyse_visual` and `visual_capabilities` had no caller. | Deleted. Live path remains `submit_visual`. | Existing `tests/test_application_boundary.py` | In the suite run. |
| Source-scan wiring tests. | `test_home_methods_exist` uses `callable`. Pause/cancel checks use `co_names`. GPU preference checks `_effective_prefer_gpu` in `co_names` and `prefer_gpu` in `co_varnames` (the keyword value is a local). | `tests/test_five_repo_completion.py`, `tests/test_closure_pass_wiring.py`, `tests/test_gpu_ep.py::test_home_ingest_passes_product_prefer_gpu` | GPU test passed in the targeted run. The others are in the suite. |
| Definition-only helpers. | Deleted after a repo search found no callers and no QML use: `_page_activity`, `stock_nms`, `format_find_lines`, `crop_jpeg_bytes`, `display_mask_overlay`, `clear_naming_runtime`, `ipc_probe.serve_forever`, `latest_unfinished_run` (info helper kept), `process._ingest_record_from_run`, Home `_show_library_home` and the unused Home/canvas handlers listed in the audit. | Suite import and Home tests. Docs: `GUI-MIGRATION-PLAN.md`, `GUI-TARGET-ARCHITECTURE.md`, `GUI-CAPABILITY-EXPOSURE-MATRIX.md`. | In the suite run. |

Kept on purpose: Tk Home, Tk review-ui, `native_shell`, S8 toolkit, `FaceKitProvider.as_runtime`, `GuiCommand.disable_reason`, `AppResetError`, `ProviderUnavailable`, `_run_visual_inline` (still used when the canvas has no store), `_cluster_record_from_run`. QML slot names on `bridge.py` are not dead. `bridge.py` was not edited.

## Consistency, resources, errors, build

| Finding | Fix | Regression | Result |
|---|---|---|---|
| Identity wheels unpinned. CI did not install them. `pack_id` omits ORT and OpenCV. | Pins: `insightface==2.0`, `onnxruntime==1.30.0`, `opencv-python-headless==5.0.0.93`, `numpy==2.5.3`, `pillow==12.3.0` in `pyproject.toml` and `requirements.txt`. CI still installs the portable test set with `--no-deps` so unit tests stay mock-only. Cross-version resume and identify are refused when both sides record ORT or OpenCV. The digest was not widened. | Pack tests above. | Pins are in the tree. `python -m pip_audit -r requirements.txt` exited 0: no known vulnerabilities found. |
| `requires-python` was `>=3.11,<3.14` while README and a 3.14 tester existed. CI ran 3.12 only. | `requires-python` is `>=3.11,<3.15`. README says 3.11–3.14. CI matrix is 3.11, 3.12, and 3.14 on `windows-latest` and `ubuntu-latest`. | `tests/test_entrypoint.py::test_packaging_hygiene` asserts `<3.15`. | Passed in the targeted run. GitHub-hosted 3.11 and 3.14 jobs were not run from this machine. |
| Light tertiary `#8A8A8A` on white is about 3.45:1. | Failing tertiaries only: light `#6E6E6E`, cyber `#678491`, ember `#988976`, Tokyo `#90839D`. Dark mica `#7E8B9C` and gradient `#8A9BB0` already cleared 4.5 and were left alone. Quaternary stays. | `test_atmosphere_tertiary_contrast` and `tests/test_ui_tokens.py` require ≥ 4.5 against surface, surface muted, and surface raised. | In the suite run. |
| Stills had no byte or pixel cap. `MemoryError` is not `OSError`. | `MAX_STILL_BYTES` 256 MiB, `MAX_IMAGE_PIXELS` 80_000_000, checked before a full decode. Video file bytes are not capped. Decoded frames use the pixel cap. | `test_still_byte_and_pixel_caps_do_not_store_media` | In the suite run. |
| `ingest` left the connection open and left the SIGINT handler installed. | `try/finally` closes the connection and restores SIGINT. `signal.signal` off the main thread is caught. | `test_ingest_restores_sigint_and_closes` | In the suite run. |
| Live setup failure left the camera and the store open. Unexpected errors skipped `_finish`. | Outer `try/finally` releases the capture and closes the connection. Failures call `_finish("interrupted")` and re-raise. Detections older than `max(2500 ms, retain_ms)` are pruned. | `test_live_setup_failure_releases_capture` | In the suite run. |
| CLIP was built per image, and failures returned `[]`. | Process-local bundle. Failures are not cached. `clip_last_error()` is copied onto `optional_errors` and is not a concept label. CLIP does not write `faces.person_id`. | `test_clip_runtime_error_is_not_a_concept` | In the suite run. |
| Face crops decoded the full photo and could not cancel. | `QImageReader.setClipRect` before read. `FaceCropImageResponse.cancel()` exists. | `test_face_crop_clips_and_cancel` | In the suite run. |
| IPC probe buffer grew without a newline. | Drop the client above 1 MiB. Unused `serve_forever` deleted. | `test_ipc_oversize_line_closes_client` | In the suite run. |
| Tk Home Lens Ask stayed disabled after `query_media` failed. | Failure calls `done()` on the Tk thread. | `test_lens_failure_clears_busy` | In the suite run. |
| A raising `cancel()` was treated as "keep going" in ingest and watch. | `CancelledError` propagates. Any other `cancel()` exception stops the pipeline. Watch re-raises other errors. | `test_cancel_exception_stops_ingest`, `test_watch_reraises_cancel_errors` | In the suite run. |
| Canvas visual submit swallowed every error and ran inline analysis on the Tk thread. | Any exception clears `_visual_analyzing` and sets a visible status. `JobBusy` says analysis is already running. Inline analysis remains only when there is no store. | Suite canvas tests. | In the suite run. |
| `requirements-dev.txt` was pytest only, so a dev install died at Qt collection. | `dev` extra and `requirements-dev.txt` include `pytest` and `PySide6>=6.6`. Qt is not pinned to 6.11.2. | Collection of the suite on `.venv` (PySide6 6.11.2 already installed). | The suite collected. |
| `pip-audit` used `continue-on-error: true`, and `python -m pip-audit` is not a module. | `continue-on-error` removed. The step runs `python -m pip_audit -r requirements.txt`. | Workflow file `.github/workflows/ci.yml`. Local: `python -m pip_audit -r requirements.txt` exited 0, "No known vulnerabilities found". `python -m pip-audit` exits 1 with "No module named pip-audit". | Local scan passed. The GitHub job was not run. |
| `install-windows.ps1` ignored native non-zero exits on PowerShell 5.1. | `Exit-IfNativeFailed` after venv create, pip upgrade, requirements, and `.[gui]`. Dot-sourcing returns after the function is defined and does not create a venv. | `test_installer_native_failure_and_dotsource` (fake `python.exe` exit 3, and a dot-sourced copy). | Passed in an earlier targeted run. The live installer was not pointed at this repo. MSI was not built. |
| Linux pytest called `xvfb-run` without installing it. | `apt-get install -y libegl1 libpulse0 xvfb` before pytest. | Workflow file. | Not executed on `ubuntu-latest`. |

## Shell load (not an original finding)

The working tree already had an uncommitted `Shell.qml` redesign. That file did not load (`id sidebarColumn` declared twice, then `sidebarCollapsed` was not in scope for children). After those load fixes, the nav `Repeater` drew its rows as visual children with a null QObject parent, so `findChild` missed `peopleButton` and `settingsButton`.

The five rows are now `Loader` children of the sidebar column, with the same labels, icons, and calls. `sidebarCollapsed` lives on the window, and the collapse canvas listens to that property. `lensLine` and `resumeJob` object names the existing tests require are present. `bridge.py` was not edited.

`tests/test_native_shell.py::test_people_desk_uses_review_and_returns_to_the_same_session` and `tests/test_shell_adapter.py::test_shell_exposes_facet_settings_and_similar` passed after that change: 2 passed in 3.50s.

Visible Windows pass, `SEMBLON_VISIBLE_SHELL=1`: `tests/test_shell_visible.py` — 1 passed in 28.71s. That run clicks People, Settings, and the other exposed controls on a real window.

## Checked, not changed

- Bound `IN (?)` placeholders. Not injectable. `review.py` still chunks at 500.
- Review frame and crop caches stay count-capped.
- `onnx_providers` CPU fallback, `progress.emit` swallow, and Qt teardown `except` blocks stay.
- No ruff, mypy, or black config. Lint was not claimed.
- Python 3.11 on this ARM64 PC is not installed. The installed x64 3.14.4 process reports `platform.machine() == ARM64` and `process_execution()` returns `emulated`. The arch detector was not changed.
- `on_frame` exceptions in live capture stay swallowed. That was not in the published UI finding.
- The Tk live overlay on a daemon thread was not in the published checklist and was left as-is.

## Not verified

- GitHub Actions for Python 3.11, 3.14, and Ubuntu `xvfb-run` were not run. The workflow file is updated. Nothing was pushed.
- The real `tools/install-windows.ps1` install, and MSI packaging, were not run. The failure-path test uses a fake `python.exe` so the script cannot create a venv in this repo.
- Screen-reader names were not exercised. The visible shell test did click the exposed controls.
- No lint tool is configured, so no lint result is claimed.
- `python -m pip_audit -r requirements.txt` exited 0 with "No known vulnerabilities found". Cache-deserialization warnings came from pip-audit's HTTP cache. They are not vulnerabilities.

## Suite

Command: `.\.venv\Scripts\python.exe -m pytest -q --tb=line`

Result: exit 0. 1008 passed, 3 skipped, 2 warnings, 543.19s.

Visible shell: `SEMBLON_VISIBLE_SHELL=1` `python -m pytest -q --tb=short tests/test_shell_visible.py` — exit 0, 1 passed in 28.71s.
