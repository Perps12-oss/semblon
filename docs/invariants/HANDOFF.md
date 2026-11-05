# Invariant programme — cold handoff

**Audience:** next agent (no prior chat). Read this before touching code.  
**Date:** 2026-11-05  
**Owner machine:** Windows (native x64 or ARM64). Quote Windows paths. Space after `--out`.

---

## What Semblon is (one paragraph)

Local-first visual memory. One user. No cloud. Production UI = PySide6 `semblon shell` → `Application` → domain / storage / providers. Faces are one capability, not the product centre. Loop: `cluster → review → person → name`. Never `cluster = person`. Schema and identity thresholds are **frozen**. Do not retune clustering. Do not invent a second shell, vector DB, or capability framework.

Read order if stuck: `docs/PRODUCT.md` → `docs/BUILD-STATUS.md` → `docs/ROADMAP.md` → `docs/CONTRACTS.md` → `docs/ARCHITECTURE.md` → `docs/SEM-ARCH-V1.4.md`. Programme contract: `docs/invariants/PROGRAMME.md`.

---

## Programme status (authoritative)

| Phase | Focus | Status | Evidence |
|---|---|---|---|
| P0 | Evidence map / G1 inventory | **Frozen** | `tools/p0/` — **do not modify** |
| P1 | Identity trust boundary | **Complete** (merged) | `P1-COMPLETION.md`, schema 7 |
| P2 | Human decisions + ErasureIntent | **Complete** (merged #218) | `P2-COMPLETION.md`, schema 8 |
| P3 | Source integrity (single-buffer) | **Complete** (merged #219) | `P3-COMPLETION.md` |
| P4 | Capability manifest three-state | **Complete on branch** — land PR | `P4-COMPLETION.md` |
| P5–P9 | Provenance → coverage → search → jobs → bounds | **Not started** | Wait for explicit go |

`main` tip when P4 branched: `4ba6a24` (merge of P3).  
P4 branch: `grok/p4-capability-manifest`.

### Verification levels (no gate bureaucracy)

- **Level 1** — unit / focused behaviour  
- **Level 2** — feature trust path (what P1–P4 claim at land)  
- **Level 3** — release (full suite / dual-arch / MSI) — **not claimed**

---

## What P4 did (so you do not redo it)

Three states only: `available` | `unavailable` | `incompatible`.

| File | Role |
|---|---|
| `semblon/capability_manifest.py` | Classify + identity/category handshake + notice copy |
| `semblon/identify.py` | Refuses unless `identity_work_allowed()` |
| `semblon/category_backfill.py` | Probe `state`; early-exit `incompatible` vs `unavailable` |
| `semblon/preflight.py` | Face/object/region → `incompatible` when contract fails; installable only if `missing` |
| `semblon/native_shell/bridge.py` | Non-blocking `incompatible_notice()` into notice strip |
| `semblon/native_shell/qml/SettingsBody.qml` | Pause copy ≠ “not installed” |
| `tests/test_p4_capability_manifest.py` | Focused Level 2 tests |

Focused land command (already **77 passed** on Windows):

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_p4_capability_manifest.py `
  tests/test_preflight.py `
  tests/test_category_backfill.py `
  tests/test_identify.py `
  --basetemp=.pytest-tmp-p4
```

**Rules that stayed frozen:** `tools/p0/` untouched; identity thresholds / `decisions.kind` untouched; schema still **8**.

---

## Hard exclusions (will poison P4 / P5 commits)

Do **not** commit these unless the human explicitly starts a brain/schema-9 slice:

- `semblon/brain/` (untracked)
- `tests/brain/` (untracked)
- `docs/brain/` (untracked)
- `docs/ARCHITECTURE-AUDIT-2026-10-28.md`
- `.rescue-compare/`
- Stash: `stash@{0}: wip-brain-and-local` (erasure media-scope + store migrations 9–12)

Brain WIP repeatedly re-dirties `semblon/store.py`, `erasure_intent.py`, `forget.py`, and related tests. If those show as modified on a P4/P5 branch: `git checkout HEAD --` them before commit. Importing brain from `store.py` currently circular-breaks collection of identify/category tests.

---

## Process the human expects

1. One slice, one path, branch `grok/<slice>`.
2. Propose briefly only when non-trivial; for authorised “next / go ahead / plow” — implement.
3. Product-led: evidence → implement → verify. No invented gate ceremony.
4. **Stop before push** unless asked to commit/push/PR.
5. **Do not start P5+** until the human says so (after P4 is merged).
6. Exclude unrelated WIP from every commit.
7. Update `docs/BUILD-STATUS.md` for what landed; do not rewrite `docs/PRODUCT.md` to match incomplete work.

Prior merge rhythm: implement → human reviews → “commit-and-push” → PR → human merges → “next”.

---

## Your immediate job (next agent)

1. Confirm P4 PR is open / green / mergeable (or open it if this handoff lands with the commit).
2. After **merge to main**, wait. Do **not** start P5 until authorised.
3. When authorised for **P5** (observation provenance): read `PROGRAMME.md` + `P0-GUI-STATE-TRANSLATION.md` (legacy_unverified / stale / invalid). New schema columns only if the P5 slice and contracts require them — do not invent DDL casually. Identity firewall still applies.
4. Keep PySide6 → Application. Never resurrect Tk Home / review-ui / canvas.

---

## Quick map of closed invariants

| ID | Rule | Where enforced |
|---|---|---|
| I1 | Bad evidence never becomes identity acceptance | compare / identify / P1 |
| I2 | Automation cannot destroy human decisions | ErasureIntent + triggers (P2) |
| I3 | Analyse the bytes you fingerprinted | `source_integrity` (P3) |
| G1 | UI never overclaims | copy tables + People/Settings; P4 separates pause vs missing |

P5 will own provenance states on observations. P6 coverage truth. P7 search evidence then FTS. P8 job crash/idempotency. P9 resource bounds.

---

## Skills / rules

- `.grok/skills/semblon-observe/SKILL.md`
- `.grok/skills/pr-slice/SKILL.md`
- `.grok/skills/identity-firewall/SKILL.md`
- `.grok/skills/ship-python/SKILL.md`
- Repo `AGENTS.md`

UCGS may warn; Phase 1 does not hard-block. Do not auto-fix violations.

---

## Do not

- Retune `eps` / enable video DBSCAN to shrink unassigned  
- Silent S1 OpenCV arch swap  
- Download identity weights in product paths  
- Call x64-on-ARM64 “native”  
- Start Electron / Tauri / permanent Tk AppShell  
- Treat FACE-002→005 as an open queue  

---

**Bottom line:** P0–P3 are on `main`. P4 is implemented and verified (77). Land P4, then idle until the human authorises P5. Keep brain/schema-9 out of the invariant programme commits.
