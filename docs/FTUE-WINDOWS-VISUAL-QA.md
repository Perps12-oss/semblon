# FTUE / First-Success — Windows visual QA checklist

**Superseded 2026-10-05 by the completed PySide6 production migration.** The product path is now `semblon shell`, not `semblon home`. The checklist below was written for the legacy Tk client and is kept as that record. Do not use it as the current product path.

**Status:** Checklist only. Visual QA has **not** been performed by Cursor and **must** be executed by a human on Windows (native ARM64 or x64).

**Product path (historical, this checklist):** `semblon home` (tk Home).

**Journey under test:**

```text
Stage → Add folder → Processing → Completion → To name / Library
```

For every state below, check:

- Frozen-looking states (UI stuck with no progress / no CTA)
- Stale Stage content while ingest or completion should own the surface
- Duplicate buttons for the same action
- Competing CTAs (especially naming / Review)
- Incorrect badges / counts (`To name (N)` = unnamed face groups, not named people)
- Clipped or overlapping controls
- Dead-looking controls (text that looks clickable but is not)
- Incorrect terminology / internal leaks (`run_id`, `JobEngine`, `FaceKit`, `buffalo_l`, `pack_id`, `person_id`)
- Windows-specific layout / DPI / font clipping

---

## 1. Pristine first launch

- [ ] Fresh store (or deleted `%LOCALAPPDATA%\Semblon\store.sqlite` equivalent)
- [ ] Home opens on Stage (capability introduction)
- [ ] Brand / Stage headline readable; no engineering dump
- [ ] Search placeholder is `Search memory…`
- [ ] Header mode chrome: Discover / People / Activity — no “Lens” as a competing product name next to Discover
- [ ] Packs / Live / Duplicates / Canvas do not compete as primary first-run actions

## 2. Stage

- [ ] Exactly **one** clear primary Add/Choose Folder action on Stage
- [ ] Header does **not** also show a second Add Folder while Stage is visible
- [ ] Explore / Discover / People cards introduce capabilities; Activity is not a Stage peer card
- [ ] Privacy line present; no internal terminology

## 3. Folder-selection transition

- [ ] Choose a valid photo folder
- [ ] Immediate leave from Stage (no lingering marketing surface)
- [ ] Processing / progress experience appears without requiring a second click

## 4. Processing while indexed file count is zero

- [ ] `files == 0` and ingest running → processing pane visible
- [ ] Progress / pause / cancel available
- [ ] Footer shows scanning state (not false “Ready” that implies idle Library)
- [ ] Stage content is not still packed underneath

## 5. Processing after files begin appearing

- [ ] Counts / soft progress update via UI queue (no Tk freeze / crash)
- [ ] “Already discovered” strip only shows real faces when present
- [ ] Pause → Resume → Cancel behave as existing JobEngine controls

## 6. Normal completion

- [ ] Completion / result card appears with photos + faces + groups
- [ ] Primary naming CTA is **Start naming** (not Open Review)
- [ ] Start naming opens **People → To name** (`unknown` route)
- [ ] Secondary path can browse Library / add another folder without a second naming door

## 7. Zero-face completion

- [ ] Folder with media but no faces → success copy that does **not** imply people were discovered
- [ ] No “Start naming” primary that claims groups exist
- [ ] Browse / add-another-folder path available

## 8. Partial-failure completion

- [ ] Mixed success/failure counts shown honestly
- [ ] Recovery path present (browse / add folder / start naming when groups exist)
- [ ] Not presented as a clean full success if failures occurred

## 9. Returning user with unnamed groups

- [ ] Library banner: **N face groups are waiting to be named.**
- [ ] Banner button: **Start naming**
- [ ] People chrome badge: **To name (N)** (not People (N) / People · N as identified people)
- [ ] Start naming / badge deep-link to To name workflow

## 10. Empty folder

- [ ] Folder with no supported media → explicit empty/unsupported result
- [ ] Real **Select Different Folder** control (clickable)
- [ ] Not left on Stage pretending nothing happened, and not a false “photos are ready” with invented people

## 11. Empty People

- [ ] Empty People shows bound actions (Add folder / Go to To name), not dead “click here” text
- [ ] No Open Review label

## 12. Empty Search / Discover

- [ ] No-store / no-named-people empties expose real controls (Start naming / Add folder)
- [ ] Search placeholder remains `Search memory…`
- [ ] Discover is the user-facing term; Lens does not appear as a competing chrome label

## 13. Restart during ingest

- [ ] Close Home while ingest runs (cancel-on-exit or force-close per OS)
- [ ] Relaunch → **not** Stage marketing, **not** a falsely completed summary
- [ ] Accurate partial / interrupted state; Resume available when folder is known

## 14. Restart after completion

### Unseen

- [ ] Complete an ingest, close before acknowledging the result card
- [ ] Relaunch → completion summary shown again

### Acknowledged

- [ ] Complete an ingest, leave via Start naming or Browse library
- [ ] Relaunch → normal Library (Memory Canvas), not the completion card again

---

## Sign-off

| Field | Value |
|---|---|
| Tester | |
| Windows edition / arch | |
| Semblon build / commit | |
| Date | |
| Result (PASS / FAIL) | |
| Notes | |

**Reminder:** Cursor cloud agents cannot perform this Windows visual QA. Human verification is required before claiming FTUE visual closure on Windows.
