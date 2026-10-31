# Dedupe deletion path audit (F10)

**Date:** 2026-10-30
**Scope:** Destructive API in `semblon/dedupe/deletion.py` vs the production Tidy / duplicates path.

## Actual product call path (scan only)

```text
QML Tidy / "Find copies"
  → ShellBridge openTidy / scan thread
  → ArchiveAdapter.duplicates()
  → semblon.duplicates.find_integrity_groups()
  → semblon.dedupe.scan_exact()   (+ near aHash/dHash in duplicates.py)
  → bridge._build_tidy_sets(report)   # presentation picks only
```

Cited wiring: `bridge.py` tidy scan → `_adapter.duplicates`; `adapter.py` `duplicates()` → `find_integrity_groups`; `duplicates.py` imports `CancelToken, scan_exact` only — not `plan_deletions` / `execute_plan`.

No step on that path deletes original photo files.

## Who calls the destructive API

| Surface | `plan_deletions` / `execute_plan`? | Notes |
|---|---|---|
| `semblon/dedupe/deletion.py` | defines both | `execute_plan` requires `confirmed=True`; re-verifies each target; never passes the keeper to `remove` |
| `semblon/dedupe/__init__.py` | re-exports | Library API |
| `semblon/duplicates.py` | **no** | `scan_exact` + sidecar cache only |
| `semblon/native_shell/adapter.py` | **no** | Integrity report only |
| `semblon/native_shell/bridge.py` Tidy | **no** | Sets / picks from scan report; no delete executor |
| Production QML Tidy | **no** | Presentation over bridge sets |
| `tests/test_dedupe_deletion_and_boundary.py` | yes | Confirmation gate, keeper skip, content-change skip |
| `tools/bench_dedupe.py` | **no** | Uses `scan_exact` only |

## Verdict

- Exact duplicate **scanning** is on the product path as above.
- File **deletion** via `execute_plan` is **not** on the production shell path today. It is a library + test surface.
- Before any further dedupe product work that removes files, wire deletion only behind the existing confirm sheet, pass a Recycle-Bin-style `remove`, and keep keeper + re-verify gates. Do not call `Path.unlink` from Tidy for originals.

## Non-findings

- `bridge.clearLibrary` unlinks discovery/keeps JSON sidecars only; originals stay on disk (`wipe_library`).
