# Human verify → then wire

**Status:** Code gates module **WIRED** 2026-09-21 (defaults ON; opt out via env `=0`).  
**Owner declaration 2026-09-21:** human ship gates in §I.5 are **CLOSED / DONE** — see `docs/SEM-ARCH-V1.4.md` §I.5. Native production shell authorized.  
**Gates module:** `semblon/gates.py` · overview `docs/GATES.md`

| # | Gate | Result |
|---|---|---|
| 1 | R3 toolkit bake-off (§6) | **CLOSED / DONE** (owner) — native shell authorized |
| 2 | Ruled out **ship claim** | **CLOSED / DONE** (owner) |
| 3 | Live overlay | Code wired (lab + Home **Live…**) |
| 4 | OCR / CLIP / pose honesty | Code wired (Settings notes when `MODALITY_PRODUCT` on) |
| 5 | APP-1 C.3 Windows live | **CLOSED / DONE** (owner) |
| 6 | R2 IPC probe | Probe on `main` (boundary only) |
| 7 | PERF workers | Harness exists; product default remains `workers=1` |
| 8 | Hierarchy frames | TEST frames (not SPEC) |
| 9 | Named §8.7 shell decision | **CLOSED / DONE** (owner) — see `07-shell-decision.md` |

---

## Wire actions completed (code)

1. `semblon.gates.enabled` defaults **ON**; explicit `0`/`false`/`off` opts out.
2. Review-ui offers **Rule out…** when flag on — product-wire claim **CLOSED / DONE**.
3. Home **Live…** launches overlay with `from_home=True` (asks source/seconds; no auto-start).
4. Settings prints modality honesty `notes` when `MODALITY_PRODUCT` is on.
5. Bake-off / §8.7 **CLOSED / DONE** — implement native shell; refuse Electron/Tauri/Tk AppShell/CustomTkinter.

## Remaining human ship gates

**None** for the items listed in SEM-ARCH §I.5 (owner closed 2026-09-21).

Historical verify procedures below are retained as reference only.

---

## How to use

1. Confirm the **code already exists** path(s) on your branch / `main`.
2. Run **How to verify** on owner Windows hardware (quote paths; project venv) **when executing §I.5 last**.
3. Record Result: PASS / FAIL + date + machine + evidence path (screenshots, JSON, notes).
4. Only after PASS, treat the item as a ship claim. Do not invent PASS earlier.

---

## Index

| # | Gate | Code exists? | Result (blank until human) |
|---|---|---|---|
| 1 | R3 toolkit bake-off (§6) | harness under `tools/r3-bakeoff/` | |
| 2 | Ruled out (CONTRACTS scaffold) | flagged writers + docs | |
| 3 | Live overlay — 2-person camera | `semblon/live_overlay.py` lab CLI | |
| 4 | OCR / CLIP / pose binaries | optional observers + honesty probes | |
| 5 | APP-1 C.3 Windows live gate | JobEngine + Home on `main` (status: check merge) | |
| 6 | R2 IPC probe merge | `semblon/ipc_probe.py` on `grok/r2-ipc-probe` | |
| 7 | PERF workers folder re-measure | `ingest --workers` + `docs/PERF-WORKERS.md` | |
| 8 | R3 §8.6 hierarchy frames | static HTML test frames | |

---

## 1) R3 toolkit bake-off (brief §6)

### Code that already exists

| Piece | Path |
|---|---|
| Human checklist | `docs/r3-artifacts/05-bake-off-checklist.md` |
| Harness README | `tools/r3-bakeoff/README.md` |
| Orchestrator | `tools/r3-bakeoff/run_bakeoff.py` |
| PowerShell wrapper | `tools/r3-bakeoff/Invoke-Bakeoff.ps1` |
| Probes C1–C6 | `tools/r3-bakeoff/probes/c1_*.py` … `c6_*.py` |
| Results schema | `tools/r3-bakeoff/schema/results.schema.json` |
| Gate flag (must not auto-set) | `SEMBLON_BAKEOFF_WINNER` via `semblon.gates.BAKEOFF_WINNER` |

### How to verify

On owner Windows, against a real WinUI3 and/or Qt candidate surface (not Electron/Tauri/Tk AppShell/CustomTkinter):

```text
py -3 tools/r3-bakeoff/run_bakeoff.py --toolkit <WinUI3|Qt> --operator <you>
```

