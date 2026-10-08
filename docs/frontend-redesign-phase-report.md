# Frontend Redesign Completion Report

## Repository Evidence

- Branch: `fix/native-shell-null-startup`
- Start commit at reporting run: `c0a5419b831643a44ee9d1604d3286104b69d807`
- Working tree during report build:
  - `M semblon/native_shell/bridge.py`
  - `M semblon/native_shell/qml/Shell.qml`
  - `M tests/test_native_shell.py`
- Prior pushed checkpoint for Phase 1/2 hardening: `c0a5419b831643a44ee9d1604d3286104b69d807`

## Capability Matrix

Legend:
- Backend = backend capability implemented
- Bridge = exposed in `ShellBridge`
- UI = exposed in `Shell.qml`
- E2E = automated or runtime evidence

| Capability | Backend | Bridge | UI | E2E | Evidence |
|---|---|---|---|---|---|
| Primary/Advanced mode toggle | Yes | Yes | Yes | Yes | `test_bridge_mode_and_atmosphere_persist`, QML object names `primaryModeButton` / `advancedModeButton` |
| Primary fail-closed message policy | Yes | Yes | Yes | Yes | `test_primary_presentation_fails_closed_and_advanced_preserves_detail`, direct adversarial command output |
| Advanced diagnostics text | Yes | Yes | Yes | Yes | `test_bridge_submit_command_primary_vs_advanced`, QML object `runStatus` |
| People summary command routing | Yes | Yes | Advanced command path | Yes | `test_bridge_submit_command_primary_vs_advanced` |
| Rule-out decision path | Yes | Yes | Yes | Yes | `tests/test_ruled_out.py` (8 passed) |
| Merge selected group | Yes | Yes | Yes | Yes | `test_people_split_uses_visual_face_selection_and_merge_target` |
| Split selected faces | Yes | Yes | Yes | Yes | `test_people_split_uses_visual_face_selection_and_merge_target` |
| Clear split selection | Yes | Yes | Yes | Yes | QML object `clearSplitSelection`, bridge method `clearSplitSelection` |
| Atmosphere selection (15 IDs) | Yes | Yes | Yes | Partial | IDs preserved in `semblon/atmosphere.py`; selector now explicit via ComboBox; targeted runtime sweep not re-run in this pass |
| Add folder from shell header | Yes | Yes | Yes | Partial | UI wired to `shellApi.addFolder()`; full ingest run crashes in env during native-shell full regression |

## Architecture Review

- Preserved canonical path: `Shell.qml -> ShellBridge -> Application -> review.py`.
- No secondary identity writer was introduced.
- No direct UI-to-storage path was introduced.
- Rule-out and other review actions still go through existing review authority methods.
- Existing architecture constraints from `docs/ARCHITECTURE.md` and `docs/CONTRACTS-RULED-OUT.md` remain satisfied.

## Copy And Mode Audit

- Primary mode blocks unknown/internal/technical payloads by fail-closed fallback.
- Advanced mode preserves technical detail for diagnostics.
- Direct adversarial evidence:
  - `PRIMARY_UNKNOWN: Semblon could not show this safely.`
  - `PRIMARY_INTERNAL: Semblon could not show this safely.`
  - `ADVANCED_UNKNOWN: backend timeout while syncing cache`
  - `ADVANCED_TECHNICAL: sqlite error / traceback / cluster_id=c1`
- Primary command behavior is product-safe (name search summary); Advanced adds diagnostics command behavior.

## Theme Audit

- Atmosphere IDs unchanged and still sourced from canonical `ATMOSPHERE_IDS` (15 IDs).
- Default dark behavior remains in prefs resolver (`mica_dark` fallback).
- Explicit saved choice persistence validated by `test_bridge_mode_and_atmosphere_persist` and `tests/test_ui_prefs.py`.
- UI now exposes explicit atmosphere selection via `ComboBox` bound to `shellApi.atmosphereChoices`.

## Test Results

- `pytest tests/test_native_shell.py -q -k "focus_qml_draws_into_strip_without_a_similar_button or bridge_mode_and_atmosphere_persist or bridge_submit_command_primary_vs_advanced or primary_presentation or decision_success_outputs_remain_safe_and_stable or decide_reaches_real_review_writer"`
  - Result: `7 passed, 17 deselected`
- `pytest tests/test_ui_prefs.py -q`
  - Result: `5 passed`
- `pytest tests/test_ruled_out.py -q`
  - Result: `8 passed`
- `pytest tests/test_native_shell.py -q`
  - Result: crashed with Windows access violation in ingest-thread dependency path during `test_shell_add_folder_indexes_appearance_and_draw_finds_it`.
- `git diff --check`
  - Result: clean (no output).

## Windows Journey Report

| Journey Step | Expected | Observed | Evidence |
|---|---|---|---|
| Clean launch shell wiring | Shell loads with bridge/model bindings | Verified by host/QML tests in targeted suite | `test_focus_qml_draws_into_strip_without_a_similar_button` |
| Mode switching | Primary default and Advanced opt-in visible | Verified by mode persistence test and QML controls | `test_bridge_mode_and_atmosphere_persist`, QML `primaryModeButton`/`advancedModeButton` |
| Diagnostics in Advanced only | Diagnostics control and text available in Advanced path | Verified by command test and QML presence | `test_bridge_submit_command_primary_vs_advanced`, QML `runStatus` |
| People review boundary | Decisions route through review functions | Verified via ruled-out and people decision tests | `tests/test_ruled_out.py`, people tests in `tests/test_native_shell.py` |
| Theme selection/persistence | Select and persist atmosphere preference | Verified in tests; 15 IDs preserved in source | `test_bridge_mode_and_atmosphere_persist`, `tests/test_ui_prefs.py`, `semblon/atmosphere.py` |
| Ingest/add-folder real run | Add folder completes and shell remains stable | Blocked in this environment by native crash in full suite ingest path | Full `tests/test_native_shell.py` crash output |

## Outstanding Issues

- Full native-shell regression is currently blocked by Windows native access violation in ingest-thread dependency path.
- Because of this blocker, complete end-to-end runtime proof for ingest-driven journeys in this pass is incomplete.
- Remaining code/report changes are uncommitted at the time this report file is created.

## Verdict

NOT COMPLETE

Reason: required full relevant regression evidence and complete runtime Windows journey coverage are blocked by the environment crash, so acceptance criteria cannot be fully evidenced in this pass.
