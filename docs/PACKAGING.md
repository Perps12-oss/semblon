# Packaging

**Engineering:** checkout install via `tools/install-windows.ps1`, or per-user **code MSI** via `packaging/msi` (WiX).  
**Verification:** HUMAN VERIFICATION REQUIRED for clean-machine UX (`packaging/msi/smoke-checklist.md`).  
**Redistribution of identity ONNX (YuNet/SFace or buffalo_l):** **UNAVAILABLE** until licence gate L PASS — never bundled in MSI/installer (BYO only).

## Supported install (code) — checkout

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\install-windows.ps1
semblon.cmd --help
semblon.cmd shell
```

The installer runs `pip install -e ".[gui]"` so PySide6 is present. Double-click `semblon.cmd` opens the PySide6 archive (`semblon shell`).

Does not bundle model weights. Ingest does not download YuNet/SFace. `semblon lab pack-accept` pins ONNX files that are already on disk (`docs/IDENTITY-PACK.md`).

Check weights without downloading:

```text
semblon.cmd lab models
```

## Supported install (code) — MSI

WiX project: `packaging/msi/Semblon.wxs` + generated `PayloadComponents.wxs`.  
Windows owner build (this Linux/cloud agent cannot run `wix build`):

```text
dotnet tool install --global wix
powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1
```

Output: `packaging\msi\dist\Semblon-<version>-code.msi`

| Path | Role |
|------|------|
| `%LOCALAPPDATA%\Programs\Semblon` | MSI code install (per-user) |
| `%LOCALAPPDATA%\Semblon` | Store — **survives** MSI uninstall |
| Install tree `*.onnx` / `buffalo_l` | **Must be absent** |

First launch bootstraps `.venv` when `.semblon-msi-install` is present (`tools/msi/bootstrap-install.ps1`). Requires `py -3.12` on the machine.

Optional sign (local):

```text
powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1 -SignThumbprint <cert-sha1>
powershell -NoProfile -ExecutionPolicy Bypass -File tools\msi\build-msi.ps1 -SignPfxPath path\to\cert.pfx -SignPfxPassword <secret>
```

Optional CI: `.github/workflows/msi-release.yml` (`workflow_dispatch`). Builds the code MSI on `windows-latest`. Signs only when repository secret `CODE_SIGNING_PFX_BASE64` is set (plus `CODE_SIGNING_PFX_PASSWORD`). Without those secrets the job still uploads an **unsigned** engineering MSI — that is not Gate C.

Details: `packaging/msi/README.md`.  
Signing runbook: `packaging/msi/SIGNING_GATE.md`.  
Smoke: `packaging/msi/smoke-checklist.md` or `packaging/msi/smoke-clean-vm.ps1`.  
BYO pack hash evidence (not L PASS): `python tools/msi/gate_l_verify_packs.py`.

## Upgrade / uninstall

`tools/install-windows.ps1` reuses `.venv` and does **not** touch `%LOCALAPPDATA%\Semblon`.  
`tools/uninstall-windows.ps1` removes `.venv` and keeps the store unless `-DeleteStore`.  
MSI uninstall removes `%LOCALAPPDATA%\Programs\Semblon` only — **not** the store.

## Licence boundary

| Artifact | Status |
|----------|--------|
| Code MSI / checkout install | Engineering path shipped |
| buffalo_l inside MSI / frozen exe | **UNAVAILABLE** — `docs/licenses.md` |
| First-ingest InsightFace download into user profile | Possible; not redistribution by Semblon installer |

## Not in this release

- MSI / frozen exe / PyInstaller bundle of buffalo_l
- Silent commercial redistribution of InsightFace weights

## Smoke procedure (human) — checkout

1. Clean directory, run `install-windows.ps1`
2. `semblon.cmd --help` exits 0
3. `semblon.cmd` with no arguments opens the PySide archive (`python -m semblon shell`).
4. Process a small stills folder from the shell or `semblon.cmd process`. Name a cluster from People in the shell.
5. `semblon.cmd lab integrity --store "%LOCALAPPDATA%\Semblon\store.sqlite"`

## Smoke procedure (human) — MSI

Follow `packaging/msi/smoke-checklist.md` (build → install → no weights in tree → store survives uninstall).
