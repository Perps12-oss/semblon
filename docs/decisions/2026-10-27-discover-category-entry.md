# Decision — explicit discovery category entry

**Date:** 2026-10-27  
**Status:** implemented on branch; verification pending

## Decision

Add a single **Discover** entry to the production PySide6 shell. It offers four intent-shaped choices:

- **People** opens the existing People review desk.
- **Objects** opens the existing description/search field in object mode.
- **Regions** opens the existing visual-discovery Focus route, using the current photo or the existing first-photo fallback.
- **Words in photos** opens the same search field in text mode.

These are entry points into existing workflows, not separate galleries, indexes, stores, or scanning engines. The archive remains the one source of media and the existing `ArchiveModel` / `PeopleModel` remain the models.

## Capability honesty

Object search is over labels already stored in the library. The object detector add-on is optional; this UI does not claim that a fresh object scan is automatically run or that the add-on is installed. The user-facing sheet says that unavailable or unscanned object data must be reported honestly and that nothing is silently downloaded.

Region discovery remains selection-led: open a photo, point or draw around a detail, then search. It does not silently trigger a full-library scan.

People review continues to require explicit human naming. This change does not change identity thresholds, identity tables, face assignment, or the identity firewall.

## Scope

Presentation and routing only:
- New `DiscoverSheet.qml`
- Main-shell Discover entry and category routing
- Search-field mode handoff so object/text intent is not overwritten on submit
- Focused tests for route wiring and capability copy

No schema, index, detector, embedding, model-download, archive, or identity changes.

## Verification

`tests/test_discover_categories.py` is added. CI and the full relevant test suite remain pending until the branch workflow runs.
