# P4 — Capability manifest (`available` / `unavailable` / `incompatible`)

**Status:** **P4 complete** (feature Level 2). P5 not started. Release Level 3 not claimed.  
**Branch:** `grok/p4-capability-manifest`  
**Schema:** 8 (unchanged)  
**Freeze:** do not modify `tools/p0/`; do not retune identity thresholds / `decisions.kind`.

## What landed

| Area | Behaviour |
|---|---|
| Three states only | `available` / `unavailable` / `incompatible` via `semblon/capability_manifest.py` |
| Classify | Probe notes with hash/mismatch/load failure → `incompatible`; plain missing → `unavailable` |
| Identity gate | `identify_face` refuses unless `identity_work_allowed()` |
| Category early-exit | `run_category_backfill` reports `incompatible` vs `unavailable` with matching user copy |
| Independence | Identity pause does not mark objects / regions / words unavailable |
| Preflight | Face / object / region packs map to `incompatible` when contract fails; installable only when `missing` |
| Shell notice | Non-blocking capability strip via `incompatible_notice()`; does not set surface unavailable |
| Settings | Face / look / object / OCR incompatible copy says paused until update, not “not installed” |

## Focused verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_p4_capability_manifest.py `
  tests/test_preflight.py `
  tests/test_category_backfill.py `
  tests/test_identify.py `
  --basetemp=.pytest-tmp-p4
```

**Result:** **77 passed** (Windows, this land).

## Known limits (not reopen triggers)

- `surfaceState === "unavailable"` shell chrome remains a broader G1/P9 topic; P4 only separates capability pause from missing install.
- Ordinary UI still never shows the raw strings `available` / `unavailable` / `incompatible`.
- Level 3 release (full suite / dual-arch / packaging) is separate.
