# Production readiness audit — 2026-10-22

**Verdict: NOT READY FOR RELEASE.**

Gate A claims in `docs/BUILD-STATUS.md` were not re-proven on a Windows desktop in this pass. Gate B is not green on GitHub Actions. Gate C stays blocked (Authenticode, weight redistribution, WiX not run here). The store is plaintext by the recorded decision. A green local pytest summary is not a release.

This file is evidence from the working tree after the repairs below. It does not amend `docs/PRODUCT.md`.

## Baseline

| Item | Value |
|---|---|
| Repository | `Perps12-oss/semblon` (private) |
| Starting HEAD | `0f9e29fbba9594bedbe0cbec5403bfe175e52683` (`main`, merge of PR #170, 2026-10-20) |
| Clone | shallow, depth 1, at `/tmp/semblon` |
| Working tree at start | clean |
| Production path | `semblon shell` → `native_shell/run.py` → `host.py` → `Application` → `ShellBridge` → `Shell.qml` |
| Python policy | `>=3.11,<3.15`. CI matrix 3.11–3.14 on `windows-latest` and `ubuntu-latest`. Lock baseline 3.12 |
| Not done | No model-weight download. No external model API. No user archive. No threshold or DBSCAN retune. No encryption implementation. No screen-capture feature. No force-push |

## Environment and commands

Host: Debian bookworm, glibc 2.36. System CPython 3.10 cannot import this tree (`requires-python` excludes it). Tests used `uv venv --python /usr/bin/python3.11 /tmp/semblon-venv`, then `uv pip install -r requirements-dev.txt` and `uv pip install -e ".[dev]"`.

Qt: `apt-get` cannot install packages here (`setgroups`). Chromium's bundled `libEGL.so` lacks `eglQueryString`. Debian Trixie `libegl1` needs `GLIBC_2.38`. Bookworm `libegl1` 1.6.0-1 was extracted to `/tmp/qtlibs`. Every pytest command used:

```text
QT_QPA_PLATFORM=offscreen
LD_LIBRARY_PATH=/tmp/qtlibs/usr/lib/x86_64-linux-gnu
```

| Command | Result |
|---|---|
| Baseline `pytest -q` before repairs | **1 failed, 906 passed, 6 skipped** (36.79s). Failure: `tests/test_ship_audit.py::test_windows_video_open_tries_extended_path` (`NotImplementedError` constructing `WindowsPath` on Linux) |
| `pytest -q` after the repairs in this tree, before the name-lock change | **911 passed, 6 skipped** in 33.25s, then **exit 134** |
| Same full command after pillow 13.0.0 | Same summary and the same abort. The abort is not the pillow pin |
| `pytest` excluding `test_native_shell.py`, `test_timeline_view.py`, `test_shell_frontend.py` | **830 passed, 6 skipped, exit 0** |
| `pytest tests/test_native_shell.py` | **37 passed, exit 0** |
| `pytest tests/test_review.py tests/test_ship_audit.py tests/test_user_box_geometry.py tests/test_memory.py tests/test_cluster.py` after the name-lock repair | **68 passed** once `name_face` was imported (the first attempt failed that import only) |
| `pytest tests/test_ship_audit.py tests/test_discovery_slice_e.py tests/test_observers.py::test_search_text_is_readonly_not_identity` after the path, centroid, and zero-score repairs | **38 passed, exit 0** (2026-10-22, this continuation) |
| `pytest tests/test_ship_audit.py tests/test_review.py tests/test_user_box_geometry.py tests/test_search_contract.py tests/test_index_provider.py tests/test_cluster.py` | **70 passed, exit 0**. Re-run of the earlier repair slice; not a full-suite claim |
| `pip-audit` on the venv before the pillow pin | **exit 1**, pillow 12.3.0, 24 advisories, fix version 13.0.0 |
| `uv pip install pip-audit` then `pip-audit --local` after pillow 13.0.0 | **exit 0**. Only skip is the local package `semblon` |
| `uv pip compile requirements.txt --generate-hashes --python-version 3.12` | Matches `requirements.lock.txt` on the compile that was committed (622 non-comment lines). An earlier compile the same day still had `certifi==2026.7.22`; the next compile floated `certifi` to `2026.10.19`. Unpinned transitives move. Do not regenerate the lock unless the new file is diffed in the same minute |
| GitHub Actions | **Not green.** Restored workflow on this branch created jobs. Push run [39814855887](https://github.com/Perps12-oss/semblon/actions/runs/39814855887) was still `queued` about two minutes later: job `test-matrix (ubuntu-latest, 3.12)` had `runner_name` null and 0 steps. That is not the 3-second `runner_id` 0 failure of run `39365699632`, and it is not a test result |
| Windows desktop, ARM64, MSI, Authenticode, owner pack | **Not run.** This machine is Linux x64 |

Exit 134 text: `Fatal Python error: bool_dealloc: deallocating True or False` during GC while the interpreter was finalizing, after the pass summary. Bare `QApplication` plus numpy and cv2 exits 0. The abort appears only when the shell-heavy modules and the rest of the suite share one process under this container's libEGL/Qt mix. It was not hidden with `os._exit`. It is **not** claimed to happen on GitHub `ubuntu-latest`.

## What was repaired

Each row has a regression test in this tree.

| ID | Defect | Repair | Test |
|---|---|---|---|
| PR-01 | `.github/workflows/ci.yml` at HEAD was a single newline (`f0c42e6` deleted the workflow). | Restored the pre-wipe workflow: matrix `windows-latest`/`ubuntu-latest` × 3.11–3.14, Linux `libegl1` `libpulse0` `xvfb`, hash-lock check on 3.12, pytest, pip-audit, aggregate job `name: test` with `if: always()`. | File review against the parent blob of `f0c42e6`. Not executed on a runner |
| PR-02 | `test_windows_video_open_tries_extended_path` patched `os.name` to `"nt"`. `pathlib.Path` then builds `WindowsPath` and raises `NotImplementedError` on Linux before `open_video` tries the extended path. | Prefix logic is `_extended_prefix` in `semblon/temporal.py`. The test stubs `_extended_win_path` and does not patch process-global `os.name`. | `test_windows_video_open_tries_extended_path`, `test_extended_win_prefix_drive_unc_and_passthrough` |
| PR-03 | `file:{path}?mode=ro` is not read-only when the path contains `#` (the query is dropped) and a literal `%2F` can point at another file. | `semblon/store.py:connect_readonly` uses `Path.as_uri() + "?mode=ro"` and `PRAGMA query_only=ON`. Production read-only opens call it. `connect()` (writers) is unchanged. | `test_readonly_open_keeps_hash_and_percent_in_the_path` |
| PR-04 | Face board boxes are xyxy. `FaceCropImageProvider` and `QRect` expect xywh, so the crop size was the corner, not the width and height. | `geometry.xyxy_to_xywh`. `ShellBridge.face_crop_spec` converts before the provider. | `test_face_corners_become_a_crop_size` |
| PR-05 | NanoDet `detect()` returns corners. Live part boxes were stored as if they were already xywh. | `region_parts._crop_parts` stores `x2-x1`, `y2-y1` and skips inverted boxes. | `test_live_part_box_uses_detector_corners` |
| PR-06 | QML `shellApi.findSimilarFaces()` passes no argument. `@Slot(str)` does not see the Python default. People rows exposed `count` while `Shell.qml` reads `faceCount`. | `@Slot()` and `@Slot(str)` on `findSimilarFaces`. People row dict has both keys. | Existing shell tests still pass. The QML call sites are `Shell.qml` (F shortcut / Same face) and the merge chip at `faceCount` |
| PR-07 | Derived `.semblon-index.npz` could load a pickle object array, and a miss returned `[]`, which `search_similar` treated as authoritative and skipped SQLite. | Labels are unicode arrays. `np.load(..., allow_pickle=False)`. A missing query, empty matrix, bad norm, or dim mismatch returns `None`. A real in-index miss still returns the hit list. | `tests/test_search_contract.py` and `tests/test_index_provider.py` passed in the full summary |
| PR-08 | pillow 12.3.0: pip-audit reported 24 CVEs, fix 13.0.0. Ingest and region search call `PIL.Image.open` on user bytes. | Pin `pillow==13.0.0` in `pyproject.toml` and `requirements.txt`. Lock regenerated. Stale `insightface`, `opencv-python`, and `colorama` dropped from the lock because they are not in `requirements.txt`. | `pip-audit --local` exit 0 |
| PR-09 | `name_faces` records `policy.face_ids` but `cluster._review_locks` only read `moved_faces` and `faces`. `decisions.face_id` is the first id. A later `cluster_run` could group the other named stills. | Locks also include `policy.face_ids`. | `test_name_faces_locks_every_named_face` |
| PR-10 | `name_cluster` refuses a conflicting `attach_to_person_id`. `name_faces` ignored it when any selected face already had a person and kept `next(iter(existing_persons))`. | `name_faces` raises `ReviewError` when `attach_to_person_id` names a different person. Same-person attach is unchanged. | `test_name_faces_refuses_conflicting_attach` |

`merge_clusters` still sets `faces.person_id` for every face in the survivor when any merged cluster has one person, and it refuses two different persons. That is the tested contract in `tests/test_review.py` (`test_merge_reviewed_same_person_keeps_decision_rows` expects `{"f1","f2","f3","f4"}`). The docstring says "not person merge", which means it does not invent a person and does not fuse two persons. It was **not** changed. Thresholds and DBSCAN parameters were not changed.

## Confirmed and left open

| ID | Sev | Status | Evidence |
|---|---|---|---|
| PR-11 | P0 release | OPEN | GitHub Actions has not gone green. Restored YAML is not a run. Historical jobs never received a runner (`runner_id` 0, logs 404). Do not read that as a proven billing-account fact; it is a startup failure with no logs |
| PR-12 | P0 release | BLOCKED | Gate C. `msi-release.yml` is `workflow_dispatch` and signs only when `CODE_SIGNING_PFX_*` is set. Those secrets are not present. WiX was not executed here. Instant failed runs whose workflow *name* is the file path are runner startup failures, not a defect proven in the current dispatch-only YAML |
| PR-13 | P0 release | BLOCKED | Identity redistribution. Runtime path is YuNet + SFace (`opencv/yunet_sface`), provisional `eps=0.45`. Decision 2026-10-16: no production engine cutover (L/Q/P open). `insightface` is not a declared dependency. buffalo_l is not cleared to redistribute. `docs/PRODUCT.md` still says FaceKit is the only identity engine. That sentence was left alone on purpose |
| PR-14 | P1 | BLOCKED | FaceKit owner pack. Workflow and helper exist. No pack on this machine. Evidence JSON is not PASS |
| PR-15 | P2 | DEFERRED | Encryption. No SQLCipher, no DPAPI. `docs/THREAT-MODEL.md` and `docs/decisions/2026-10-16-store-encryption-deferred.md` match the code. Not implemented |
| PR-16 | P1 | REPAIRED | New sha256 at a path used to leave the old `media.path` on the replacement file. `claim_new_media` clears that path first. Old digest and confirmed faces stay. | `test_replaced_bytes_do_not_keep_the_old_path` |
| PR-17 | P2 | REPAIRED | `delete_person` left `clusters.centroid`. An empty cluster now drops it. A cluster with other faces is rebuilt from those `faces.embedding` values. | `test_delete_person_drops_centroid_of_their_cluster` |
| PR-18 | P1 offline | OPEN, not executed | `observers.clip_embed` and `semantic_visual.py` call `open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")`. `open_clip` is not installed in the audit venv. The call was not run. `docs/OPTIONAL-MODALITY-STATUS.md` already says the first download is a deliberate human step. This audit did not prove install, tests, or ordinary browse contact the network |
| PR-19 | P2 | REPAIRED | `score or 1.0` promoted a stored 0 to 1.0. Missing score is still 1.0. | `test_text_search_keeps_a_zero_score` |
| PR-20 | — | NOT REPRODUCED | Windows Python 3.14 access violation. Prior evidence says ingest completion is queued onto the Qt thread (`QMetaObject.invokeMethod`, `QueuedConnection`) and `Shell.qml` does not import `QtMultimedia`. No `0xC0000005` string in the tree. Not executed on Windows in this pass. Do not treat the old note as a new crash, and do not treat this pass as a Windows retest |
| PR-21 | P2 env | OBSERVED | Full-suite exit 134 in this container after a pass summary. Subsets exit 0. Not a product assertion failure |

`identify` ACCEPT writes a decision and does not stamp `faces.person_id`. Inbox labelling that as known is the documented split between a machine verdict and a person. Not changed.

People writes that do stamp `faces.person_id`: `review._resolve_person` via `name_cluster`, `name_face`, `name_faces`, `name_track` (delegates), `split_cluster` (clears leavers, restamps the survivor from `cluster_person`), and `merge_clusters` under the tested contract above. `erasure.delete_person` removes them. `cluster_run` sets `cluster_id` only.

## Security and privacy

- Read-only SQLite URI bypass (PR-03) is fixed and tested, including a folder name `Photos #2 %2F..%2F`.
- Derived index no longer unpickles (PR-07).
- Pillow advisories in the locked set are cleared (PR-08). Reachability of every CVE was not argued; the pin moved because `Image.open` runs on user bytes.
- No credential, token, or private key was found as part of the repaired paths. This was not a secret-scanning product run against history.
- Store at rest: plaintext SQLite under the user ACL. Same-user malware, a synced backup, or a stolen disk can read display names, paths, and face templates. That is the accepted deferred decision, not a new claim of encryption.
- Optional CLIP (PR-18) is the remaining accidental-network concern. It was not triggered here.
- Region pack install remains an explicit hash-pinned download. The region encoder itself does not download.

## Performance

No material optimization was attempted. No before/after timings were taken. The photographic eval numbers already in `docs/BUILD-STATUS.md` were not re-run (they need local weights). Speculative index or QML work was left alone.

## Compatibility and packaging

| Claim | This pass |
|---|---|
| Linux CPython 3.11, offscreen Qt, bookworm libEGL | Test summary green, then finalizer abort (PR-21) |
| CPython 3.12 / 3.13 / 3.14 | Not executed |
| Windows x64 | Not executed |
| Windows ARM64 | Not executed. Historical OpenCV load note remains |
| Clean-machine MSI | Not built |
| Signed installer | Not signed |
| Offline with no optional CLIP/pack | Core tests did not download weights |

## Release recommendation

**NOT READY FOR RELEASE.**

Shipping would mean an unsigned installer, identity weights that are not cleared to redistribute, a CI workflow that has not gone green since it was restored, and no Windows retest of the shell in this audit. Local unit tests passing do not close Gate B or Gate C.

Accepted limitations that are not, by themselves, the release block: plaintext store (explicitly deferred), Tk retirement already recorded, screen capture not a product feature.

## Human decisions still required

1. Provision a GitHub Actions runner and accept or reject the restored `ci.yml` on real Windows and Ubuntu legs.
2. Close L/Q/P (redistribute YuNet/SFace or not; Semblon eval of provisional `eps=0.45`; native ARM64) before any engine sentence in `docs/PRODUCT.md` changes.
3. Provide the owner pack and record PASS, or keep issue 06 blocked.
4. Provide Authenticode material, or keep Gate C blocked.
5. Replacing bytes at a path now keeps the old digest and drops its path. That choice is in `claim_new_media` and tested. It is not a request to delete the old faces.
