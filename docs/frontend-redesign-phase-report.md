# Frontend Redesign Completion Report

## Repository Evidence

- Branch: `fix/native-shell-null-startup`
- Baseline pushed commit before this repair: `5a5bbc7743bf10d528903db601fdc0a38ba87173`
- Windows machine: Windows 11 ARM64 (`10.0.26200`)
- Canonical test interpreter: `C:\Users\S8633\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- Canonical test command: `C:\Users\S8633\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest ...`
- Process architecture: AMD64 Python running under ARM64 Windows emulation.
- Dependency set in canonical interpreter:
  - `pytest 9.0.3`
  - `cv2 5.0.0`
  - `onnxruntime 1.30.0`
  - `PySide6 6.11.1`
- Pre-fix crash evidence preserved from this run:
  - `C:\Users\S8633\AppData\Local\Python\bin\python.exe -m pytest tests/test_native_shell.py -q`
  - Result: Windows fatal access violation while `test_shell_add_folder_indexes_appearance_and_draw_finds_it` waited in `_wait_idle`; crashing worker thread was `semblon-job-ingest`.

## Root Cause

- `ShellBridge._start_ingest()` passed `on_done=lambda _result: self.ingestFinished.emit()` into the background ingest worker.
- `JobEngine._run_submitted()` executed that callback on the worker thread, so PySide/Shiboken performed Qt signal delivery and Python slot/signature work off the bridge's Qt thread.
- This matched the unstable native crash signatures observed before the fix: ingest worker crashes in `shibokensupport.signature.loader`, `inspect`, and `linecache` while the main test thread waited in `_wait_idle`.
- The defect was shell-specific: synchronous `python -m semblon process ...` runs in the same dependency environment completed successfully, while the background native-shell path intermittently AV'd.

## Fix Implemented

- `semblon/native_shell/bridge.py`
  - queued ingest completion back onto the bridge's Qt thread with `QMetaObject.invokeMethod(..., QueuedConnection)` before emitting `ingestFinished`.
  - preserved existing background ingest, polling, cancellation, and UI refresh behavior.
  - removed the literal `person_id` token from the shell layer without changing rule-out behavior, preserving the native-shell package boundary contract.
- `tests/test_native_shell.py`
  - added `test_bridge_ingest_finished_is_marshaled_to_bridge_thread` to prove the completion callback is delivered on the bridge thread even when `submit_ingest` finishes on a background worker.

## Capability Matrix

Legend:
- Backend = capability implemented
- Bridge = exposed in `ShellBridge`
- UI = exposed in `Shell.qml`
- Evidence = automated or runtime proof from this run

| Capability | Backend | Bridge | UI | Evidence | Notes |
|---|---|---|---|---|---|
| Primary/Advanced mode toggle | Yes | Yes | Yes | Yes | `tests/test_native_shell.py` |
| Primary fail-closed message policy | Yes | Yes | Yes | Yes | `tests/test_native_shell.py` |
| Advanced diagnostics text | Yes | Yes | Yes | Yes | `tests/test_native_shell.py` |
| People summary command routing | Yes | Yes | Yes | Yes | `tests/test_native_shell.py` |
| Rule-out decision path | Yes | Yes | Yes | Yes | `tests/test_ruled_out.py`, `tests/test_review.py` |
| Merge selected group | Yes | Yes | Yes | Yes | `tests/test_native_shell.py`, `tests/test_review.py` |
| Split selected faces | Yes | Yes | Yes | Yes | `tests/test_native_shell.py`, `tests/test_review.py` |
| Clear split selection | Yes | Yes | Yes | Yes | `tests/test_native_shell.py` |
| Atmosphere selection and persistence | Yes | Yes | Yes | Yes | `tests/test_ui_prefs.py`, `tests/test_native_shell.py` |
| Add folder from shell header | Yes | Yes | Yes | Yes | 20 isolated passes, 3 full native-shell suite passes, offscreen shell run |
| Cancel and resume ingest | Yes | Yes | Yes | Yes | offscreen shell run, `tests/test_jobs.py`, `tests/test_process_stage_cancel.py` |
| Persisted archive after relaunch | Yes | Yes | Yes | Yes | separate-process shell relaunch check |

## Architecture Review

- Preserved canonical path: `Shell.qml -> ShellBridge -> Application -> review.py`.
- No secondary identity writer was introduced.
- No direct UI-to-storage mutation path was introduced.
- Review decisions remain in the authorised review workflow.
- No face-clustering parameters were changed.
- No exception swallowing, sleeps, capability disabling, or test weakening was introduced.

## Test Results

- Pre-fix baseline:
  - `C:\Users\S8633\AppData\Local\Python\bin\python.exe -m pytest tests/test_native_shell.py -q`
  - Result: access violation in `semblon-job-ingest` during `test_shell_add_folder_indexes_appearance_and_draw_finds_it`.
- Focused regression:
  - `C:\Users\S8633\AppData\Local\Python\bin\python.exe -m pytest tests/test_native_shell.py -q -k "bridge_ingest_finished_is_marshaled_to_bridge_thread or shell_add_folder_indexes_appearance_and_draw_finds_it or test_native_shell_package_has_no_identity_or_ingest_imports"`
  - Result: `3 passed`.
- Formerly failing add-folder journey, 20 fresh processes:
  - `C:\Users\S8633\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest tests/test_native_shell.py -q -k "shell_add_folder_indexes_appearance_and_draw_finds_it"`
  - Result: `20/20 passed`, all exit codes `0`.
- Full native-shell suite, 3 fresh processes:
  - `C:\Users\S8633\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest tests/test_native_shell.py -q`
  - Result: `25 passed` on run 1, run 2, and run 3.
- Required regression suites:
  - `C:\Users\S8633\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest tests/test_process.py -q`
  - Result: `7 passed`.
  - `C:\Users\S8633\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest tests/test_ui_prefs.py -q tests/test_ruled_out.py -q tests/test_review.py -q tests/test_review_ui.py -q tests/test_identify.py -q tests/test_ingest_workers.py -q tests/test_jobs.py -q tests/test_process_stage_cancel.py -q`
  - Result: all passed.
- Full project suite:
  - `C:\Users\S8633\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`
  - Result: `944 passed, 2 skipped`.
- Hygiene:
  - `git diff --check`
  - Result: clean.

## Windows Journey Report

All runtime steps below used the actual QML native shell host in offscreen mode with the canonical Windows interpreter and disposable media folders.

| Journey Step | Observed Result | Evidence |
|---|---|---|
| Launch application | Window created successfully with title `Semblon`; bridge/model wiring active | offscreen shell harness output: `('launch', True, 'QQuickWindow')`, `('window_visible', True, 'Semblon')` |
| Empty-state before ingest | Archive started empty | `('empty_before', True, True)` |
| Add folder via shell path | `bridge.addFolder()` completed through the live shell bridge with patched file dialog result | offscreen shell harness |
| Ingest remains responsive and completes | job returned to `idle` without crash | `('ingest1_idle', True, 'idle')` |
| Indexed media appears | archive moved out of empty state; DB recorded media and observations | `('empty_after_ingest1', True, False)`, `('media_count_after_ingest1', True, 2)`, `('observation_count_after_ingest1', True, 2)` |
| Corrupt/unsupported files do not crash | `broken.jpg` and `notes.txt` present in disposable folder; ingest still completed | same ingest1 results above |
| Open Focus and return | focus opened on first media id and then closed cleanly via `escape()` | `('focus_opened', True, '...')`, `('focus_closed', True, '')` |
| Search workflow | people search executed; with this disposable data it truthfully reported no people match | follow-up harness: `('result_text_after_search', 'No people matched that search.')` |
| Similar workflow | region similar search completed without crash and produced 8 results | follow-up harness: `('similar_state', 'ready')`, `('similar_count', 8)` |
| Cancel and recover | cancel returned shell to idle; resume was offered and completed | `('cancel_reached_idle', True, 'idle')`, `('resume_available_after_cancel', True, True)`, `('resume_completed', True, 'idle')` |
| Repeated ingest | second folder ingest completed and increased stored media | `('ingest2_idle', True, 'idle')`, `('media_count_after_ingest2', True, 27)` |
| Close during idle | engine disposed without crash | `('shutdown_idle', True, 'engine.deleteLater')` |
| Relaunch and persistence | second shell process reopened existing store with `empty=False` and persisted media count present | separate-process relaunch: `relaunch_media 1`, `relaunch_empty False`, exit codes `0/0` |

## Limitations And Non-Blocking Notes

- PySide6 emitted a font-directory warning during offscreen shell runs because Qt 6 no longer ships fonts in that location. This did not prevent launch, ingest, focus, search, similar, cancellation, shutdown, or relaunch.
- The disposable shell journey used controlled synthetic media and offscreen Qt rendering to avoid touching user data while still exercising the actual Windows native-shell product path.

## Verdict

COMPLETE

Reason: the native-shell access violation was tied to worker-thread signal emission, the fix was implemented in production code, the failing journey passed 20 fresh processes, the full native-shell suite passed 3 fresh runs, the required regression and project suites passed, and the real Windows native shell completed launch, ingest, cancellation/recovery, shutdown, and relaunch persistence without crashing.
