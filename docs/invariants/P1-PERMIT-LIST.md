# P1 paths touched (record, not a gate)

Freeze base: `50722ef`. Useful as a diff checklist against that freeze — not an approval ceremony.

## Production

`semblon/compare.py` · `semblon/identify.py` · `semblon/ingest.py` · `semblon/store.py` · `semblon/erasure.py` · `semblon/reembed.py` · `semblon/live.py` · `semblon/inbox.py` · `semblon/native_shell/adapter.py` · `semblon/native_shell/bridge.py` · `semblon/native_shell/presentation.py` · `semblon/native_shell/qml/People.qml`

## Tests / docs

`tests/test_identify.py` · `tests/test_p1_i1_baseline_detectors.py` · `tests/test_schema.py` · `tests/test_reembed.py` · `tests/test_people_identity_g1.py` · related fixture updates · `docs/invariants/P1-*.md` · BUILD-STATUS / ROADMAP

## Forbidden still

`tools/p0/**` · `docs/invariants/P0-COMPLETION.md` (frozen) · clustering threshold retune · unrelated shell redesign

## Exclusions (do not commit)

`.rescue-compare/` · `docs/ARCHITECTURE-AUDIT-2026-10-28.md`
