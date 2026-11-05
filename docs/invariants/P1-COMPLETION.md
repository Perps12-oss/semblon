# P1 — Identity trust boundary

**Status:** **P1 complete** (feature Level 2). P2 separate — see `P2-COMPLETION.md`. Release Level 3 not claimed.  
**Freeze base:** `50722efa8a9522867e37db352c30bc5d786ec1e2`  
**Schema at P1 land:** 7  

## How we verify (replace gate bureaucracy)

| Level | When | What |
|---|---|---|
| 1 — Feature | Every change | Implement · targeted tests · regression · BUILD-STATUS |
| 2 — Trust-critical | Identity, erasure, ingest/retrieval | Invalid inputs · failure · persistence/restart · deletion · known limits |
| 3 — Release | Ship | Full suite · Windows x64/ARM64 · perf/recovery · UX · packaging |

## What landed

| Area | Behaviour |
|---|---|
| Compare / persist | Fail-closed face embeddings; invalid never `status=ok` with blob |
| Identify | Probe + gallery load validation; durable `identify_evaluations`; UNKNOWN valid |
| Re-embed (A11) | Contract on write; delete evaluations for rewritten/unmatched faces |
| Live (A12) | Persist via `_persist_faces`; validate probe; write evaluations; retention deletes evaluations; never auto `person_id` |
| People / G1 (A15) | Named / Not sure / Not checked yet; machine ACCEPT ≠ named |

## Focused verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_identify.py `
  tests/test_p1_i1_baseline_detectors.py `
  tests/test_schema.py `
  tests/test_reembed.py `
  tests/test_people_identity_g1.py `
  tests/test_face005.py `
  tests/test_critique_p0.py `
  tests/test_live.py
```

**Result:** **57 passed** (Windows, this land).

Also: `git diff 50722ef..HEAD -- tools/p0/` empty. `DEFAULT_THRESHOLD` expression unchanged. `decisions.kind` unchanged.

## Known limits (not separate “failed gates”)

- Some invalid-input shapes are source-inspected on shared validators, not each given a dedicated test name.
- Live is not the production shell door; contract still applies when used.
- Full-suite / dual-arch / packaging = Level 3, separate from P1 feature complete.

## Stop

Do not start P2 until explicitly instructed.
