# Critique P0 — correctness fixes (2026-09-20)

Harsh triage of a multi-file engineering critique. **This slice fixes identity/truth bugs only.** It does not rewrite live/watch, does not widen `pack_id` digests (would invalidate stores), does not add schema indexes, and does not open PERF workers/EP.

| Kept / fixed | Why |
|---|---|
| Inbox: named/`person_id` before `low_quality` | Named faces were vanishing into REVIEW_REQUIRED |
| Inbox: JOIN + prefer `policy_json.decision` | N+1 queries; caller threshold was re-litigating history |
| Tracks: membership-stable `track_id` | `name_track` / re-derive must see the same id |
| Search: RO open, LIKE escape, `search_face(record=False)` | Search must not write; `%` in queries must be literal |
| Ingest: re-hash weights after `load_app` | First-run download must not seal `sha256:unhashed` |
| Engine: `app is None` + unexpected dim fail loud | Silent AttributeError / wrong dim |
| Providers: `as_runtime` after load | Stop advertising CPU-only after a GPU EP load |
| Stats: `busy_timeout` + named=`status=ok` | Consistency + honesty |

| Deferred (valid, not this ticket) | Why |
|---|---|
| `pack_id` 16→32 hex | Breaks every existing store compare key |
| `compare()` numpy / model cache / DDL indexes | PERF / contract slices |
| live commit batching / cancel-during-read | Live surface; separate ticket |
| Atomic markdown writes, watchdog races | Real but lower severity |

Branch: `cursor/critique-correctness-28cd`.
