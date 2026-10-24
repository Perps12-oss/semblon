# Ship gates — build to the end

**Product contract:** `docs/PRODUCT.md` (unchanged).  
**Status tracker:** `docs/BUILD-STATUS.md`.  
**This file** closes every identified gap that this checkout cannot execute, by an existing decision or by a procedure a reader can run without a new product decision.

No new schema columns. No identity-threshold edits. No second application path.

## Already closed, and stays closed

| Gate | Why it stays closed |
|---|---|
| Architecture migration | `docs/ARCHITECTURE.md` COMPLETE 2026-10-05. Production UI is PySide6 → `Application`. |
| APP-1 C.3 | `docs/COMPLETION-MATRIX.md` VERIFIED ON WINDOWS. |
| FACE-002 → FACE-005 | `docs/FACE-GATES.md`. Not a queue. |
| S1 clustering | `eps=0.40` on the golden buffalo_l run, `min_samples=2`. Do not retune. Do not re-ingest `20260913T153515Z-1e915abe`. |
| Milestone 2 photographic rank | `docs/evidence/photo-region-eval.json`. Do not reopen. |
| Roadmap milestones 1–4 | Archive, point-and-find on that photo set, day context, keep a discovery. Evidence in `docs/BUILD-STATUS.md`. |

## Lens rank bar — implemented here

`feature_rerank` divides each door by the best value in the candidate pool, then applies the published weights. Weights were not edited. Synthetic command:

```text
python tools/eval_lens_retrieval.py --eval-set synthetic
```

Recorded result lives in `docs/evidence/lens-retrieval-eval.json`. Precision is null. The kind door is `SKIPPED` when SigLIP is absent; that is the specified missing-pack behaviour (`docs/decisions/2026-10-19-lens-style-retrieval.md` slice 2). Confirmatory precision waits on `docs/LENS-CONFIRMATORY.md`.

## Out of ship by an existing decision

| Gap | Decision | What ships instead |
|---|---|---|
| ANN / slice 9 | `docs/decisions/2026-10-19-lens-style-retrieval.md` slice 9 and the eval paragraph: exact-scan timing does not justify ANN. `ann_justified` stays false. | Exact derived matrix. SQLite embeddings stay authoritative. `semblon/index_provider.py` `active_vector_index`. |
| Vector DB, Chroma, FAISS as a product dependency | Same decision, explicit refusals. `docs/SEM-ARCH-V1.4.md` §I.4. | Same exact index. |
| Grounding DINO as a required part splitter | Same decision, explicit refusals: do not require Grounding DINO. Slice 3 already ships top-3 NanoDet parts plus Whole area. | If someone adds it later, the contract is already written: user highlight only, top 3, missing pack searches the user box, no library-wide segment, no identity writes, no new columns. |
| ColQwen / heavy VLM on the interactive path | Same decision, stage 3: not in the interactive path. Slice 8 ships the colour + local pixel check after the grid. | A heavier judge, if added, must match `judge_matches`’s return shape, run after the first grid, skip when the pack is missing, and write nothing to the store. It is not a dependency of Find similar. |
| Learned GBDT fit on the synthetic five | Same decision: do not tune GBDT from that run. | Hand weights plus pool fractions are the ship ranker. Train/test split and file names: `docs/LENS-CONFIRMATORY.md`. |
| Store encryption | `docs/decisions/2026-10-16-store-encryption-deferred.md` lines 7–9. Do not encrypt the live store in this release. | Plaintext store under the user ACL. `docs/THREAT-MODEL.md` states that. Do not claim SQLCipher or DPAPI. |
| Product screen-capture UI | `docs/decisions/2026-10-16-screen-capture-deferred.md` lines 7–9. | Lab capture only. Title-prefix filtering is not a privacy boundary. |
| Albums / collections | Not a `docs/PRODUCT.md` workflow. A collection table would be a new schema column, which `docs/CONTRACTS.md` forbids. Kept finds are `{store}.discoveries.json` (roadmap milestone 4, verified). | Keep this find. No album table. |
| Bundled identity weights | `docs/decisions/2026-10-16-identity-engine-redistribution.md` commercial stance: bring-your-own pack until a redistribution licence exists. MSI fail-closed on `.onnx`. | Code install. Operator pins weights with `semblon lab pack-accept`. |
| Rust rewrite, Electron, Tauri, Tk Home, permanent Tk | `docs/SEM-ARCH-V1.4.md` §I.4. `docs/ARCHITECTURE.md`. | PySide6 shell. |

Reopening ANN requires a new measurement, not a new product idea: time an exact top-50 scan on the owner library at the 10k scale gate (`docs/SEM-ARCH-V1.4.md` §H). Record corpus size, milliseconds, and machine in a JSON next to the index seam. Only if that scan is the bottleneck may a provider be added behind `active_vector_index`, over the same SQLite embeddings, approximate flagged, FAISS not a required install. The synthetic 10-row timing is not that measurement.

## Gate B — engineering baseline

**Finish state:** procedure below. This checkout cannot mark it VERIFIED. GitHub Actions on this branch is the evidence, after a runner actually starts.

Current workflow (accepted cost cut, `docs/decisions/2026-10-16-python-support-policy.md` 2026-10-23 paragraph): `.github/workflows/ci.yml` runs Python 3.12 on `windows-latest` only. Ubuntu, 3.11, 3.13, 3.14, the lock compile, and `pip-audit` are not on Actions. `requires-python` stays `>=3.11,<3.15`. That cost cut is not evidence the other cells pass, and it is not permission to drop 3.11 from the advertised range.

