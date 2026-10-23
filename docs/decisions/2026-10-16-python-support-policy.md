# Decision: Python support policy (dependency evidence)

**Date:** 2026-10-16  
**Status:** Current  
**Tracker:** `docs/BUILD-STATUS.md` issue 01 / 05

## Decision

Advertise and CI-test **Python 3.11, 3.12, 3.13, and 3.14** on Windows and Ubuntu (`requires-python = ">=3.11,<3.15"`), with **marker-correct pins** so every advertised cell can install.

Primary release / lock baseline: **Python 3.12**.

**2026-10-23:** GitHub CI runs only that baseline, on Windows. Ubuntu, 3.11, 3.13, 3.14, the lock compile, and `pip-audit` are not executed on Actions. `requires-python` is still `>=3.11,<3.15`. This is a cost cut, not evidence that the other cells install or pass.

## Evidence (PyPI metadata, 2026-10-16)

| Package | Pin | `requires_python` | Notes |
|---|---|---|---|
| scipy | 1.18.1 | `>=3.12` | Has cp312–cp314 wheels including win_amd64 / win_arm64 |
| scipy | 1.17.1 | `>=3.11` | Last line that installs on 3.11; also has cp314 wheels |
| numpy | 2.4.6 / 2.5.3 | `>=3.11` / `>=3.12` | Already marker-split |
| scikit-image | 0.26.0 | `>=3.11` | cp311–cp314 wheels |
| onnxruntime | 1.30.0 | `>=3.11` | |
| insightface | 2.0 | `>=3.10` | |
| opencv-python-headless | 5.0.0.93 | `>=3.6` | |
| pillow | 12.3.0 | `>=3.10` | |
| onnx | 1.23.2 | `>=3.10` | |
| PySide6-Essentials | 6.12.0 | `>=3.10,<3.16` | |

## Change

```
scipy==1.17.1; python_version < "3.12"
scipy==1.18.1; python_version >= "3.12"
```

Do **not** force 1.18.1 onto 3.11. Do **not** drop 3.11 from the matrix without new evidence. If a later Windows native crash shows 3.14 unsafe, document exclusion with dump/trace evidence and keep the failure visible — do not delete reproducers.

## Non-goals

This decision does not claim Gate B VERIFIED. CI must still pass after the pin change. Native access-violation investigation remains separate.
