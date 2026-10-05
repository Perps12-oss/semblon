# Semblon — Production Architecture Baseline

**Status:** COMPLETE — 2026-10-05

The production architecture migration is complete.

Semblon's production UI is now:

```text
PySide6 → Application → Domain / Storage / Providers
```

The PySide6 shell (`semblon shell`) is the canonical production product surface. `Application` is the canonical application boundary and owns access to archive, jobs, Lens/search, and related application operations.

## Production architecture

```text
                    PySide6
                       │
                       ▼
                 Application
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
      Archive         Jobs       Lens / Search
        │              │              │
        └──────────────┼──────────────┘
                       ▼
                Domain / Storage
                       │
                 Providers / ML
```

`ArchiveSession` is the application-owned archive service. Qt reaches it through `Application`. It is not a second archive. `JobEngine` is constructed only inside `Application`. `semblon process` is the synchronous headless ingest: it calls `process_folder` and does not construct a second job engine.

The following rules are now architectural constraints:

- PySide6 is the production UI.
- `Application` is the canonical application boundary. It does not import a UI toolkit.
- UI clients do not access storage directly.
- Media lookup crosses the `Application` boundary. UI rendering and decoding may stay local to the UI (Qt uses `QImageReader`).
- NumPy and image arrays do not form `Application` or `JobEngine` command APIs. The engine loads the file from a media id. Arrays stay inside vision and provider code.
- `JobEngine` has one owner: `Application`.
- Lens/query operations have one canonical application door: `Application.query_media` → `lens.query_image`.
- Region Similar has one canonical application operation: `Application.remember_and_find_region` → `region_search.remember_and_find`.
- There is one archive/application ownership model.
- Transitional implementations are not retained merely to avoid migration work.

## Retired architecture

`review.html` and `review_chrome` are retired and are no longer part of Semblon's production architecture.

The former HTML review surface was a developer/QA interface. Its useful underlying review operations remain available through `review_board` / `review.py`. The HTML application itself was not migrated into the product.

No production Review page replaces it.

Historical documentation may continue to reference the former HTML review system where necessary to preserve an accurate record of past development.

## Legacy clients

Tk Home (`semblon home`) and Tk review-ui remain only as temporary legacy clients.

They are not alternative production architecture and must not be used as the basis for new product work.

New production UI work belongs in the PySide6 shell.

## Research and secondary tools

Research tooling such as `tools/s8_toolkit_spike` and the existing Live overlay remain outside the production shell unless explicitly promoted in a future product decision.

Their existence does not create additional production application architecture.

## Migration milestone

ARCHITECTURE MIGRATION — COMPLETE

- Production shell: PySide6
- Application boundary: canonical and UI-independent
- Review HTML: retired
- Tk: legacy only
- Production installer/launcher: PySide6 (`pip install -e ".[gui]"`; double-click `semblon.cmd`)
- Verification: 914 passed / 8 skipped / 0 failed (2026-10-05)
- Schema, identity thresholds, and Lens behavior: unchanged

## Next phase

The architecture migration is closed.

Semblon should now move from architectural consolidation to production product construction.

The next work is not another shell migration, framework investigation, or competing architecture.

The foundation is now fixed.

The product work is to build and finish the Semblon experience on that foundation:

Field + Focus. Archive first. Find, People, Decision, Appearance and Time as lenses/desks on the same session.

The objective is a simple, intentional, polished Windows product—not another architectural prototype.

Future architectural changes must be justified by an actual product or engineering requirement rather than reopening decisions already closed by this migration.

Qt Find is not implemented. Do not invent it as part of reopening the shell.

## Do not resurrect

Do not resurrect Tk Home as the product door, `review.html`, `review_chrome`, `lens_home`, `native_shell/window.py`, or a parallel application/storage path. The production architecture is PySide6 → Application.

## Other authorities

This baseline closes the shell. It does not replace the frozen product contract or the schema.

| File | Job |
|---|---|
| `docs/PRODUCT.md` | Frozen product contract + amendments |
| `docs/CONTRACTS.md` | Schema / CLI / runtime authority |
| `docs/SEM-ARCH-V1.4.md` | Planned-work authority; current shell points here |
| `docs/COMPLETION-MATRIX.md` | What is closed vs still open |
| `docs/APPLICATION_API.md` | Façade commands |
| `docs/PRODUCTION-STATUS.md` | Capability classification |
| `docs/FACE-GATES.md` | Closed FACE validation index |
| `docs/R3-BRIEF.md` | Visual/interaction contract (does not choose a second shell) |
| `docs/REFERENCE-STACK.md` | Feature/UX reference stack (does not override this baseline) |

Human ship gates in `SEM-ARCH-V1.4` §I.5 stay **CLOSED / DONE**. The September 2026 record that production GUI was tk Home, and that Qt was an optional non-product shell, is historical.
