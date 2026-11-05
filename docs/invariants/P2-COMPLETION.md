# P2 — Human decision preservation + ErasureIntent DB

**Status:** **P2 complete** (feature Level 2). P3 not started. Release Level 3 not claimed.  
**Branch:** `grok/p2-decision-erasure`  
**Schema:** 8  
**Freeze:** do not modify `tools/p0/`; do not retune identity thresholds / `decisions.kind`.

## What landed

| Area | Behaviour |
|---|---|
| I2 people redo | `_clear_unnamed_faces` clears all unnamed faces; human decisions detach (`face_id` NULL + `former_face_id`) — no stacking, no delete |
| ErasureIntent | Caller type: requestor, scope (`person`\|`library`), reason, authorized_by, optional person/face allowlist |
| DB enforcement | Schema-8 BEFORE DELETE triggers + `semblon_erasure_ok` on every `store.connect` / `init_db` |
| Explicit erase | `delete_person` / `wipe_library` activate intent; originals never deleted |
| identify_evaluations | Still cleared on person erase / face tree delete / wipe (P1-ERASURE-SCOPE) |
| GUI rule-out | “We'll stop suggesting this match. Nothing was removed.” — no Undo (not implemented) |

## Focused verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_p2_decision_erasure.py `
  tests/test_schema.py `
  tests/test_identify.py `
  tests/test_reembed.py `
  tests/test_people_identity_g1.py `
  tests/test_face005.py `
  tests/test_critique_p0.py `
  tests/test_live.py `
  tests/test_category_backfill.py `
  tests/test_ship_audit.py `
  tests/test_review.py `
  --basetemp=.pytest-tmp-p2
```

**Result:** **138 passed** (Windows, this land).

## Known limits (not reopen triggers)

- Detached human decisions keep history via `former_face_id`; they are not auto-rebound onto the next detection for that photo.
- Machine `identify` decisions and unnamed faces remain clearable without ErasureIntent.
- Writable connections that bypass `store.connect` / `init_db` fail closed on protected deletes (no function → trigger abort).
- Level 3 release (full suite / dual-arch / packaging) is separate.
