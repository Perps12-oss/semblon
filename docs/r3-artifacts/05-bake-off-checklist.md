# R3 §8.5 — Toolkit bake-off checklist (human-run)

**Status:** NOT STARTED — no PASS/FAIL recorded here.  
**Authority:** `docs/R3-BRIEF.md` §6.  
**Prerequisite:** §8.1–§8.4 artifacts under this folder are complete.  
**Not:** choosing WinUI / Qt / other from preference; inventing schema; polishing Tk Home.

Measure each criterion on the candidate toolkit(s) on the owner’s Windows machine. Leave blanks until a real run. Wrong spec + passing toolkit = wrong product — do not soft-pass.

## Candidates under test

| Toolkit | Machine | Date | Operator | Notes |
|---|---|---|---|---|
| | | | | |
| | | | | |

Rejected still (do not bake-off as production shell): Electron, Tauri, permanent Tk AppShell, CustomTkinter.

## Six criteria (pass / fail blanks)

| # | Criterion | Pass? | Fail notes / evidence path |
|---|---|---|---|
| 1 | Fully suppress OS accent in every native control (focus, selection, toggle, progress). | [ ] PASS · [ ] FAIL | |
| 2 | Opaque achromatic surface over Mica without bleed. | [ ] PASS · [ ] FAIL | |
| 3 | < 16 ms frame time on 4K/60 video scrub. | [ ] PASS · [ ] FAIL | |
| 4 | WCAG AA on all custom controls, both themes. | [ ] PASS · [ ] FAIL | |
| 5 | 10k-thumbnail virtualized grid without jank. | [ ] PASS · [ ] FAIL | |
| 6 | Native accessibility tree on custom-drawn surfaces (face boxes, compare cells). | [ ] PASS · [ ] FAIL | |

Overall bake-off for a toolkit: **PASS only if all six are PASS**. Partial scores do not choose the shell.

## After this checklist

1. Record results (this file or linked run notes) with machine + toolkit versions.  
2. Return to `docs/SEM-ARCH-V1.4.md` §J for **R3 shell decision**.  
3. Durable **Ruled out** remains a separate CONTRACTS gap — bake-off does not invent columns.

## Explicitly deferred

- §8.6 Clickable hierarchy frames (last; test, not spec)
