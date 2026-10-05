# R3 toolkit bake-off harness (§8.5 / brief §6)

**Superseded 2026-10-05 by the completed PySide6 production migration.** This harness is historical measurement code. It does not choose the shell. Production architecture is `docs/ARCHITECTURE.md`.

**Status:** code exists — **not** product default; **no PASS claimed**.  
**Authority:** `docs/R3-BRIEF.md` §6 · checklist `docs/r3-artifacts/05-bake-off-checklist.md`.  
**Purpose:** runnable measurement stubs that write a results JSON matching the six bake-off criteria. A human must run them against real candidate toolkit app(s) on owner Windows hardware.

This harness does **not**:

- choose WinUI vs Qt (or any winner)
- invent PASS / FAIL verdicts (`criteria[].pass` and `overall.pass` stay `null`)
- promote PySide Home or replace `semblon home` / `review-ui`
- add schema columns or touch identity

Pattern: **code exists → human verifies → later wiring**.

## Layout

| Path | Role |
|---|---|
| `run_bakeoff.py` | Orchestrator — runs probes 1–6, writes results JSON |
| `schema/results.schema.json` | Machine-writable results schema |
| `lib/results.py` | Empty doc + writer (forces `pass: null`) |
| `lib/contrast.py` | WCAG contrast math for optional C4 input |
| `probes/c1_*.py` … `c6_*.py` | Per-criterion probes |
| `results/` | Generated JSON + human evidence (gitignored except keep) |
| `examples/` | Sample frametime log + WCAG pairs for dry-run |

## Six criteria

1. OS accent suppress (native focus / selection / toggle / progress)  
2. Opaque achromatic surface over Mica without bleed  
3. < 16 ms frame time on 4K/60 video scrub  
4. WCAG AA on all custom controls, both themes  
5. 10k-thumbnail virtualized grid without jank  
6. Native a11y tree on custom-drawn surfaces (face boxes, compare cells)

Where a criterion cannot be auto-measured without a real WinUI/Qt window, the probe emits `status: pending_human` with exact steps in `human_steps`.

## Human must run (owner machine)

1. Check out this branch; open a terminal at the repo root.  
2. Pick **one** candidate toolkit build at a time (WinUI 3 **or** Qt/PySide6 spike — not Electron/Tauri/Tk AppShell).  
3. Generate a stub results file:

```text
py -3 tools/r3-bakeoff/run_bakeoff.py --toolkit WinUI3 --operator <you>
py -3 tools/r3-bakeoff/run_bakeoff.py --toolkit Qt --operator <you>
```

4. Follow `human_steps` inside each criterion of the written JSON (also summarized in the checklist).  
5. Optional auto-ingest when you have logs:

```text
py -3 tools/r3-bakeoff/run_bakeoff.py --toolkit Qt --frametimes tools/r3-bakeoff/examples/frametimes_sample_ms.txt --wcag-pairs tools/r3-bakeoff/examples/wcag_pairs_sample.json
```

6. Copy screenshots / PIX / Accessibility Insights exports under `tools/r3-bakeoff/results/evidence/<toolkit>/cN/`.  
7. Only then set `criteria[i].pass` to `true`/`false` in the JSON **and** tick the matching row in `docs/r3-artifacts/05-bake-off-checklist.md`.  
8. Overall bake-off PASS only if all six are PASS for that toolkit. Partial scores do not choose the shell.

## Dry-run (no toolkit)

```text
py -3 tools/r3-bakeoff/run_bakeoff.py --toolkit dry-run
```

Expect most criteria `pending_human`; with the example flags, C3/C4 become `measured` with `pass: null`.

## Rejected still

Electron, Tauri, permanent Tk AppShell, CustomTkinter — do not bake-off as production shell.
