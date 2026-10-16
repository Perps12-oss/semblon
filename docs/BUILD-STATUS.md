# Semblon build status — completion programme tracker

**Authority:** this file is the single completion tracker for the 12-issue programme.  
**Architecture ledger:** `docs/COMPLETION-MATRIX.md` (closed migration / capability ledger).  
**Product contract:** `docs/PRODUCT.md` (vision fixed; this file does not amend it).  
**Do not** treat `docs/ROADMAP.md` as a second status SoT.

| Field | Value |
|---|---|
| Evidence date | 2026-10-16 (programme execution) |
| Branch | `grok/product-truth` |
| HEAD | `6d4f7c36` — *Freeze the product contract and measure the build against it.* (includes earlier product-truth docs + python support policy) |
| Working tree | Programme implementation changes **uncommitted**; pytest-tmp / `.venv-312` / `wheelhouse-completion/` local only; **not pushed** |

## Status vocabulary

| Status | Meaning |
|---|---|
| NOT STARTED | No verified implementation |
| IN PROGRESS | Work exists; acceptance unmet |
| BLOCKED | Named external decision, dependency, or environment prevents completion |
| IMPLEMENTED | Code/config exists; verification incomplete |
| VERIFIED | All defined acceptance criteria pass with recorded evidence |
| DEFERRED | Explicit documented product decision excludes the item from this release |

## Gates

| Gate | Meaning | Status |
|---|---|---|
| A — Core product | E2E visual-memory journey, archive continuity, context where metadata permits | IN PROGRESS (continuity + context + unicode crop evidenced locally; full visible Windows journey not re-run) |
| B — Engineering baseline | Supported CI, lock, identity path, retired surfaces, honest safety/privacy | IN PROGRESS (lock generated; CI green not yet evidenced on this push; 3.14 shell still risky) |
| C — Release | Offline clean install + intended assets + **signed** installer | BLOCKED (no WiX on this machine; no Authenticode cert; buffalo_l redistribution UNAVAILABLE) |

## Dual verdict

| Verdict | Value |
|---|---|
| **1. Product and engineering completion** | **NOT COMPLETE** — Gates A/B unmet (CI matrix not green in this environment; Gate A lacks full visible-shell journey evidence) |
| **2. Release readiness** | **NOT READY** — Gate C blocked: signing credentials absent, WiX absent here, identity redistribution UNAVAILABLE |

Deferred without blocking unrelated work: **02** encryption, **08** product capture UI.

## Twelve-item programme

| ID | Priority | Status | Evidence / remaining |
|---|---|---|---|
| 01 Win crash / Python matrix | P0 | IN PROGRESS | Policy recorded (`docs/decisions/2026-10-16-python-support-policy.md`). SciPy markers applied. Dual OpenCV refuse works. Local 3.14 shell hit `0xc0000139` with mixed PySide6 installs during `build_shell`; non-shell tests passed after single headless OpenCV. **CI matrix green not evidenced this run.** |
| 02 Encrypted store | P2 | DEFERRED | Design + decision: `docs/decisions/2026-10-16-store-encryption-deferred.md`, `docs/THREAT-MODEL.md`. Store remains plaintext. No live DB experiments. |
| 03 Signed offline MSI | P1 | IMPLEMENTED (eng) / BLOCKED (sign+WiX) | Wheelhouse downloaded from lock (`wheelhouse-completion/`, 25 wheels). `wix` not on PATH. Signing BLOCKED — no cert. Unsigned wheelhouse ≠ signed release. |
| 04 Identity engine / pack | P0 | IMPLEMENTED (local) / BLOCKED (redistribute) | Decision: `docs/decisions/2026-10-16-identity-engine-redistribution.md`. `test_face_pack_refuses_download` passed. Licence UNAVAILABLE. |
| 05 Hashed dependency lock | P1 | IMPLEMENTED | `requirements.lock.txt` via `uv pip compile --generate-hashes --python-version 3.12`. CI drift check added for 3.12. Installer prefers `--require-hashes` when lock present. Lock still lists `opencv-python` (insightface dep); install scripts uninstall it. InsightFace **wheel** is `2.0` (METADATA Version 2.0); a dirty venv may report `__version__` 2.1 until reinstalled from lock. **Not VERIFIED** until CI lock step + clean install pass. |
| 06 FaceKit owner workflow | P1 | IMPLEMENTED / BLOCKED (run) | Docs: `docs/FACEKIT-OWNER.md`. Workflow unchanged. No owner pack on this machine — run not green. |
| 07 Retired Tk / review.html / spike | P1 | IMPLEMENTED | Empty `semblon/review_chrome/` removed. CLI remains `shell` only. s8 research retained. Entry tests pass. |
| 08 Screen-capture privacy | P1 | DEFERRED | Decision: `docs/decisions/2026-10-16-screen-capture-deferred.md`. Module docstring corrected. Title-prefix ≠ security. |
| 09 Visual-memory search | P0 | IN PROGRESS | Region crop uses `_decode_still` (unicode). UI notes say colour histogram. `test_crop_reads_non_ascii_windows_path` passed. Full visible archive journey not re-run. |
| 10 Archive continuity | P0 | VERIFIED (unit) | Re-run on HEAD: move/rename, duplicate scan, same-filename/different-content, missing-original integrity — **passed** (see verification log). |
| 11 Contextual discovery | P1 | IMPLEMENTED | `openFocusInContext` scopes day when mtime exists; QML similar thumbs use it. `test_open_focus_in_context_scopes_day_when_mtime_exists` passed. |
| 12 Unified experience + docs | P0/P1 | IN PROGRESS | Tracker/ledger/roadmap roles fixed. Histogram honesty in similar notes. Full Primary journey Windows visible pass not recorded. |

