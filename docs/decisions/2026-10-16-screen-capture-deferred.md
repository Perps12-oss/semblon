# Decision: Product screen-capture UI deferred

**Date:** 2026-10-16  
**Status:** Current — DEFERRED for this release  
**Tracker:** `docs/BUILD-STATUS.md` issue 08

## Decision

Screen capture is **not** a Primary product feature for this release. Keep lab/CLI capture (`semblon lab capture`) and the existing title-prefix guard for that path. Do not present the title-prefix check as comprehensive privacy protection.

## Limits of the current guard

`semblon/privacy.py` skips windows whose title starts with `"semblon"`. That is a convenience filter only:

- It does not stop OS-level capture APIs used by other apps.
- It does not cover renamed windows, other Semblon process titles that omit the prefix, or non-title metadata.
- It is not a security boundary.

## If capture returns as a product feature

Implement visible capture status, user-configurable exclusions with persistence, and documentation of what is stored and how it is erased. Test matching and non-matching windows.

## Claims

Do not describe Semblon as providing complete screen-capture privacy in UI copy or docs for this release.
