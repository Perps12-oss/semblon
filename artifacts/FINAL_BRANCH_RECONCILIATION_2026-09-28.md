# Final branch reconciliation — 2026-09-28

**Authority:** `origin/main` @ `646d44b` (Merge pull request #109).  
**Scope:** content reconciliation only for four leftover remotes.  
**Not done here:** merges, cherry-picks, deletes, implementation edits.

Method: for each branch, list commits reachable from the tip but not from `main`, identify files those commits introduce, then compare **blob content** against current `main` (including squash-merge equivalence via `git cherry` and tip-vs-`main` diffs). Design conclusions were checked against `docs/SEM-ARCH-V1.4.md`, `docs/COMPLETION-MATRIX.md`, `docs/R3-BRIEF.md`, and `docs/r3-artifacts/`.

---

## Summary table

| Branch | Unique commits | Unique files (vs merge-base) | Already represented on main? | Superseded? | Still useful? | Recommended action |
| --- | ---: | ---: | --- | --- | --- | --- |
| `cursor/cloud-agent-1790029604589-pl3zf` | 1 (`c9758e6`) | 1 new: `docs/SEM-RECONCILIATION-2026-09-21.md` (727 lines) | **No** — file absent on `main` | **Yes** — product conclusions conflict with post-#54/`COMPLETION-MATRIX` truth | Historical research only; not active architecture | **ARCHIVE** |
| `cursor/r3-chrome-deepen-9c81` | 9 (of which cherry `+` unique patches remain) | Broad tip tree; durable unique *content* = deepen of `semblon/r3_chrome.py` + tests, plus obsolete `docs/I5-SHIP-GATES-LAST.md` / `docs/r3-packets/README.md` | Design vocabulary **yes** (`R3-BRIEF` + `r3-artifacts`); thin chrome module **yes** (#62 path); deepen Python helpers **no** | Tip still claims §8.7 / shell winner **OPEN**; `I5-SHIP-GATES-LAST` deleted on purpose when §I.5 closed | Design: already on main. Deepen Python: unique but stale experiment | **ARCHIVE** |
| `grok/app1-c3-gate-pass` | 1 (`30ca6be`) | Edits only: `docs/PRODUCTION-STATUS.md`, `docs/SEM-ARCH-V1.4.md` | **Yes** — richer C.3 record on main | **Yes** — 2026-09-21 “PASSED” wording superseded by 2026-09-22 **VERIFIED ON WINDOWS** packet | No unique evidence beyond status prose | **DELETE** |
| `grok/r2-ipc-probe` | 1 (`ed831a2`) | Introduced `semblon/ipc_probe.py`, `tests/test_ipc_probe.py`, CLI/`SEM-ARCH` wiring | **Yes** — probe blobs **byte-identical** to `main` | Branch tip docs/CLI are merely **behind** current `main` | Nothing left to salvage | **DELETE** |

---

## Per-branch detail

### 1. `cursor/cloud-agent-1790029604589-pl3zf` → **ARCHIVE**

| Field | Finding |
| --- | --- |
| Tip | `c9758e6` 2026-09-21 — `Cursor: Apply local changes for cloud agent` |
| Ahead / behind | 1 / 121 |
| Unique commits | `c9758e6` only (`git cherry` `+`) |
| Unique files | **Adds** `docs/SEM-RECONCILIATION-2026-09-21.md` — **not present** on `main` |
| Content vs main | No equivalent filename. Related “retired parallel plans” were deleted on 2026-09-22 (`COMPLETION-MATRIX` §Retired docs); this reconciliation was **never** landed under that sweep |

**What the document is.** A large forensic capability matrix (ARCH rows, live/Lens/observers/Canvas/PERF, claim-check, NOW/NEXT/DE-SCOPE) dated 2026-09-21 against commit `2c19d05…`.

**Substantive conclusions vs current architecture.** Many rows are obsolete or **wrong relative to today’s product**:

- Corrected sentence claims **PySide is what `home` launches** and Canvas is a separate Tk process. Current `main`: production GUI is **tk Home + review-ui** (`docs/COMPLETION-MATRIX.md`; `semblon home` → `run_product_home`; optional Qt `semblon shell` is KEEP, not Home).
- Marks IPC (R2) as not implemented — R2 loopback probe is **DONE** on `main` (`semblon/ipc_probe.py`, `semblon lab ipc-probe`).
- Shell-authority conflict and “accept PySide as Home” NOW workstream — **superseded** by #54 / §8.7 CLOSED / matrix COMPLETE.
- Useful as a **time-capsule audit** of mid-September gaps (workers default, ARM64 OpenCV, optional modalities honesty) that the matrix still tracks — but those live in `COMPLETION-MATRIX` / `PERF-P1-ARM64` / `OPTIONAL-MODALITY-STATUS`, not in this file’s outdated shell story.

**Still useful?** As **historical research** only. Do **not** promote into active docs (`SEM-ARCH`, `PRODUCTION-STATUS`, `COMPLETION-MATRIX`).

**Where unique knowledge should live if preserved**

| Material | Destination |
| --- | --- |
| Full 727-line audit | **research artifact** — keep reachable via git object `c9758e6` (and/or copy under `artifacts/` if a browsable path is desired later). **Nowhere** in active architecture docs. |
| Still-true gaps (ARM64 OpenCV load, workers default=1, buffalo_l UNAVAILABLE) | Already in **current documentation** (`COMPLETION-MATRIX`, PERF docs). |
| Implementation | **nowhere** — no code on this branch. |

**Final classification: ARCHIVE**

---

### 2. `cursor/r3-chrome-deepen-9c81` → **ARCHIVE**

| Field | Finding |
| --- | --- |
| Tip | `7f076b6` 2026-09-22 — `feat(r3): deepen chrome vocabulary toward R3-BRIEF` |
| Ahead / behind | 9 / 111 |
| Unique commits (reachable, not on main) | `31154f9`, `c6af692`, `64aaeb4`, `682ba3b`, `7f076b6` (cherry `+`); `9a06f06`, `9e3b5a3`, `b6cc39e` are cherry `-` (patch-equivalent already on main via #62 shakedown path); `4e0a3ae` is a merge commit |
| Related landed PR | #62 `cursor/shakedown-six-dee4` MERGED 2026-09-22 — docs + base R3 chrome + PERF harness; **this deepen tip was never its own merged PR** |

**Already on main (content)**

- Toolkit-agnostic display/processing chrome core: `semblon/r3_chrome.py` + `tests/test_r3_chrome.py` (thinner than tip).
- `docs/PERF-PROVIDER-HARNESS.md` and `tools/perf_provider_harness.py` — **blob-identical** tip vs `main`.
- Design vocabulary: `docs/R3-BRIEF.md` §1–§4 (overlay layers, Disabled≠Unknown≠Processing, 17 components × 9 interactions, IA nav) and canonical Artifacts under `docs/r3-artifacts/` (`01-state-matrix.md`, `03-collision-ledger.md`, …).
- §I.5 human gates: recorded **CLOSED / DONE** inside `docs/SEM-ARCH-V1.4.md` §I.5 + `COMPLETION-MATRIX` (not via the tip’s blank checklist file).

**Unique on tip vs current main**

1. **Deepen Python API** (not on `main`): `OVERLAY_LAYERS`, `INERT_DISTINGUISHER`, `COMPONENTS` / `INTERACTION_STATES`, `COLLISION_RULES`, `NAV_SECTIONS`, `face_box_chrome`, `component_allows`, `link_label`, richer `evidence_from_face` similarity keys, plus matching tests; tip `canvas.overlay_boxes` calls `face_box_chrome`. Main canvas only uses `face_display_state` as a label.
2. **`docs/I5-SHIP-GATES-LAST.md`** — blank DEFERRED checklist. **Absent on main** because it was **retired** when gates closed (`9703c36` / matrix “Retired docs”). Restoring it would reopen a superseded process doc.
3. **`docs/r3-packets/README.md`** — pointer stub. Redundant; Artifacts live under `docs/r3-artifacts/README.md`. Packets dir retired on main.
4. Tip **`SHELL_CHROME_NOTE` / deepen narrative still treat §8.7 shell winner as OPEN** — **stale** vs main (`§8.7 CLOSED / DONE`; production GUI = tk Home COMPLETE).

**UI research/design vs implementation**

| Layer | Status |
| --- | --- |
| Research / design findings (collision rules, overlay model, inert silhouettes, 17×9 matrix, adjectival Possible) | **Already represented** in active docs (`R3-BRIEF`, `r3-artifacts`). |
| Base chrome module from shakedown | **Shipped** on main (thinner module + legend). |
| Deepen encoding + canvas token wiring | **Unmerged experiment** — unique code, not selected after #62; tip status text conflicts with closed §I.5. |

**Still useful?** Design knowledge: **no additional extract needed** (already canonical). Deepen Python: **unique but stale** — useful only as a research encoding of Artifact 1, not as active product work.

**Where unique knowledge should live**

| Material | Destination |
| --- | --- |
| Artifact 1 / collision / overlay rules | **current documentation** / **architecture** — already `docs/R3-BRIEF.md` + `docs/r3-artifacts/*`. |
| Deepen `r3_chrome.py` / tests / tip canvas wiring | **research artifact** via tip `7f076b6` (optional later copy under `artifacts/`). **Not** automatic re-merge into implementation without a new SEM-ARCH slice. |
| `I5-SHIP-GATES-LAST.md` | **nowhere / archive** — obsolete process; §I.5 closed on main. |
| Implementation on this branch as a live queue | **nowhere** — not KEEP. |

**Final classification: ARCHIVE**

---

### 3. `grok/app1-c3-gate-pass` → **DELETE**

| Field | Finding |
| --- | --- |
| Tip | `30ca6be` 2026-09-21 — `docs: record APP-1 C.3 Windows live gate PASS` |
| Ahead / behind | 1 / 134 |
| Unique commits | `30ca6be` only (`git cherry` `+`) |
| Unique files | No new files — only edits to `docs/PRODUCTION-STATUS.md` and `docs/SEM-ARCH-V1.4.md` |

**Content vs main.** Branch records C.3 as **PASSED 2026-09-21** (“human-verified; no conflicts”) and advances roadmap wording toward R2. Current `main` records a **stronger, later** owner packet:

- `docs/SEM-ARCH-V1.4.md` §C.3 — **VERIFIED ON WINDOWS** · **CLOSED** (2026-09-22)
- `docs/COMPLETION-MATRIX.md` — pytest 20 passed; live `semblon home` Pause/Resume + Canvas
- `docs/PRODUCTION-STATUS.md` — same 2026-09-22 owner evidence

No separate evidence attachment, checklist fill, or test artifact exists only on this branch. The 2026-09-21 PASS prose is an earlier status edit **superseded** by the matrix packet.

**Still useful?** No. Knowledge lives in **current documentation** / **test/evidence** references already cited on main.

**Final classification: DELETE**

---

### 4. `grok/r2-ipc-probe` → **DELETE**

| Field | Finding |
| --- | --- |
| Tip | `ed831a2` 2026-09-21 — `feat(R2): loopback JSON-lines JobEngine IPC probe` |
| Ahead / behind | 1 / 132 |
| Unique commits | `ed831a2` only (`git cherry` `+` — squash/rewrite ancestry; content landed) |
| Files introduced at tip | `semblon/ipc_probe.py`, `tests/test_ipc_probe.py`, plus SEM-ARCH/CLI notes |

**Content vs main (IPC specifically)**

| Artifact | Tip vs `main` |
| --- | --- |
| `semblon/ipc_probe.py` | **Identical blob** (`1087c1877e4ec87b…`) |
| `tests/test_ipc_probe.py` | **Identical blob** (`f34aec3a8fa6fa61…`) |
| `semblon lab ipc-probe` | Present on main (`semblon/cli.py`) |
| SEM-ARCH §D.1 | Main states R2 probe **DONE**; tip text is an older subset of the same claim |

**Have findings been incorporated into current IPC/runtime architecture?** **Yes.** The loopback JSON-lines JobEngine probe (ops: ping/status/submit_ingest/cancel/pause/unpause/result/shutdown + progress/done; `127.0.0.1` only; not product IPC) is the on-`main` R2 boundary proof. Tip-vs-`main` diffs on `cli.py` / `SEM-ARCH-V1.4.md` are **branch behind**, not unique forward knowledge.

**Still useful?** No unique material.

**Final classification: DELETE**

---

## Final classifications (one each)

| Branch | Classification | Rationale |
| --- | --- | --- |
| `cursor/cloud-agent-1790029604589-pl3zf` | **ARCHIVE** | Unique 2026-09-21 reconciliation doc not on main; conclusions largely superseded (esp. PySide-as-Home); preserve as history, not active docs. |
| `cursor/r3-chrome-deepen-9c81` | **ARCHIVE** | Design already on main; deepen Python is unique but stale (§8.7 OPEN tip); I5 checklist obsolete. Not active KEEP work. |
| `grok/app1-c3-gate-pass` | **DELETE** | Status-only commit fully superseded by 2026-09-22 VERIFIED packet on main. |
| `grok/r2-ipc-probe` | **DELETE** | Probe source+tests byte-identical on main; R2 findings already incorporated. |

**None of the four is KEEP.** None requires **EXTRACT THEN DELETE** before branch removal: the only “still useful” items are historical/research and are already either (a) on main as design docs / IPC code, or (b) recoverable from recorded tip SHAs `c9758e6` / `7f076b6` after remote branch deletion (git objects remain until GC; cite SHAs here).

---

## Explicit non-actions (this report)

- Did not modify implementation code.
- Did not merge, cherry-pick, or delete remotes.
- Did not alter `main`.

Optional follow-up (owner): delete the two **DELETE** remotes; for the two **ARCHIVE** remotes, either leave SHAs cited above or copy the unique docs/code snapshots into `artifacts/` before remote deletion if a path outside git history is preferred.