Green means:

1. The `test` job on the commit finishes with exit 0 (a queued job with `runner_id` 0 is not green).
2. Local Linux, from a clean `.venv`, the cloud command exits 0:

```text
xvfb-run -a .venv/bin/python -m pytest -q
```

An interpreter-finalizer abort after a green summary (historical exit 134) is not a pass and not, by itself, a GitHub failure. Report the exit code.

3. `python tools/assert_one_opencv.py` prints one headless OpenCV.
4. Owner pack evidence is a separate file (`docs/FACEKIT-OWNER.md`). Missing pack is not a CI failure. It is issue 06, below.

Do not restore the eight-cell matrix in the same change as a product fix unless the cost-cut paragraph is amended by a decision. Do not claim the matrix is green from a laptop log.

## Gate C — signed code install, weights brought by the owner

**Finish state:** code MSI procedure exists. Signature and licence letters are owner inputs. Bundling weights is out of ship (table above). An unsigned upload is an engineering build, not Gate C (`docs/PACKAGING.md`).

Owner, on Windows:

```text
dotnet tool install --global wix
powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1
```

Sign locally with `-SignThumbprint` or `-SignPfxPath`, or dispatch `.github/workflows/msi-release.yml` after setting `CODE_SIGNING_PFX_BASE64` and `CODE_SIGNING_PFX_PASSWORD`. The workflow verifies with `signtool verify /pa`. Then run `packaging/msi/smoke-checklist.md` on a clean machine. Confirm the install tree contains no `.onnx`.

Until those secrets exist, release readiness stays **NOT READY**. That is an absent certificate, not an open product question. The product already requires a signed, versioned package (`docs/PRODUCT.md` workflow 5). The commands above are how that package is produced.

## Identity gates L, Q, I, P

Runtime code path is YuNet + SFace (`docs/IDENTITY-PACK.md`, `docs/BUILD-STATUS.md` issue 04). `docs/PRODUCT.md` still names FaceKit. This ship does not edit that sentence: the evaluation record says a product-approval decision is a separate act and this work is not that act (`docs/decisions/2026-10-16-identity-engine-evaluation.md`).

| Gate | Pass | This checkout |
|---|---|---|
| L | Written rights for the exact ONNX bytes, local SHA-256, NOTICE plan (`docs/licenses.md`) | Not claimed. BYO stands. |
| Q | Semblon detect and recognise measured separately on an owner set. False merge worse than false split. No transfer of `eps`, `min_samples`, or `STRONG_MIN_INTRA` onto SFace. | Not run. No weights downloaded. Provisional `eps=0.45` in `identity_config.py` stays provisional. |
| I | Pack id includes weight hashes. No cross-pack compare. Extras do not write `faces.person_id`. | Code path is in tree. Not a Q pass. |
| P | Windows x64 native and Windows ARM64 native labelled honestly. x64-on-ARM64 is `emulated`. | ARM64 OpenCV load remains BLOCKED (`docs/PERF-P1-ARM64.md`). |

Owner evidence when the pack is already on disk (no download):

```text
semblon lab pack-accept
semblon lab models
python tools/facekit_owner_evidence.py --pack-dir "%USERPROFILE%\.semblon\models\yunet_sface" --out facekit-owner-evidence.json
```

Workflow: `.github/workflows/facekit-owner.yml`. A missing JSON is not PASS.

## ARM64 OpenCV load

**Finish state:** blocked on the owner machine. Probe code is complete.

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\perf_p1_arm64_repro.ps1
```

Pass is a load that returns, then P0 timing, with `process_execution()` `native` on ARM64 Python. Replacing `opencv_geometry500.dll` is the named blocker in `docs/PERF-P1-ARM64.md`. Do not silent-swap S1 onto that tree. Do not invent a speedup ratio. x64 remains the evidenced identity path until that repro passes.

## Whole-machine stress

**Finish state:** owner procedure. Not a second architecture.

Run on the owner Windows machine, workers left at 1 (`docs/PERF-WORKERS-HARNESS.md`):

| Size | What to record |
|---|---|
| 90 | Already the frozen identity baseline. Do not re-ingest the golden dump. |
| 1k / 5k / 10k | Ingest time, memory, DB growth, query latency, cancel/resume, one Focus region search. `docs/SEM-ARCH-V1.4.md` §H. |

Write the numbers into `docs/evidence/` with the machine label (`native` or `emulated`). Raising the worker default waits on `default_gate.verdict=PASS` in a separate change. This file does not raise it.

## Production UX

Field, Focus, Home, People, and the library workspace are on the PySide6 shell. Gate A acceptance is the offscreen journey already listed in `docs/BUILD-STATUS.md` (`test_gate_a_archive_similar_and_context_journey` and the rows under it). A visible desktop grab (`SEMBLON_VISIBLE_SHELL=1`) is optional residual, not an open product workflow. Do not start a second shell.

## Honest release line

The archive code path for point, find, context, and keep is in tree. Synthetic Lens ranks meet the rank bar. The product is **not** release-ready until Gate B’s `test` job is green on a runner and Gate C’s signed code MSI has been smoked, with weights still brought by the owner. Say that. Do not mark a refused precision number, a skipped kind door, or an unsigned MSI as a pass.
