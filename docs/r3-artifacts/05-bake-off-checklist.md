# R3 §8.5 — Toolkit bake-off checklist (human-run)

**Status:** NOT STARTED — no PASS/FAIL recorded here.  
**Authority:** `docs/R3-BRIEF.md` §6.  
**Prerequisite:** §8.1–§8.4 artifacts under this folder are complete.  
**Not:** choosing WinUI / Qt / other from preference; inventing schema; polishing Tk Home.

Measure each criterion on the candidate toolkit(s) on the owner’s Windows machine. Leave blanks until a real run. Wrong spec + passing toolkit = wrong product — do not soft-pass.

## Measurement harness (code exists; no PASS)

Runnable stubs live under **`tools/r3-bakeoff/`**. They write a results JSON matching this checklist’s six criteria. The harness **never** sets `pass` / overall PASS.

| Piece | Path |
|---|---|
| README (how to run) | `tools/r3-bakeoff/README.md` |
| Orchestrator | `tools/r3-bakeoff/run_bakeoff.py` |
| PowerShell wrapper | `tools/r3-bakeoff/Invoke-Bakeoff.ps1` |
| Results JSON schema | `tools/r3-bakeoff/schema/results.schema.json` |
| Probes C1–C6 | `tools/r3-bakeoff/probes/c1_*.py` … `c6_*.py` |
| Written results (local) | `tools/r3-bakeoff/results/bakeoff-*.json` |

```text
py -3 tools/r3-bakeoff/run_bakeoff.py --toolkit <WinUI3|Qt> --operator <you>
```

Where a criterion cannot be auto-measured without a real WinUI/Qt app, the JSON criterion has `status: pending_human` and `human_steps` with exact owner actions. Optional: `--frametimes` (C3), `--wcag-pairs` (C4) — still leave PASS blank until human confirms.

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

1. Record results (this file **and** linked `tools/r3-bakeoff/results/*.json`) with machine + toolkit versions.  
2. Fill `docs/r3-artifacts/07-shell-decision.md` — winner only if six-of-six PASS.  
3. Return to `docs/SEM-ARCH-V1.4.md` §J for **native production shell**.  
4. Durable **Ruled out** remains a separate CONTRACTS gap — bake-off does not invent columns.

## Related (already landed)

- §8.6 Clickable hierarchy frames: `docs/r3-artifacts/06-hierarchy-frames.html` (TEST, not SPEC).
- CLI: `python -m semblon lab r3-bakeoff --toolkit dry-run` (same harness; never invents PASS).
