# P3 — Source integrity (single-buffer digest/decode)

**Status:** **P3 complete** (feature Level 2). P4 complete — see `P4-COMPLETION.md`. Release Level 3 not claimed.  
**Branch:** `grok/p3-source-integrity`  
**Schema:** 8 (unchanged)  
**Freeze:** do not modify `tools/p0/`; do not retune identity thresholds / `decisions.kind`.

## What landed

| Area | Behaviour |
|---|---|
| Single buffer | `read_source_buffer` → digest that buffer → `decode_bgr_buffer` only |
| No path fallback | `_decode_bgr` never calls `cv2.imread` after imdecode failure |
| Digest check | `load_source_bgr(..., expected_sha256=)` raises `SourceChanged` on mismatch |
| Ingest observe/semantic | Re-reads once, verifies library sha256 before face/region analysis |
| Category backfill | Same check; outcome `source_changed` + “Changed during scan — will retry.” |
| Re-embed / detail promote | Verify media sha256 before analysis; mismatch skips rewrite |
| GUI | Progress headline prefers that message (`ui_copy.headline`) |

## Focused verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_p3_source_integrity.py `
  tests/test_ingest_workers.py `
  tests/test_category_backfill.py `
  tests/test_reembed.py `
  tests/test_scan_tiers.py `
  --basetemp=.pytest-tmp-p3
```

**Result:** **58 passed** (Windows, this land).

## Known limits (not reopen triggers)

- Interactive Focus / selection decode paths outside ingest tiers may still open paths for display; they do not write identity from a mismatched digest in the paths listed above.
- Detached `source_changed` coverage stays `failed` so the next category pass retries (`_fresh` requires completed).
- Level 3 release (full suite / dual-arch / packaging) is separate.