Or `tools/r3-bakeoff/Invoke-Bakeoff.ps1`. Follow `human_steps` in any `pending_human` criterion. Optional: `--frametimes`, `--wcag-pairs`. Fill `docs/r3-artifacts/05-bake-off-checklist.md` blanks only from measured evidence. Overall PASS only if all six criteria PASS.

| Criterion | Result | Evidence path |
|---|---|---|
| C1 OS accent suppress | | |
| C2 Opaque Mica / achromatic | | |
| C3 &lt; 16 ms 4K/60 scrub | | |
| C4 WCAG AA both themes | | |
| C5 10k virtualized grid | | |
| C6 Native a11y tree on custom surfaces | | |
| Overall toolkit | | |

### Wire after PASS

1. Human names the winning toolkit in writing (SEM-ARCH-V1.4 §J / R3 shell decision).
2. Human may set `SEMBLON_BAKEOFF_WINNER=1` **only by hand** — bake-off runners and CI must never write this env.
3. Start native shell implementation against `docs/R3-BRIEF.md` + `docs/r3-artifacts/` (not by polishing Tk Home into the final shell).
4. Do not invent schema columns from the bake-off.

---

## 2) Ruled out (durable negative decision)

### Code that already exists

| Piece | Path |
|---|---|
| Contracts slice | `docs/CONTRACTS-RULED-OUT.md` |
| Parent pointer | `docs/CONTRACTS.md` (Ruled out section) |
| Wiring note | `docs/r3-packets/06-ruled-out-wiring.md` |
| Writer | `semblon/review.py` → `rule_out_subject` |
| UI wrapper | `semblon/review_ui.py` → `apply_rule_out` |
| Gate | `SEMBLON_RULED_OUT` (`semblon.gates.RULED_OUT`) — default **OFF** |

Store mapping (no new columns): `decisions.kind=reject` + `policy_json.action=rule_out`.

### How to verify

```text
set SEMBLON_RULED_OUT=1
.\.venv\Scripts\python.exe -m semblon review rule-out --store <path> --face <id>
  REM or --cluster <id>; optional person attachment per CONTRACTS-RULED-OUT
```

Confirm against `docs/CONTRACTS-RULED-OUT.md` human checklist:

1. `action=rule_out` under `kind=reject` is distinguishable from Ignore (`action=ignore`).
2. Optional `person_id` is correct for “Possible: Maya → Ruled out”.
3. Board/export **shows** Ruled out (does not hide like Ignore).
4. Does not set `clusters.status='ignored'`; does not write `person_id` as enrolment.

| Check | Result | Notes |
|---|---|---|
| Semantics vs Ignore | | |
| Optional person_id | | |
| Board visibility | | |
| Identity firewall intact | | |

### Wire after PASS

1. Expose Rule out on review-ui / Home / future shell (visual: R3 §1 dashed + `≠`).
2. Keep Ignore as deferred; do not collapse the two verbs.
3. Remove **UNWIRED** labels from product docs once chrome ships.
4. Leave product default OFF until that chrome lands; then treat as a normal review verb (still FaceKit-only).
5. Dedicated `decisions.kind='rule_out'` remains PROPOSED only — land only with an explicit CONTRACTS migration if policy discrimination proves insufficient.

---

## 3) Live overlay — two-person camera

### Code that already exists

| Piece | Path |
|---|---|
| Scaffold module | `semblon/live_overlay.py` |
| Engine | `semblon/live.py` → `live_capture` |
| Lab CLI | `semblon lab live-overlay` (`semblon/cli.py`) |
| Doc | `docs/LIVE-OVERLAY.md` |
| Unit tests (fake camera) | `tests/test_live_overlay.py` |
| Gates | `SEMBLON_LIVE_OVERLAY` · `SEMBLON_WIRE_HOME_LIVE` (stronger; Home entry) |

### How to verify

Real webcam or RTSP; **two people** in frame simultaneously (unit tests are not enough):

```text
.\.venv\Scripts\python.exe -m semblon lab live-overlay --store <path> --source 0 --seconds 30
```

Or `set SEMBLON_LIVE_OVERLAY=1` when calling `run_live_overlay`. Confirm:

1. Two boxes update across frames.
2. Track ids stay stable when people do not cross / leave.
3. Labels show ACCEPT (named gallery) and/or UNKNOWN.
4. SQLite: live faces still have `person_id IS NULL`.

| Check | Result | Notes |
|---|---|---|
| Two boxes | | |
| Stable track ids | | |
| ACCEPT / UNKNOWN labels | | |
| No `faces.person_id` write | | |

