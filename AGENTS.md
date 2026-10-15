# Semblon agent rules

Working name SEMBLON (SEM-blon). FACEKIT is an engineering term only.

Read in order: `docs/PRODUCT.md` → `docs/CONTRACTS.md` → `docs/ARCHITECTURE.md` (production baseline, **COMPLETE** 2026-10-05) → `docs/SEM-ARCH-V1.4.md` (planned work). Where an older SEM-ARCH section names Tk Home as the product door, or calls `docs/ARCHITECTURE.md` a pointer only, the baseline wins. Do not invent a parallel plan, OBS/SIM/VISION tickets, a FACE-n successor queue, or `SEMBLON_IMPLEMENTATION_PLAN.md`.

## Product

Personal local-first Windows product. One user. No cloud. No ACC. Files stay put. SQLite + originals are authoritative. Frozen v1 still says **no GUI required**. The production UI since 2026-10-05 is the PySide6 archive (`semblon shell`). Tk Home, review-ui, and canvas are retired.

Loop: `cluster → review → person → name`. Never `cluster = person`. Generalized (plan only): `group ≠ entity`.

Unknown is valid. False merge > false split. Wrong identity > unknown.

## Now

**North star / planned work:** `docs/SEM-ARCH-V1.4.md`.

S1 identity-quality PASS is closed on golden run `20260913T153515Z-1e915abe`. Do not retune clustering. Do not re-ingest that dump. FACE-002 → FACE-005 is a closed validation index (`docs/FACE-GATES.md`), not the queue.

**Authorized now:** product construction on the closed architecture baseline (`docs/ARCHITECTURE.md`, **COMPLETE** 2026-10-05). Production UI is PySide6 → `Application` → domain / storage / providers. Field + Focus, archive first. Find, People, Decision, Appearance, and Time are future lenses on that session — not new shells. FaceKit remains the only identity engine. Schema and identity thresholds stay frozen. Completion split: `docs/COMPLETION-MATRIX.md`.

**Do not resurrect** Tk Home, `review-ui`, `canvas`, `review.html`, `review_chrome`, `lens_home`, `native_shell/window.py`, or a parallel application/storage path. The production architecture is PySide6 → Application. `tools/s8_toolkit_spike` and the Live overlay are not the production shell.

**Human ship gates CLOSED / DONE** (`SEM-ARCH-V1.4` §I.5): APP-1 C.3 (**VERIFIED ON WINDOWS** 2026-09-22 — APP-1 **CLOSED**), bake-off/§8.7, Ruled-out product-wire claim (**WIRED** #65). Architecture migration is **COMPLETE**. Still refuse Electron/Tauri/permanent Tk AppShell/CustomTkinter; do not invent DDL or reopen identity thresholds.

**Home shell IA LOCKED (2026-10-02):** Model D — Memory-first Stage dissolve (`docs/SHELL-IA.md`). No permanent MAIN sidebar; do not scaffold one. Atmosphere follows Stage → dissolve → Memory (`docs/ATMOSPHERE.md`). Do not reopen sidebar-vs-stage without concrete Model D failure evidence.

**KEEP (not the plan, not the production shell):** S7a sampled-video holdout (`docs/S7A.md`); S8 toolkit spike (`docs/S8-TOOLKIT.md`) as research only; PERF P0 baseline frozen as evidence (`docs/PERF-P0-BASELINE.md`). PERF P1 ARM64 OpenCV hang is historical evidence (`docs/PERF-P1-ARM64.md`), **not** a stop-work order on ingest workers / EP / commit policy. Do **not** retune eps or enable video DBSCAN to shrink `unassigned`.

ARM64 OpenCV **binary** is proven (`cv2.cp314-win_arm64.pyd`, PE `0xaa64`) but **not loadable** in the P1 venv today (`opencv_geometry500.dll` hang). Semblon S1 still uses x64 `cv2` (`0x8664`). Never silent S1 swap. ARM64 ORT `1.30.0` works in `.venv-arm64-perf`. x64 native FACE-000 unverified. Emulation “3–8×” remains hypothesis.

Progress `on_event` spine is **retained**.

## Forbidden unless the current SEM-ARCH slice explicitly requires it

Hands, semantic clustering, public lookup, ACC, vector DB, CustomTkinter, FastAPI, parked §20 libraries, new schema columns, cross-pack compare.

Optional extra observers (color/object/OCR/CLIP/pose) and stall `watchdog.py` / folder `watch` / `live` are authorized as **non-identity** surfaces. They must not write `faces.person_id` or `embeddings.modality='face'`.

FaceKit / InsightFace is the identity engine. `pack_id` includes weight hashes. `buffalo_l` is a family name, not the compare key. Geometry / appearance / objects / semantics must not silently influence identity.

`report` must not write to the store.

## Machine

Windows ARM64 native and Windows x64 native are first-class. x64-on-ARM64 is `emulated` only. Never call that native. Quote Windows paths. Space after `--out`.

## How to work

One slice, one path, branch `grok/<slice>`. Cite file:line or a command you ran. Stop before push. Do not start a Cursor Cloud Agent.