## Python support policy

See `docs/decisions/2026-10-16-python-support-policy.md`.

| Policy | Value |
|---|---|
| Advertised / CI | 3.11–3.14 (`>=3.11,<3.15`) |
| Primary lock baseline | 3.12 |
| SciPy | `1.17.1` if `<3.12`; `1.18.1` if `>=3.12` |

## Verification log (commands actually run)

Environment: Windows ARM64 host; x64 Python 3.12 (`.venv-312`) and x64 Python 3.14 (emulated).

| Command | Result |
|---|---|
| PyPI `requires_python` inventory for pinned deps | Recorded in decision 2026-10-16-python-support-policy |
| `uv pip compile requirements.txt --generate-hashes --python-version 3.12 -o requirements.lock.txt` | exit 0; lock written |
| `pip download -r requirements.lock.txt -d wheelhouse-completion --require-hashes` | exit 0; 25 wheels |
| `.venv-312` pytest (ship audit continuity + region unicode + shell context + frontend + entry) | **55 passed** (`--basetemp=.pytest-tmp-completion4`) |
| Continuity subset re-check | **4 passed** |
| `py -3.14` non-shell continuity/unicode/cli help | **3 passed**; shell fixture **ERROR** + fatal `0xc0000139` in `build_shell` with polluted PySide mix |
| `wix --version` | not found |
| FaceKit owner workflow live run | **not run** (no pack) |
| Full CI matrix GHA after pin fix | **not run** from this agent |
| Signed MSI | **not run** (no cert) |
| Live user database | **not modified** |

## Capability notes

- Default Similar / region match is colour histogram (`color-hist`), not semantic / face identity.
- Pack gate: `assert_face_pack_ready` / `semblon lab pack-accept`; MSI asserts no weights.
- ARM64 OpenCV load remains historically BLOCKED per `docs/PERF-P1-ARM64.md`.

## Outstanding blockers (exact)

1. Green supported CI matrix after SciPy markers (especially 3.11 install + Linux QQuickStyle — mitigated in `host.py`/`conftest.py`, needs GHA evidence).
2. Clean PySide6-only 3.14 Windows shell confirmation (or evidence-based 3.14 shell exclusion).
3. Owner FaceKit pack for issue 06 VERIFIED.
4. buffalo_l redistribution licence for Gate C identity assets.
5. WiX + Authenticode certificate for signed MSI (Gate C).

## What this file will not absorb

Architecture migration status stays in `docs/COMPLETION-MATRIX.md`. Closed FACE gates stay in `docs/FACE-GATES.md`. Product vision stays in `docs/PRODUCT.md`.