### Wire after PASS

1. Keep lab entry: `semblon lab live-overlay` / `SEMBLON_LIVE_OVERLAY=1`.
2. Home entry only after overlay PASS: set `SEMBLON_WIRE_HOME_LIVE=1` and add an explicit Home control that requires `--live-overlay` or env — **no auto-start webcam**.
3. Do not assign `person_id` from the overlay. Identity remains Name / review.
4. Do not flip `WIRE_HOME_LIVE` on for clean installs by default.

---

## 4) OCR / CLIP / pose binaries (honesty)

### Code that already exists

| Piece | Path |
|---|---|
| Observers | `semblon/observers.py` (`probe_*_status`, `optional_status`, `ocr_image`, `clip_embed`, `pose_landmarks`) |
| Ingest flag | `semblon ingest … --observers face,color,object,text,clip,pose` (default `face`) |
| CLI status | `semblon lab providers` |
| Honesty doc | `docs/OPTIONAL-MODALITY-STATUS.md` |
| Product gate (UI chrome) | `SEMBLON_MODALITY_PRODUCT` |

### How to verify

On the machine that will run Semblon:

```text
.\.venv\Scripts\python.exe -m semblon lab providers
```

| Modality | Ready only when | Result | Notes |
|---|---|---|---|
| OCR | `pytesseract` + `tesseract` on PATH (`where.exe tesseract`) | | |
| CLIP | `open_clip` + `torch` + local ViT-B-32/openai weights (no status download) | | |
| Pose | `mediapipe.solutions.pose` exists | | |

Missing → `false` + `notes[<key>]` starting with `unavailable:`. Optional smoke with `--observers …` on a still folder; extras must never write `embeddings.modality='face'` or `faces.person_id`.

### Wire after PASS

1. Home Settings may surface `notes` when a flag is false.
2. Docs may list OCR/CLIP/pose as optional extras **for that machine** (still Level 3 / experimental / non-identity).
3. Product chrome for modality surfaces: only with `SEMBLON_MODALITY_PRODUCT=1` after honesty verify.
4. Do **not** add these packages to default `install-windows.ps1` / `requirements.txt` product path; do not flip clean-install defaults on.

---

## 5) APP-1 C.3 Windows live gate

### Code that already exists

| Piece | Path |
|---|---|
| Job door | `semblon/jobs.py` (`JobEngine`) |
| Application facade | `semblon/application.py` |
| Home UI | `semblon/home_ui.py` |
| Contract | `docs/APPLICATION_API.md` |
| Roadmap gate text | `docs/SEM-ARCH-V1.4.md` §C.3 |

**Merge status note:** JobEngine is on `main`. Branch `grok/app1-c3-gate-pass` records C.3 **PASSED** (2026-09-21) in docs. If that commit is **not** on your `main` yet, treat C.3 as still open and run the live gate below before closing the checklist.

### How to verify

Real Windows, live folder ingest via Home (unit tests alone insufficient). Proof list from SEM-ARCH-V1.4 §C.3:

| Proof | Result | Notes |
|---|---|---|
| UI responsive during ingest | | |
| Ingest / progress continue | | |
| Cancel works | | |
| Cancelled recoverable | | |
| Resume / unpause works (same job while paused; Resume-after-cancel = new submit) | | |
| Home reads state during ingest | | |
| Review remains open during ingest | | |
| People / Search usable (no global lockout) | | |
| No nested Tk mainloop | | |
| No Tk from worker threads | | |
| No duplicated JobEngine / hidden second ingest | | |
| No identity-semantics regression | | |
| Kill process does not corrupt store | | |
| Timings recorded | | |

### Wire after PASS

1. If docs on `main` still say C.3 open: merge the C.3 PASS record (`grok/app1-c3-gate-pass` or equivalent) — docs only if code already matches.
2. APP-1 is closed; do not open another APP-1 feature merge. Next is R2 (below) then R3 shell decision inputs.
3. No product-default change required for JobEngine (already the ingest door).

---

## 6) R2 IPC probe (merge if needed)

### Code that already exists

| Piece | Path (on branch `grok/r2-ipc-probe`) |
|---|---|
| Probe server | `semblon/ipc_probe.py` |
| CLI | `semblon lab ipc-probe` |
| Tests | `tests/test_ipc_probe.py` |
| Roadmap | `docs/SEM-ARCH-V1.4.md` §D.1 |

Loopback JSON-lines on `127.0.0.1` only. Ops: `ping`, `status`, `submit_ingest`, `cancel`, `pause`, `unpause`, `result`, `shutdown` (+ push `progress` / `done`). **Not** product IPC (no named pipes, no WinUI host, no LAN bind).

If `semblon/ipc_probe.py` is missing on your checkout, the probe is not merged yet.

### How to verify

```text
.\.venv\Scripts\python.exe -m pytest tests/test_ipc_probe.py -q
.\.venv\Scripts\python.exe -m semblon lab ipc-probe --store <path>
```

Then a JSON-lines client on the printed port: `ping` → `submit_ingest` → progress → `pause` / `unpause` → `cancel` or wait `done` → `result` → `shutdown`. Confirm bind refuses non-loopback.

| Check | Result | Notes |
|---|---|---|
| Unit tests | | |
| Live loopback session | | |
| Non-loopback refused | | |

### Wire after PASS

1. Merge `grok/r2-ipc-probe` (or cherry-pick) to `main` if not already present.
2. Keep labeled as **probe / boundary proof** — do not promote to product IPC or open LAN.
3. Native shell hosts may speak this protocol later; final IPC design remains a separate slice.
4. No identity or schema changes as part of R2 merge.

---

## 7) PERF workers folder re-measure

### Code that already exists

| Piece | Path |
|---|---|
| Flag | `semblon ingest FOLDER --store PATH --workers N` (default **1**) |
| Evidence doc | `docs/PERF-WORKERS.md` |
| Related baselines | `docs/PERF-P0-BASELINE.md`, `docs/PERF-P1-ARM64.md` |

Current design: `--workers` parallelizes **hash** only; single FaceAnalysis on the writer path. Historical multi-session design was slower at w=2/4 on emulated x64 — do not default from that evidence.

### How to verify

Fresh stores; quote paths; prefer **native** host (record arch / emulated honestly):

```text
set FOLDER=<your library folder>
set PERF=%LOCALAPPDATA%\Semblon\perf-workers
.\.venv\Scripts\python.exe -m semblon ingest "%FOLDER%" --store "%PERF%\w1.sqlite" --workers 1
.\.venv\Scripts\python.exe -m semblon ingest "%FOLDER%" --store "%PERF%\w2.sqlite" --workers 2
.\.venv\Scripts\python.exe -m semblon ingest "%FOLDER%" --store "%PERF%\w4.sqlite" --workers 4
```

Compare wall time, face/status counts (must match), SQLite errors (must be none). Append results to `docs/PERF-WORKERS.md` (or a dated addendum). Record machine, arch, EP.

| workers | ingest_s | faces | Result notes |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 4 | | | |
| Default change justified? | | | |

### Wire after PASS

1. **Only if** measured speedup is real on the target native host **and** counts match: consider raising product default — still a separate explicit PR, not silent.
2. Until then: keep default `workers=1`; leave `--workers N` experimental.
3. Do not retune identity thresholds or enable video DBSCAN to shrink `unassigned`.

---

## 8) R3 §8.6 hierarchy frames (IA test)

### Code that already exists

| Piece | Path |
|---|---|
| Clickable test frames | `docs/r3-artifacts/06-hierarchy-frames.html` |
| IA source | `docs/R3-BRIEF.md` §4 |
| Index | `docs/r3-artifacts/README.md` |

### How to verify

Open `06-hierarchy-frames.html` in a browser. Exercise Library (Home/Photos/Videos), People/Unknown, Activity, Settings. Select assets and confirm Inspector splits **Evidence (machine)** vs **Proposed action (human)**. Fail if: Library conflated with observation layer; failed ingest appears as a Library row; Merge observations merged with Assign to person; identity modal appears.

| Check | Result | Notes |
|---|---|---|
| Nav ownership | | |
| Library vs observation | | |
| Inspector split | | |
| Activity owns failures | | |

### Wire after PASS

1. Use frames as acceptance tests while implementing the native shell — not as a Tk redesign brief.
2. Shell navigation must match §4 labels; Inspector must keep the evidence/action split.
3. No schema or toolkit choice implied by this HTML.

---

## Explicit non-goals (do not “wire” from this doc)

- Retuning FaceKit / DBSCAN / identify thresholds
- Fake PASS from portable pytest alone
- Auto-setting `SEMBLON_BAKEOFF_WINNER`
- Promoting R2 loopback probe to LAN / product IPC
- Electron, Tauri, permanent Tk AppShell, CustomTkinter as production shell
- Inventing Ruled-out schema columns without a named CONTRACTS migration
